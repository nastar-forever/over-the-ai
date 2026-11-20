import pygame

from typing import Literal
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .import anim
from .import asset
    

@dataclass
class Layout(ABC):
    items: list[asset.SurfacesContainer] = field(init=False, default_factory=list)
    animations: anim.AnimationStack
    
    @property
    @abstractmethod
    def items_limit(self) -> int: ... # -1 or 0 for no limit
    
    
    def cut(self) -> None:
        raise IndexError(f"{len(self.items)} items is beyond the limit ({self.items_limit})")
    
    
    @abstractmethod
    def positions(self) -> list[tuple[int, int]]: ... # RELATIVE POSITION
    
    
    def __call__(self, origin: tuple[int, int], update: bool = False) -> list[tuple[pygame.Surface, tuple[int, int]]]:
        poses = [(pos[i] + origin[i] for i in range(2)) for pos in self.positions()]
        method = self.animations.update if update else self.animations.get
        ctxs = method(origin=origin)
        
        for idx, (pos, ctxframe) in enumerate(zip(poses, ctxs)):
            poses[idx] = ctxframe.position if ctxframe.postype == "absolute" else (pos[i] + ctxframe.position[i] for i in range(2))
        return zip((surf.get() for surf in self.items), poses)
    
    
    def append(self, surfcont: asset.SurfacesContainer):
        self.items.append(surfcont)
        
        if len(self.items) >= self.items_limit and self.items_limit > 0:
            self.cut()


@dataclass
class UniformGridLayout(Layout):
    width: int
    height: int
    rows: int
    columns: int
    
    
    @property
    def items_limit(self):
        return self.rows * self.columns
    
    
    @property
    def _pos_map(self) -> list[tuple, tuple]:
        return [(x, y) for x in range(self.rows) for y in range(self.columns)]
    
    
    def positions(self):
        poses = []
        
        for pos in self._pos_map:
            poses.append((pos[0] * self.width, pos[1] * self.height))
        return poses