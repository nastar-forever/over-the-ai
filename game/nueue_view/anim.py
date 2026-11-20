from __future__ import annotations

import math
import pygame

from typing import Literal, Callable, ClassVar
from dataclasses import dataclass, Field
from abc import ABC, abstractmethod

import game.nueue_view.asset as asset


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
    frame_duration: float
    _since_last: ClassVar[float] = 0
    _curr_frame: ClassVar[int] = 0
    
    def update(self, _, curr):
        if curr - self._since_last >= self.frame_duration:
            self._curr_frame = (self._curr_frame + 1) % self.frame_counts
            
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
    sprite: asset.SurfacesContainer
    duration: float
    tween_to: tuple[int, int]
    tween_from: tuple[int, int] = Field(default=(0, 0))
    ease_func: Callable[[float], float] = Field(default=linear)
    postype: Literal["absolute", "relative"] = "relative"
    _lerped = ClassVar[tuple[int, int]] = None
    
    def __post_init__(self):
        self._lerped = self.tween_from
    
    def update(self, start, curr):
        t = min((start - curr) / self.duration, 1)
        self._lerped = (self.tween_from[i] + (self.tween_to[i] - self.tween_from[i]) * self.ease_func(t) for i in range(2))
        
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
        self.starttime = time or pygame.time.get_ticks()
        self.playing = True
    
    @staticmethod
    def fallback() -> _AnimationCtxFrame: return _AnimationCtxFrame()
    def is_done(self) -> bool: ...
    
    def update(self) -> _AnimationCtxFrame: ...
    
    def __call__(self):
        if self.is_done():
            self.stop()
            return self.fallback()
        
        if not self.playing:
            return self.fallback()
        
        ret = self.update()
        return ret
    

    @abstractmethod
    def get(self) -> _AnimationCtxFrame: ...
    
    @abstractmethod
    def reset(self): ...

    def stop(self):
        self.starttime = 0
        self.playing = True
        self.reset()
    

class GeneralAnimationPlayer(_AnimationPlayer):
    def __init__(self, animation: Animation):
        super().__init__()
        self.animation = animation
    
    def is_done(self):
        return self.animation.is_done()
    
    def update(self):
        return self.animation.update(self.starttime, pygame.time.get_ticks())
    
    def reset(self):
        self.animation.reset()
        self.starttime = pygame.time.get_ticks()

    
    
@dataclass
class AnimStackElement:
    parent: AnimationStack
    
    def _general_getter(self, i):
        return self.parent(id(self))[i]
    def _general_setter(self, val, i):
        self.parent[id(self)][i] = val
    
    @property
    def animation(self): return self._general_getter(0)
    @animation.setter
    def animation(self, val): self._general_setter(val, 0)
    
    @property
    def mask(self): return self._general_getter(1)
    @mask.setter
    def mask(self, val): self._general_setter(val, 1)
    
    def play(self):
        self._general_setter(True, 2)
        self._general_setter(pygame.time.get_ticks())
    
    def stop(self):
        self._general_setter(False, 2)
    
    def remove(self):
        del self.parent[id(self)]
        

class AnimationStack(_AnimationPlayer):
    def __init__(self):
        super().__init__()
        self.tokendict: dict[int, tuple[Animation, list[bool]], bool] = {}
    
    def add_stack(self, animation: Animation, mask: list[bool]) -> AnimStackElement:
        token = AnimStackElement(self)
        self.tokendict[id(token)] = [animation, mask, False, 0] # anim, mask, playing, starttime
        return token
    
    
    def fallback(self):
        return [_AnimationCtxFrame for _ in range(len(self.tokendict))]
    
    def is_done(self):
        return all([token[0].is_done() for token in self.tokendict.values()])
    
    def reset(self):
        for token in self.tokendict.values():
            token[0].reset()
        self.starttime = pygame.time.get_ticks()
        
    def update(self, origin: tuple[int, int], postype: Literal["relative", "absolute"] = "absolute"):
        length = len(list(self.tokendict.values())[0][1])
        ctxs = [_AnimationCtxFrame(postype=postype) for _ in range(length)]
        
        for key, (anim, mask, playing, starttime) in self.tokendict.items():
            if not playing:
                continue
            
            if anim.is_done():
                self.tokendict[key][2] = False
                continue
            
            for i, m in enumerate(mask):
                if not m:
                    continue
                
                ctxframe = anim.update(starttime, pygame.time.get_ticks())
                ctxs[i].variant = ctxframe.variant
                ctxs[i].position = ctxframe.position if ctxframe.postype == "absolute" else (
                    ctxframe.position[0] + origin[0],
                    ctxframe.position[1] + origin[1]
                )
        return ctxs
    
    def get(self, origin: tuple[int, int]):
        ctxs = []
        
        for anim, mask, playing, starttime in self.tokendict.values():
            if not playing:
                continue
            
            for m in mask:
                if not m:
                    continue
                
                ctxframe = anim.update(starttime, pygame.time.get_ticks())
                ctxs.append(ctxframe)
        return ctxs