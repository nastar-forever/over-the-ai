from typing import ClassVar, Literal
from dataclasses import dataclass, Field
from abc import ABC, abstractmethod

import anim
import asset

@dataclass
class LayoutItemAnimation:
    animation: anim.Animation
    mask: list[bool]

@dataclass
class Layout(ABC, asset._PrimitiveRenderer):
    items: ClassVar[list[asset.SurfacesContainer]] = Field(default_factory=list)
    animations: anim.AnimationStack
    
    @property
    @abstractmethod
    def items_limit(self) -> int: ... # -1 or 0 for no limit
    
    
    def cut(self) -> None:
        raise IndexError(f"{len(self.items)} items is beyond the limit ({self.items_limit})")
    
    
    @abstractmethod
    def positions(self) -> list[tuple[int, int]]: ...
    
    def update_anims(self):
        for anim in self.animations:
            anim.animation.update()
    
    def __call__(self, origin: tuple[int, int], update: bool = False) -> list[tuple[int, int]]:
        
        poses = self.positions()
        offsets = list[tuple[Literal["relative", "absolute"], tuple[int, int]]] = []

        if update:
            self.update_anims()
        
        for item in self.animations:
            if not item.mask
    
    
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
        
        for pos in self._pos_map, self.items:
            poses.append((pos[0] * self.width, pos[1] * self.height))
        return poses