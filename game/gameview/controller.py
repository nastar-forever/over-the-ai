from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

import events
from environment import VERDICT_HOLD, VERDICT_WIN

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

@dataclass
class _Move:
    """One AI move, played back one whole cell at a time (no sub-cell lerp)."""
    ev: events.AIMoved
    step_time: float
    triggers: dict[int, list[tuple[int, int]]] = field(default_factory=dict)  # path idx -> cells to unfreeze
    i: int = 0
    t: float = 0.0

    @property
    def done(self) -> bool:
        return self.i >= len(self.ev.path) - 1


class GameController:
    """Owns the Environment, the log, and every player action. The view only calls these."""

    def __init__(self, make_env, messages: dict, ai_delay: float = 0.4, log_lines: int = 7, *,
                 snapshot, walk_time: float = 0.12, dash_time: float = 0.03,
                 win_delay: float = 0.9, panic_steps: int = 16, panic_time: float = 0.06):
        self.make_env = make_env
        self.msg = messages
        self.ai_delay = ai_delay
        self.snapshot = snapshot            # cell -> hashable look of that cell (layers, state)
        self.walk_time, self.dash_time = walk_time, dash_time
        self.win_delay, self.panic_steps, self.panic_time = win_delay, panic_steps, panic_time
        self.rng = random.Random()
        self.log: deque[str] = deque(maxlen=log_lines)
        self.restart()

    def restart(self):
        self.env = self.make_env()
        self.env.drain()  # discard init events
        self._ai_timer = 0.0
        self.moves: deque[_Move] = deque()
        self.frozen: dict[tuple[int, int], object] = {}   # coord -> old look, until OMI arrives
        self.ai_pos: dict[int, tuple[int, int]] = {}      # ai idx -> drawn cell while animating
        self._held: list = []                             # events logged when the move ends
        self.log.clear()
        self.say("boot")
        self._win_ev = None        # win log line, held until the panic is over
        self._win_shown = False
        self._panic = None         # frames left to play once the panic starts
        self._panic_wait = 0.0
        self._panic_t = 0.0

    def say(self, key: str, **kw):
        tpl = self.msg[key]
        for line in ([tpl] if isinstance(tpl, str) else tpl):
            self.log.append(line.format(**kw))

    # ---- state
    @property
    def moving(self) -> bool:
        return bool(self.moves)
    
    @property
    def panicking(self) -> bool:
        return self.env.verdict == VERDICT_WIN and not self._win_shown

    @property
    def verdict(self) -> int:
        """The verdict only appears once the move animation and the win panic are over."""
        return VERDICT_HOLD if self.moving or self.panicking else self.env.verdict

    @property
    def player_turn(self) -> bool:
        e = self.env
        return not self.moving and e.verdict == VERDICT_HOLD and e.should_player_play()

    @property
    def locked(self) -> bool:
        return not self.player_turn

    @property
    def steps_limit(self) -> int:
        return self.env.mstate.max_player_stepcount

    @property
    def steps_used(self) -> int:
        e = self.env
        return min(e.playersteps - e.last_playersteps, self.steps_limit)

    @staticmethod
    def _name(card) -> str:
        return type(card).__name__

    def can_merge(self, i: int, j: int) -> bool:
        f = self.env.fetched
        if i == j or not (0 <= i < len(f) and 0 <= j < len(f)):
            return False
        a, b = f[i], f[j]
        return (isinstance(a, tuple(b.merging_partners))
                and isinstance(b, tuple(a.merging_partners))
                and any(isinstance(b, r[0]) for r in a.used_in_recipes))

    # ---- player actions
    def play(self, card):
        e = self.env
        if self.locked or card is e.active_card or card not in e.fetched:
            return
        e.cancel_placement()
        if e.play_card(card) and e.active_card is not card:  # instant card
            self.say("card_used", card=self._name(card))

    def place(self, x: int, y: int):
        e = self.env
        card = e.active_card
        if card is not None and not self.locked and e.place(x, y):
            self.say("card_used", card=self._name(card))

    def cancel(self):
        self.env.cancel_placement()

    def rotate(self, how: str):
        t = self.env.active_placement
        if t:
            {"cw": t.rot_cw, "ccw": t.rot_ccw, "flip": t.flip}[how]()

    def shuffle(self):
        if self.locked:
            return
        self.env.cancel_placement()
        if self.env.reroll():
            self.say("shuffle")

    def deposit(self, card):
        e = self.env
        if self.locked or card not in e.fetched:
            return
        e.cancel_placement()
        if len(e.bank) >= e.bank_limit:
            self.say("bank_full")
        elif e.transfer(card):
            self.say("deposit", card=self._name(card))

    def withdraw(self, card):
        e = self.env
        if self.locked or card not in e.bank:
            return
        e.cancel_placement()
        if e.transfer(card):
            self.say("withdraw", card=self._name(card))

    def merge(self, i: int, j: int):
        if self.locked or not self.can_merge(i, j):
            return
        self.env.cancel_placement()
        self.env.merge(i, j)  # logged via MergingHappened

    # ---- frame update
    def update(self, dt: float):
        if self.moving:
            self._tick_move(dt)
            return

        e = self.env
        for ev in e.drain():
            self._route(ev)

        if self.panicking:
            self._tick_panic(dt)
            return

        if e.verdict == VERDICT_HOLD and not e.should_player_play():
            self._ai_timer += dt
            if self._ai_timer >= self.ai_delay:
                self._ai_timer = 0.0
                self._ai_step()
        else:
            self._ai_timer = 0.0

    # ---- AI move playback
    def _ai_step(self):
        e = self.env
        coords = list(e.all_coords())
        before = {c: self.snapshot(e.coord_to_cell(*c)) for c in coords}
        e.aistep()
        evs = e.drain()

        if not any(isinstance(ev, events.AIMoved) for ev in evs):   # stuck / nothing to animate
            for ev in evs:
                self._route(ev)
            return

        # everything the move changed stays at its old look until OMI gets there
        self.frozen = {c: s for c, s in before.items() if self.snapshot(e.coord_to_cell(*c)) != s}

        cur = collapse = None
        for ev in evs:
            match ev:
                case events.AIMoved(ai_idx=i, path=p, mode=m):
                    cur = _Move(ev, self.dash_time if m == "dash" else self.walk_time)
                    self.moves.append(cur)
                    self.ai_pos[i] = p[0]
                    self._log_event(ev)                 # "executed dash..." shows right away
                case events.CellChanged(x=x, y=y):
                    # a wall collapse is emitted just before the CellChanged of the cell that caused it
                    if collapse is not None and cur is not None:
                        path = cur.ev.path
                        idx = path.index((x, y)) if (x, y) in path else len(path) - 1
                        cur.triggers.setdefault(idx, []).extend(collapse.cells)
                    collapse = None
                case _:
                    if isinstance(ev, events.SMWallCollapsed):
                        collapse = ev
                    if isinstance(ev, events.VerdictReached) and ev.verdict == VERDICT_WIN:
                        self._win_ev = ev
                    else:
                        self._held.append(ev)
    
    def _route(self, ev):
        if isinstance(ev, events.VerdictReached) and ev.verdict == VERDICT_WIN:
            self._win_ev = ev            # logged after the panic, not before
        else:
            self._log_event(ev)

    def _plan_panic(self) -> deque:
        """Random hops and short dashes inside OMI's pen, as frames of {ai_idx: cell}."""
        paths = {}
        for idx, ai in enumerate(self.env.ais):
            region = self.env.reachable_cells((ai.x, ai.y))
            pos, path = (ai.x, ai.y), []
            while len(path) < self.panic_steps:
                options = [d for d in DIRS if (pos[0] + d[0], pos[1] + d[1]) in region]
                if not options:
                    break
                dx, dy = self.rng.choice(options)
                for _ in range(self.rng.choice((1, 1, 1, 2, 3, 4))):   # sometimes a short dash
                    nxt = (pos[0] + dx, pos[1] + dy)
                    if nxt not in region:
                        break
                    pos = nxt
                    path.append(pos)
            paths[idx] = path[:self.panic_steps]
        n = max((len(p) for p in paths.values()), default=0)
        return deque({i: p[k] for i, p in paths.items() if k < len(p)} for k in range(n))

    def _tick_panic(self, dt: float):
        if self._panic is None:
            self._panic = self._plan_panic()
            self._panic_wait, self._panic_t = self.win_delay, 0.0
        if self._panic_wait > 0:                 # beat of silence first
            self._panic_wait -= dt
            return
        self._panic_t += dt
        while self._panic_t >= self.panic_time and self._panic:
            self._panic_t -= self.panic_time
            self.ai_pos.update(self._panic.popleft())
        if not self._panic:
            self._win_shown = True
            if self._win_ev is not None:
                self._log_event(self._win_ev)
                self._win_ev = None

    def _tick_move(self, dt: float):
        m = self.moves[0]
        m.t += dt
        while m.t >= m.step_time and not m.done:
            m.t -= m.step_time
            m.i += 1
            self._arrive(m)
        if m.done:
            self.moves.popleft()
            if not self.moves:
                self._finish_move()

    def _arrive(self, m: _Move):
        path = m.ev.path
        self.ai_pos[m.ev.ai_idx] = path[m.i]
        self.frozen.pop(path[m.i], None)
        ahead = set(path[m.i + 1:])
        for c in m.triggers.get(m.i, ()):
            if c not in ahead:                          # cells still on the route unfreeze on arrival
                self.frozen.pop(c, None)

    def _finish_move(self):
        self.frozen.clear()
        self.ai_pos.clear()
        held, self._held = self._held, []
        for ev in held:
            self._log_event(ev)

    def _log_event(self, ev):
        match ev:
            case events.AIMoved(path=p, mode=m):
                self.say("ai_move", mode=m, steps=len(p) - 1, x=p[-1][0], y=p[-1][1])
            case events.VulnExploited(x=x, y=y, wall_level=lv):
                self.say("vuln", x=x, y=y, level=lv)
            case events.LureEaten(x=x, y=y):
                self.say("lure", x=x, y=y)
            case events.SMWallCollapsed(level=lv):
                self.say("wall", level=lv)
            case events.ExitReached(x=x, y=y):
                self.say("exit", x=x, y=y)
            case events.MergingHappened(idle=a, over=b, result=r):
                self.say("merge", a=self._name(a), b=self._name(b), result=self._name(r))
            case events.VerdictReached(verdict=v):
                self.say("win" if v == VERDICT_WIN else "lose")