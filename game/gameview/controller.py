from __future__ import annotations

from collections import deque

import events
from environment import VERDICT_HOLD, VERDICT_WIN


class GameController:
    """Owns the Environment, the log, and every player action. The view only calls these."""

    def __init__(self, make_env, messages: dict, ai_delay: float = 0.4, log_lines: int = 7):
        self.make_env = make_env
        self.msg = messages
        self.ai_delay = ai_delay
        self.log: deque[str] = deque(maxlen=log_lines)
        self.restart()

    def restart(self):
        self.env = self.make_env()
        self.env.drain()  # discard init events
        self._ai_timer = 0.0
        self.log.clear()
        self.say("boot")

    def say(self, key: str, **kw):
        tpl = self.msg[key]
        for line in ([tpl] if isinstance(tpl, str) else tpl):
            self.log.append(line.format(**kw))

    @property
    def locked(self) -> bool:
        e = self.env
        return e.verdict != VERDICT_HOLD or not e.should_player_play()

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
        e = self.env
        if e.verdict == VERDICT_HOLD and not e.should_player_play():
            self._ai_timer += dt
            if self._ai_timer >= self.ai_delay:
                self._ai_timer = 0.0
                e.aistep()
        else:
            self._ai_timer = 0.0
        for ev in e.drain():
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