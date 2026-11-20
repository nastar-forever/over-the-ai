from __future__ import annotations

import math
import pygame

from typing import Literal, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from . import _base
from . import asset


@dataclass
class _AnimationCtxFrame:
    postype: Literal["absolute", "relative"] = "relative"
    position: tuple[int, int] = (0, 0)
    variant: int = -1 # -1 means don't change
    
class Animation(ABC):
    @property
    def would_loop(self) -> bool:
        return False
    
    @abstractmethod
    def update(self, start: float, curr: float) -> _AnimationCtxFrame: ...
    @abstractmethod
    def get(self) -> _AnimationCtxFrame: ...
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
    _since_last: float = field(init=False, default=0)
    _curr_frame: int = field(init=False, default=0)
    
    def update(self, _, curr):
        if self._since_last <= 0: # Prevents first-update bug
            self._since_last = curr
            return _AnimationCtxFrame(variant=self._curr_frame)
        
        if curr - self._since_last >= self.frame_duration:
            self._curr_frame = (self._curr_frame + 1) % self.frame_counts
            
        self._since_last = curr
        return _AnimationCtxFrame(variant=self._curr_frame)
    
    def get(self):
        return _AnimationCtxFrame(variant=self._curr_frame)
    
    def reset(self):
        self._curr_frame = 0
        self._since_last = 0    
    

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
    
    def __post_init__(self):
        self._lerped = self.tween_from
    
    def is_done(self):
        return self._lerped == self.tween_to
    
    def update(self, start, curr):
        t = min((curr - start) / self.duration, 1)
        self._lerped = tuple(self.tween_from[i] + (self.tween_to[i] - self.tween_from[i]) * self.ease_func(t) for i in range(2))
        
        return _AnimationCtxFrame(
            self.postype,
            self._lerped
        )
    
    def get(self):
        return _AnimationCtxFrame(self.postype, self._lerped)
    
    def reset(self):
        self._lerped = self.tween_from


class _AnimationPlayer(ABC):
    def __init__(self):
        self.starttime = 0
        self.playing = False
    
    def play(self, time: float|None):
        self.starttime = pygame.time.get_ticks() if time is None else time
        self.playing = True
    
    @staticmethod
    def fallback() -> _AnimationCtxFrame: return _AnimationCtxFrame()
    def is_done(self) -> bool: ...
    
    def update(self) -> _AnimationCtxFrame: ...
    
    def __call__(self, *args, **kwargs):
        if self.is_done():
            self.stop()
            return self.fallback()
        
        if not self.playing:
            return self.fallback()
        
        ret = self.update(*args, **kwargs)
        return ret
    

    @abstractmethod
    def get(self) -> _AnimationCtxFrame: ...
    
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
    
    def update(self):
        return self.animation.update(self.starttime, pygame.time.get_ticks())
    
    def get(self):
        return self.animation.get()
    
    def reset(self):
        self.animation.reset()
        self.starttime = pygame.time.get_ticks()

    
class _AnimStackObject(_base.RefObject):
    def __init__(self, parent: AnimationStack):
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
        

@dataclass
class _AnimationStackElement:
    animation: Animation
    mask: list[bool]
    active: bool
    starttime: int

class AnimationStack(_AnimationPlayer):
    def __init__(self):
        super().__init__()
        self.tokendict: dict[int, _AnimationStackElement] = {}
    
    def add_stack(self, animation: Animation, mask: list[bool]) -> _AnimStackObject:
        token = _AnimStackObject(self)
        self.tokendict[id(token)] = _AnimationStackElement(animation, mask, False, 0)
        return token
    
    
    def fallback(self):
        return [_AnimationCtxFrame() for _ in range(len(self.tokendict))]
    
    def is_done(self):
        return all([token.animation.is_done() for token in self.tokendict.values()])
    
    def reset(self):
        for token in self.tokendict.values():
            token.animation.reset()
        self.starttime = pygame.time.get_ticks()
        
    def update(self, origin: tuple[int, int], postype: Literal["relative", "absolute"] = "absolute"):
        if not self.tokendict:
            return []
        
        length = len(list(self.tokendict.values())[0][1])
        ctxs = [_AnimationCtxFrame(postype=postype) for _ in range(length)]
        
        for key, (anim, mask, playing, starttime) in self.tokendict.items():
            if not playing:
                continue
            
            if anim.is_done():
                self.tokendict[key].active = False
                continue
            
            ctxframe = anim.update(starttime, pygame.time.get_ticks())
            
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
                
                ctxframe = element.animation.get(element.starttime, pygame.time.get_ticks())
                ctxs.append(_AnimationCtxFrame(
                    postype,
                    ctxframe.position if ctxframe.postype == "absolute" else tuple(ctxframe.position[i] + origin[i] for i in range(2)),
                    ctxframe.variant
                ))
        return ctxs