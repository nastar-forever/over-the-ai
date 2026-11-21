from collections import deque
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pygame

import events as events

@dataclass
class CrossFrameData:
    ai_pos: dict[int, pygame.Vector2] = field(default_factory=dict)   # in float cell coords
    hidden_cells: set[tuple[int, int]] = field(default_factory=set)
    shake: float = 0.0
    flash: tuple[tuple[int, int, int], float] | None = None
    hand: list = field(default_factory=list)
    bank: list = field(default_factory=list)
    
    def reset(self):
        self.ai_pos.clear(); self.hidden_cells.clear()
        self.hand = []; self.bank = []
        self.shake, self.flash = 0.0, None


class Animation(ABC):
    def on_queued(self, cfdata: CrossFrameData): ... # runs when pushed, before it plays

    @abstractmethod
    def update(self, dt: float, cfdata: CrossFrameData): ...

    @abstractmethod
    def is_done(self) -> bool: ...


class Move(Animation):
    WALK_SPEED, DASH_SPEED = 8.0, 28.0 # cells per second

    def __init__(self, ev: events.AIMoved):
        self.ev = ev
        self.n = len(ev.path) - 1
        self.speed = self.DASH_SPEED if ev.mode == "dash" else self.WALK_SPEED
        self.t = 0.0 # progress, in cells
        self._revealed = 0
        self.triggers: dict[int, list[tuple[int, int]]] = {}  # path index -> extra cells to un-hide


    def attach(self, coords, trigger_cell, cfdata):
        """Hide `coords` now, and un-hide them when the AI enters `trigger_cell`."""
        try:
            idx = self.ev.path.index(trigger_cell)
        except ValueError:
            idx = self.n
        self.triggers.setdefault(idx, []).extend(coords)
        cfdata.hidden_cells.update(coords)


    def on_queued(self, cfdata):
        cfdata.ai_pos.setdefault(self.ev.ai_idx, pygame.Vector2(self.ev.path[0]))


    def update(self, dt, cfdata):
        self.t = min(self.t + dt * self.speed, self.n)
        i = int(self.t)
        while self._revealed < i:
            self._revealed += 1
            cfdata.hidden_cells.discard(self.ev.path[self._revealed])
            cfdata.hidden_cells.difference_update(self.triggers.get(self._revealed, ()))
        a = pygame.Vector2(self.ev.path[i])
        b = pygame.Vector2(self.ev.path[min(i + 1, self.n)])
        cfdata.ai_pos[self.ev.ai_idx] = a.lerp(b, self.t - i)


    def is_done(self):
        return self.t >= self.n


class Reveal(Animation): # a batch of CellChanged
    def __init__(self, coords, duration=0.15):
        self.coords, self.duration, self.t = coords, duration, 0.0

    def on_queued(self, cfdata):
        cfdata.hidden_cells.update(self.coords)

    def update(self, dt, cfdata):
        self.t += dt
        if self.t >= self.duration:
            cfdata.hidden_cells.difference_update(self.coords)

    def is_done(self):
        return self.t >= self.duration


class SyncHand(Animation):
    def __init__(self, fetched, bank=None):
        self.fetched, self.bank, self.done = fetched, bank, False

    def update(self, dt, cfdata):
        cfdata.hand = list(self.fetched)
        if self.bank is not None:
            cfdata.bank = list(self.bank)
        self.done = True

    def is_done(self):
        return self.done


ANIM_BY_EVENT = {
    events.AIMoved: lambda ev, env: Move(ev),
    events.FetchedChanged: lambda ev, env: SyncHand(ev.fetched, ev.bank),
    events.MergingHappened: lambda ev, env: SyncHand(ev.fetched),
}


class AnimationPlayer:
    def __init__(self):
        self.queue: deque[Animation] = deque()
        self.current: Animation | None = None

    def _add(self, a: Animation, cfdata):
        a.on_queued(cfdata)
        self.queue.append(a)

    def push_events(self, evs, env, cfdata):
        batch = []
        move = None
        collapse = None

        def flush():
            if batch:
                self._add(Reveal(list(batch)), cfdata)
                batch.clear()

        for ev in evs:
            if isinstance(ev, events.SMWallCollapsed):
                collapse = ev
                continue

            if isinstance(ev, events.CellChanged):
                if collapse is not None and move is not None:
                    move.attach(collapse.cells, (ev.x, ev.y), cfdata)
                    collapse = None
                batch.append((ev.x, ev.y))
                continue

            flush()
            factory = ANIM_BY_EVENT.get(type(ev))
            if factory:
                anim = factory(ev, env)
                self._add(anim, cfdata)
                if isinstance(anim, Move):
                    move = anim
        flush()

    def update(self, dt, cfdata):
        if self.current is None and self.queue:
            self.current = self.queue.popleft()
            
        if self.current:
            self.current.update(dt, cfdata)
            if self.current.is_done():
                self.current = None
                
        if self.current is None and not self.queue: # idle: the env is the truth again
            cfdata.ai_pos.clear()
            cfdata.hidden_cells.clear()

    def is_done(self) -> bool:
        return self.current is None and not self.queue