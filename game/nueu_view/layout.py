import pygame

from typing import Literal
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from . import _base
from . import anim
from . import asset


@dataclass
class _LayoutReturn:
    gr: _base.GetReturn
    position: tuple[int, int]

@dataclass
class Layout(ABC):
    animations: anim.ArrayAnimationPlayer
    items: list[asset.SurfacesContainer] = field(default_factory=list)
    
    @property
    @abstractmethod
    def items_limit(self) -> int: ... # -1 or 0 for no limit
    
    
    def cut(self) -> None: # user can define it's own cut behavior
        raise IndexError(f"{len(self.items)} items is beyond the limit ({self.items_limit})")
    
    
    @abstractmethod
    def positions(self) -> list[tuple[int, int]]: ... # RELATIVE POSITION
    
    
    def __call__(self, origin, delta: float | None = None) -> list[_LayoutReturn]:
        ctxs = self.animations.get_for(len(self.items), delta)
        out = []
        
        for item, base, ctx in zip(self.items, self.positions(), ctxs):
            if ctx.variant != -1:
                item.variant = ctx.variant
        
            if ctx.postype == "absolute":
                pos = ctx.position
            else:
                pos = (origin[0] + base[0] + ctx.position[0], origin[1] + base[1] + ctx.position[1])
            out.append(_LayoutReturn(item.get(), pos))    
        return out
    
    def drain(self) -> list[asset.SurfacesContainer]:
        out = self.items
        self.items = []
        return out
    
    def _checklen(self):
        if len(self.items) > self.items_limit and self.items_limit > 0:
            self.cut()
    
    def append(self, surfcont: asset.SurfacesContainer):
        self.items.append(surfcont)
        self._checklen()
    
    def fill(self, surfconts: list[asset.SurfacesContainer]):
        self.items = surfconts
        self._checklen()


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
        return [(x, y) for y in range(self.rows) for x in range(self.columns)]
    
    
    def positions(self):
        poses = []
        
        for pos in self._pos_map:
            poses.append((pos[0] * self.width, pos[1] * self.height))
        return poses