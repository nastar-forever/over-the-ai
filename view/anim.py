from typing import Callable
from collections import deque
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pygame

import events
import environment

def ease_out(t): return 1 - (1 - t) ** 3

@dataclass
class CrossFrameData:
    ai_pos: dict[int, pygame.Vector2] = field(default_factory=dict)
    hidden_cells: set[tuple[int, int]] = field(default_factory=set)   # changes not yet "revealed"
    shake: float = 0.0
    flash: tuple[tuple[int, int, int], float] | None = None

class Animation(ABC):
    @abstractmethod
    def update(self, dt: float, cfdata: CrossFrameData): ...
    
    @abstractmethod
    def is_done(self) -> bool: ...
    
    
@dataclass
class Tween(Animation):
    a: float
    b: float
    duration: float
    ease: Callable[[float], float]
    
    def update(self, dt: float, cfdata: CrossFrameData): ...
    def is_done(self): ...
    
class Move(Animation): ...
class Reveal(Animation): ... # CellChanged
class CollapseAnim(Animation): ...
class Place(Animation): ...

ANIM_BY_EVENT: dict[type[events.GameEvent], Callable[[events.GameEvent, environment.Environment], Animation]] = {...}

class AnimationPlayer:
    queue: deque[Animation]
    current: Animation|None
    def push_events(self, events: events.GameEvent, env: environment.Environment): ...
    def update(self, dt: float, cfdata: CrossFrameData): ...
    def is_done(self) -> bool: ...