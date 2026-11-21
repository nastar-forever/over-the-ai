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

def _merge(base: AnimationFrameContext, new: AnimationFrameContext):
    if new.variant != -1:
        base.variant = new.variant
    if new.postype == "absolute":
        base.postype, base.position = "absolute", new.position
    else:
        base.position = tuple(
            base.position[i] + new.position[i]
            for i in range(2)
        )

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
    
    def __post_init__(self):
        if self.frame_duration <= 0 or self.frame_counts <= 0:
            raise ValueError("frame_duration and frame_counts must be > 0")
    
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
    
    def _pos(self):
        t = 1.0 if self.duration <= 0 else min(self._elapsed / self.duration, 1.0)
        e = self.ease_func(t)
        return tuple(round(a + (b - a) * e) for a, b in zip(self.tween_from, self.tween_to))
    
    def update(self, delta):
        self._elapsed += delta
        return self.get()
    
    def get(self):
        return AnimationFrameContext(
            self.postype,
            self._pos()
        )
    
    def get(self):
        return AnimationFrameContext(
            self.postype,
            self._pos()
        )
    
    def is_done(self):
        return self._elapsed >= self.duration
    
    def reset(self):
        self._elapsed = 0


class AnimationQueue:
    def __init__(self, *anims: Animation):
        self.anims: deque[Animation] = deque(anims)
        self._all = anims
    
    def push(self, anim: Animation):
        self.anims.append(anim)
    
    def skip(self):
        self.anims.popleft()
    
    def reset(self):
        for anim in self.anims:
            anim.reset()
        self.anims = deque(self._all)
    
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
    
    def reset(self):
        for anim in self.anims:
            anim.reset()


# class _AnimationPlayer(ABC):
#     def __init__(self):
#         self.starttime = 0
#         self.playing = False
    
#     def play(self, time: float|None):
#         self.starttime = pygame.time.get_ticks() if time is None else time
#         self.playing = True
    
#     @staticmethod
#     def fallback() -> AnimationFrameContext: return AnimationFrameContext()
#     def is_done(self) -> bool: ...
    
#     def update(self, delta: float) -> AnimationFrameContext: ...
    
#     def __call__(self, *args, **kwargs):
#         if self.is_done():
#             self.stop()
#             return self.fallback()
        
#         if not self.playing:
#             return self.fallback()
        
#         ret = self.update(*args, **kwargs)
#         return ret
    

#     @abstractmethod
#     def get(self) -> AnimationFrameContext: ...
    
#     @abstractmethod
#     def reset(self): ...

#     def stop(self):
        # self.starttime = 0
        # self.playing = False
        # self.reset()
    

# class GeneralAnimationPlayer(_AnimationPlayer):
#     def __init__(self, animation: Animation):
#         super().__init__()
#         self.animation = animation
    
#     def is_done(self):
#         return self.animation.is_done()
    
#     def update(self, delta):
#         return self.animation.update(delta)
    
#     def get(self):
#         return self.animation.get()
    
#     def reset(self):
#         self.animation.reset()
#         self.starttime = pygame.time.get_ticks()
    
@dataclass
class _ArrayAnimationPlayerElement:
    animation: Animation
    mask: list[bool]
    playing: bool
    
class _ArrayAnimationPlayerObject(_base.RefObject):
    animation = property(
        lambda self: self._general_getter("animation"),
        lambda self, val: self._general_setter("animation", val)
    )
    mask = property(
        lambda self: self._general_getter("mask"),
        lambda self, val: self._general_setter("mask", val)
    )
    
    def play(self): self._general_setter("playing", True)
    def stop(self): self._general_setter("playing", False)
    def remove(self): del self.source[self.key]

class ArrayAnimationPlayer:
    def __init__(self):
        self.elements: dict[int, _ArrayAnimationPlayerElement] = {}
        self._next_k = 0
        
    def add_animation(self, animation: Animation, mask: list[bool]) -> _ArrayAnimationPlayerObject:
        key, self._next_k = self._next_k, self._next_k + 1
        self.elements[key] = _ArrayAnimationPlayerElement(animation, mask, False)
        return _ArrayAnimationPlayerObject(self, self.elements, mask)
    
    def is_done(self):
        return all(el.animation.is_done() for el in self.elements if el.playing)
    
    def get_for(self, n: int, delta: float|None = None) -> list[AnimationFrameContext]:
        ctxs = [AnimationFrameContext() for _ in range(n)]
        for el in self.elements.values():
            if not el.playing: continue
            
            advance = delta is not None and not el.animation.is_done()
            ctx = el.animation.update(delta) if advance else el.animation.get()
            
            for i, m in enumerate(el.mask):
                if m:
                    _merge(ctxs[i], ctx)
        return ctxs

# class ArrayAnimationPlayer:
#     def __init__(self):
#         super().__init__()
#         self.elements: dict[int, _ArrayAnimationPlayerElement] = {}
#         self._next_k = 0
    
#     def add_animation(self, animation: Animation, mask: list[bool]) -> _ArrayAnimationPlayerObject:
#         key, self._next_k = self._next_k, self._next_k + 1
#         self.elements[key] = _ArrayAnimationPlayerElement(animation, mask, False)
#         return _ArrayAnimationPlayerObject(self, self.elements, key)
    
    
#     def fallback(self):
#         return [AnimationFrameContext() for _ in range(len(self.elements))]
    
#     def is_done(self):
#         return all([token.animation.is_done() for token in self.elements.values() if token.playing])
    
#     def reset(self):
#         for token in self.elements.values():
#             token.animation.reset()
#         self.starttime = pygame.time.get_ticks()
        
#     def update(self, delta, origin: tuple[int, int], postype: Literal["relative", "absolute"] = "absolute"):
#         if not self.elements:
#             return []
        
#         length = len(list(self.elements.values())[0][1])
#         ctxs = [AnimationFrameContext(postype=postype) for _ in range(length)]
        
#         for key, (anim, mask, playing, starttime) in self.elements.items():
#             if not playing:
#                 continue
            
#             if anim.is_done():
#                 self.elements[key].active = False
#                 continue
            
#             ctxframe = anim.update(delta)
            
#             for i, m in enumerate(mask):
#                 if not m:
#                     continue
                
#                 ctxs[i].variant = ctxframe.variant
#                 ctxs[i].position = ctxframe.position if ctxframe.postype == "absolute" else (
#                     ctxframe.position[0] + origin[0],
#                     ctxframe.position[1] + origin[1]
#                 )
#         return ctxs
    
#     def get(self, origin: tuple[int, int], postype: Literal["relative", "absolute"] = "absolute"):
#         ctxs = []
        
#         for element in self.elements.values():
#             if not element.active:
#                 continue
            
#             for m in element.mask:
#                 if not m:
#                     continue
                
#                 ctxframe = element.animation.get()
#                 ctxs.append(AnimationFrameContext(
#                     postype,
#                     ctxframe.position if ctxframe.postype == "absolute" else tuple(ctxframe.position[i] + origin[i] for i in range(2)),
#                     ctxframe.variant
#                 ))
#         return ctxs