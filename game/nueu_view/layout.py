import pygame

import operator
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

    def unchanging(self, type: Literal["positions", "rotations"]): # helper users can use
        return [(0, 0) if type == "positions" else 0 for _ in range(self.items)]

    # User-defined methods
    @property
    @abstractmethod
    def items_limit(self) -> int: ... # -1 or 0 for no limit
    @abstractmethod
    def positions(self) -> list[tuple[int, int]]: ... # RELATIVE POSITION
    @abstractmethod
    def rotations(self) -> list[float]: ...
    
    def cut(self) -> None: # user can define it's own cut behavior
        raise IndexError(f"{len(self.items)} items is beyond the limit ({self.items_limit})")
    
    
    def _resolve(cv: anim.ContextValue, base, combine):
        return cv.value if cv.type == "absolute" else combine(base, cv.value)
    
    def __call__(self, origin, delta: float | None = None) -> list[_LayoutReturn]:
        ctxs = self.animations.get_for(len(self.items), delta)
        out = []
        
        for item, base, base_rot, ctx in zip(self.items, self.positions(), self.rotations(), ctxs):
            pos = self._resolve(ctx.position, tuple(origin[i] + base[i] for i in range(2)), _base.add2)
            angle = self._resolve(ctx.rotation, base_rot, operator.add)
            scale = self._resolve(ctx.scale, 1.0, operator.mul)
            
            gr = item.get()
            if angle or scale != 1.0:
                w, h = gr.size
                surf = pygame.transform.rotozoom(gr.surface, angle, scale)
                pos = surf.get_rect(center=(pos[0] + w / 2, pos[1] + h / 2)).topleft
                gr = _base.GetReturn(surf, surf.get_size())
            out.append(_LayoutReturn(gr, pos))
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