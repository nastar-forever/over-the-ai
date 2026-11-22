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
class Layout(_base.PrimitiveRenderer, ABC):
    animations: anim.ArrayAnimationPlayer
    items: list = field(default_factory=list, kw_only=True)
    _delta: float|None = field(init=False, default=None, repr=False)
    _surface: pygame.Surface|None = field(init=False, default=None, repr=False)

    def unchanging(self, type: Literal["positions", "rotations"]): # helper users can use
        return [(0, 0) if type == "positions" else 0 for _ in range(len(self.items))]

    # User-defined methods
    @property
    @abstractmethod
    def items_limit(self) -> int: ... # -1 or 0 for no limit
    @property
    @abstractmethod
    def size(self) -> tuple[int, int]: ...
    @abstractmethod
    def positions(self) -> list[tuple[int, int]]: ... # RELATIVE POSITION
    @abstractmethod
    def rotations(self) -> list[float]: ...
    
    def cut(self) -> None: # user can define it's own cut behavior
        raise IndexError(f"{len(self.items)} items is beyond the limit ({self.items_limit})")
    
    
    def _resolve(self, cv: anim.ContextValue, base, combine):
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
            
    
    def drain(self) -> list[_base.PrimitiveRenderer]:
        out = self.items
        self.items = []
        return out
    
    def _checklen(self):
        if len(self.items) > self.items_limit and self.items_limit > 0:
            self.cut()
    
    def append(self, surfcont: _base.PrimitiveRenderer):
        self.items.append(surfcont)
        self._checklen()
    
    def fill(self, surfconts: list[_base.PrimitiveRenderer]):
        self.items = surfconts
        self._checklen()
        
    def update(self, delta: float) -> None:
        for item in self.items:
            item.update(delta)
        self._delta = delta
    
    def get(self) -> _base.GetReturn:
        size = self.size
        
        if self._surface is None or self._surface.get_size() != size: # already check size changes
            self._surface = pygame.Surface(size, pygame.SRCALPHA)
        else:
            self._surface.fill((0, 0, 0, 0))

        for lr in self((0, 0), self._delta):
            self._surface.blit(lr.gr.surface, lr.position)
        
        self._delta = None
        return _base.GetReturn(self._surface, size)

    def _draw(self, parent_surface, origin):
        gr = self.get()
        parent_surface.blit(gr.surface, gr.construct_rect(origin))
        

@dataclass
class UniformGridLayout(Layout):
    # def __init__(
    #     self,
    #     width: int,
    #     height: int,
    #     rows: int,
    #     columns: int,
    #     animations: anim.ArrayAnimationPlayer,
    #     items: list[_base.PrimitiveRenderer]|None = None
    # ):
    #     self.width = width
    #     self.height = height
    #     self.rows = rows
    #     self.columns = columns
    #     super().__init__(animations, [] if items is None else items)
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
    
    @property
    def size(self):
        return (self.width * self.columns, self.height * self.rows)
    
    def positions(self):
        poses = []
        
        for pos in self._pos_map:
            poses.append((pos[0] * self.width, pos[1] * self.height))
        return poses
    
    def rotations(self):
        return self.unchanging("rotations")


@dataclass
class RowLayout(Layout):
    items_limit: int = -1
    
    def cut(self):
        self.items = self.items[self.items_limit:]
        
    def positions(self):
        out = []
        lastx = 0
        
        for item in self.items:
            size = item.get().size
            
            newx = lastx + size[0] + (self.gap if lastx else 0)
            out.append((newx, 0))
            lastx = newx
        return out
    
    def rotations(self):
        return self.unchanging("rotations")
    
    def size(self):
        return max([pos[0] for pos in self.positions()]) + self.items[-1].get().size[0]
    

@dataclass
class UniformRowLayout(Layout):
    width: int
    height: int
    gap: int
    items_limit: int = -1
    # def __init__(
    #     self,
    #     width: int,
    #     height: int,
    #     gap: int,
    #     animations: anim.ArrayAnimationPlayer,
    #     items_limit: int = -1,
    #     items: list|None = None
    # ):
    #     self.width = width
    #     self.height = height
    #     self.gap = gap
    #     self.items_limit = items_limit
    #     super().__init__(animations, [] if items is None else items)
    
    def cut(self):
        self.items = self.items[self.items_limit:]
    
    def positions(self):
        return [(i*self.gap + i*self.width , 0) for i in range(len(self.items))]
    
    def rotations(self):
        return self.unchanging("rotations")
    
    @property
    def size(self):
        n = len(self.items)
        return (n * self.width + max(n - 1, 0) * self.gap, self.height)
    
    
@dataclass
class UniformColumnLayout(Layout):
    width: int
    height: int
    gap: int
    items_limit: int = -1
    # def __init__(
    #     self,
    #     width: int,
    #     height: int,
    #     gap: int,
    #     animations: anim.ArrayAnimationPlayer,
    #     items_limit: int = -1,
    #     items: list|None = None
    # ):
    #     self.width = width
    #     self.height = height
    #     self.gap = gap
    #     self.items_limit = items_limit
    #     super().__init__(animations, [] if items is None else items)

    def cut(self):
        self.items = self.items[self.items_limit:]    

    def positions(self):
        return [(0, i*self.gap+ i*self.height) for i in range(len(self.items))]
    
    def rotations(self):
        return self.unchanging("rotations")
    
    @property
    def size(self) -> tuple[int, int]:
        n = len(self.items)
        return (self.width, n * self.height + max(n - 1, 0) * self.gap)