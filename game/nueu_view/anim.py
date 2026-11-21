from __future__ import annotations

import math
import pygame

from dataclasses import dataclass, field
from typing import Literal, Callable
from abc import ABC, abstractmethod
from collections import deque

from . import _base
from . import asset


@dataclass
class AnimationFrameContext:
    postype: Literal["absolute", "relative"] = "relative"
    position: tuple[int, int] = (0, 0)
    variant: int = -1 # -1 means don't change

class Animation(ABC):
    @property
    def would_loop(self) -> bool:
        return False
    
    @abstractmethod
    def update(self, delta: float) -> AnimationFrameContext: ...
    @abstractmethod
    def get(self) -> AnimationFrameContext: ...
    @abstractmethod
    def is_done(self) -> bool: ...
    @abstractmethod
    def reset(self) -> None: ...

class LoopingAnimation(Animation):
    @property
    def would_loop(self):
        return True
    
    def is_done(self):
        return False
    
    
@dataclass
class SpriteAnim(LoopingAnimation):
    frame_counts: int
    frame_duration: float # float
    _elapsed: float = field(init=False, default=0)
    _curr_frame: int = field(init=False, default=0)
    
    def update(self, delta):
        self._elapsed += delta
        while self._elapsed >= self.frame_duration:
            self._elapsed -= self.frame_duration
            self._curr_frame = (self._curr_frame + 1) % self.frame_counts
            
        return AnimationFrameContext(variant=self._curr_frame)

    
    def get(self):
        return AnimationFrameContext(variant=self._curr_frame)
    
    def reset(self):
        self._curr_frame = 0
        self._elapsed = 0
    

linear = lambda t: t
ease_out = lambda t: 1 - (1 - t) ** 3

@dataclass
class TweenAnim(Animation):
    duration: float # ms
    tween_to: tuple[int, int]
    tween_from: tuple[int, int] = field(default_factory=lambda: (0, 0))
    ease_func: Callable[[float], float] = field(default=linear)
    postype: Literal["absolute", "relative"] = "relative"
    _lerped: tuple[int, int] = field(init=False)
    _elapsed: float = field(init=False, default=0)
    
    def __post_init__(self):
        self._elapsed >= self.duration
    
    def is_done(self):
        return self._lerped == self.tween_to
    
    def update(self, start, curr):
        t = min(self._elapsed / self.duration, 1)
        self._lerped = tuple(self.tween_from[i] + (self.tween_to[i] - self.tween_from[i]) * self.ease_func(t) for i in range(2))
        
        return AnimationFrameContext(
            self.postype,
            self._lerped
        )
    
    def get(self):
        return AnimationFrameContext(self.postype, self._lerped)
    
    def reset(self):
        self._lerped = self.tween_from
        self._elapsed = 0


class AnimationQueue:
    def __init__(self, *anims: Animation):
        self.anims: deque[Animation] = deque(anims)
    
    def push(self, anim: Animation):
        self.anims.append(anim)
    
    def skip(self):
        self.anims.popleft()
    
    def update(self, delta):
        self.anims[0].update(delta)
        if self.anims[0].is_done():
            self.anims.popleft()
    
    def is_done(self):
        return not self.anims

class AnimationParallel:
    def __init__(self, *anims: Animation):
        self.anims: list[Animation] = list(anims)
    
    def skip(self):
        self.anims.clear()
    
    def update(self, delta):
        for anim in self.anims:
            if not anim.is_done():
                anim.update(delta)
    
    def is_done(self):
        return all(anim.is_done() for anim in self.anims)


class _AnimationPlayer(ABC):
    def __init__(self):
        self.starttime = 0
        self.playing = False
    
    def play(self, time: float|None):
        self.starttime = pygame.time.get_ticks() if time is None else time
        self.playing = True
    
    @staticmethod
    def fallback() -> AnimationFrameContext: return AnimationFrameContext()
    def is_done(self) -> bool: ...
    
    def update(self, delta: float) -> AnimationFrameContext: ...
    
    def __call__(self, *args, **kwargs):
        if self.is_done():
            self.stop()
            return self.fallback()
        
        if not self.playing:
            return self.fallback()
        
        ret = self.update(*args, **kwargs)
        return ret
    

    @abstractmethod
    def get(self) -> AnimationFrameContext: ...
    
    @abstractmethod
    def reset(self): ...

    def stop(self):
        self.starttime = 0
        self.playing = False
        self.reset()
    

class GeneralAnimationPlayer(_AnimationPlayer):
    def __init__(self, animation: Animation):
        super().__init__()
        self.animation = animation
    
    def is_done(self):
        return self.animation.is_done()
    
    def update(self, delta):
        return self.animation.update(delta)
    
    def get(self):
        return self.animation.get()
    
    def reset(self):
        self.animation.reset()
        self.starttime = pygame.time.get_ticks()
    
@dataclass
class _ArrayAnimationPlayerElement:
    animation: Animation
    mask: list[bool]
    active: bool
    starttime: int
    
class _ArrayAnimationPlayerObject(_base.RefObject):
    def __init__(self, parent: ArrayAnimationPlayer):
        self.parent = parent
        self.source = parent.tokendict
    
    @property
    def animation(self): return self._general_getter("animation")
    @animation.setter
    def animation(self, val): self._general_setter("animation", val)
    
    @property
    def mask(self): return self._general_getter("mask")
    @mask.setter
    def mask(self, val): self._general_setter("mask", val)
    
    def play(self):
        self._general_setter("active", True)
        self._general_setter("starttime", pygame.time.get_ticks())
    
    def stop(self):
        self._general_setter("active", False)
        self._general_setter("starttime", 0)
    
    def remove(self):
        del self.source[id(self)]

class ArrayAnimationPlayer(_AnimationPlayer):
    def __init__(self):
        super().__init__()
        self.tokendict: dict[int, _ArrayAnimationPlayerElement] = {}
    
    def add_animation(self, animation: Animation, mask: list[bool]) -> _ArrayAnimationPlayerObject:
        token = _ArrayAnimationPlayerObject(self)
        self.tokendict[id(token)] = _ArrayAnimationPlayerElement(animation, mask, False, 0)
        return token
    
    
    def fallback(self):
        return [AnimationFrameContext() for _ in range(len(self.tokendict))]
    
    def is_done(self):
        return all([token.animation.is_done() for token in self.tokendict.values()])
    
    def reset(self):
        for token in self.tokendict.values():
            token.animation.reset()
        self.starttime = pygame.time.get_ticks()
        
    def update(self, delta, origin: tuple[int, int], postype: Literal["relative", "absolute"] = "absolute"):
        if not self.tokendict:
            return []
        
        length = len(list(self.tokendict.values())[0][1])
        ctxs = [AnimationFrameContext(postype=postype) for _ in range(length)]
        
        for key, (anim, mask, playing, starttime) in self.tokendict.items():
            if not playing:
                continue
            
            if anim.is_done():
                self.tokendict[key].active = False
                continue
            
            ctxframe = anim.update(delta)
            
            for i, m in enumerate(mask):
                if not m:
                    continue
                
                ctxs[i].variant = ctxframe.variant
                ctxs[i].position = ctxframe.position if ctxframe.postype == "absolute" else (
                    ctxframe.position[0] + origin[0],
                    ctxframe.position[1] + origin[1]
                )
        return ctxs
    
    def get(self, origin: tuple[int, int], postype: Literal["relative", "absolute"] = "absolute"):
        ctxs = []
        
        for element in self.tokendict.values():
            if not element.active:
                continue
            
            for m in element.mask:
                if not m:
                    continue
                
                ctxframe = element.animation.get()
                ctxs.append(AnimationFrameContext(
                    postype,
                    ctxframe.position if ctxframe.postype == "absolute" else tuple(ctxframe.position[i] + origin[i] for i in range(2)),
                    ctxframe.variant
                ))
        return ctxs