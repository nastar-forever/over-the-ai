import math
import pygame

from typing import Literal, Callable, ClassVar
from abc import ABC, abstractmethod
from dataclasses import dataclass

import assets


@dataclass
class AnimationFrame:
    surface: assets.SurfacesContainer
    postype: Literal["absolute", "relative"] = "relative"
    position: tuple[int, int] = (0, 0)


class Animation(ABC, assets._PrimitiveRenderer):
    @property
    def would_loop(self) -> bool:
        return False
    
    @property
    @abstractmethod
    def is_done(self) -> bool: ...
    
    @abstractmethod
    def update(self, start_time: float, current_time: float, dt: float) -> AnimationFrame: ...
    
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]):
        frame = self.update()
        orig = origin if frame.postype == "relative" else (0, 0)
        pos = (orig[i] + frame.position[i] for i in range(2))
        parent_surface.blit(frame.surface.get(), pos)

class LoopingAnimation(Animation):
    @property
    def would_loop(self) -> bool:
        return True
    
    @property
    def is_done(self) -> bool|None:
        return None

    
@dataclass
class SpriteAnim(LoopingAnimation):
    spritesheet: assets.SurfacesContainer
    frame_duration: float
    since_last: ClassVar[float] = 0
        
    def update(self, start, curr, _):
        if curr - self.since_last >= self.frame_duration:
            self.spritesheet.variant = (self.spritesheet.variant + 1) % self.spritesheet.variants_count
            self.since_last = curr
        
        return AnimationFrame(
            self.spritesheet
        )
        

linear = lambda t: t
ease_out = lambda t: 1 - (1 - t) ** 3


@dataclass
class TweenAnim(Animation):
    sprite: assets.SurfacesContainer
    tween_from: tuple[int, int]
    tween_to: tuple[int, int]
    duration: float
    ease_func: Callable[[float], float] = linear
    
    def update(self, start, curr, _):
        t = min((start - curr) / self.duration, 1)
        lerped = (self.tween_from[i] + (self.tween_to[i] - self.tween_from[i]) * self.ease_func(t) for i in range(2))
        
        return AnimationFrame(
            self.sprite,
            "absolute",
            lerped
        )        

@dataclass
class BlockyTweenAnim(Animation):
    sprite: assets.SurfacesContainer
    tween_from: tuple[int, int]
    tween_to: tuple[int, int]
    duration: float
    block_dim: tuple[int, int]
    
    def update(self, start, curr, _):
        elapsed = curr - start
        t = min(elapsed / self.duration, 1)
        ps = self.tween_from
        pt = self.tween_to
        
        sign = lambda x: (x > 0) - (x < 0)
        
        newpos = (
            sign(pt[i] - ps[i]) + math.floor(abs((pt[i] - ps[i]) * t) / self.block_dim[i])
            for i in range(2)
        )
        
        return AnimationFrame(
            self.sprite,
            "absolute",
            newpos
        )