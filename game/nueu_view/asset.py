import pygame

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Callable

from . import _base

@dataclass(eq=False)
class SurfacesContainer(_base.PrimitiveRenderer):
    surfaces: list[pygame.Surface]
    size: tuple[int, int]
    filters: list[Callable[[pygame.Surface], None]] = None
    filters_enabled: bool = False
    variant: int = 0
    
    def __post_init__(self):
        self.surfaces = [
            s if s.get_size() == self.size else pygame.transform.scale(s, self.size)
            for s in  self.surfaces
        ]
    
    def get(self) -> _base.GetReturn:
        surf = self.surfaces[self.variant]
        
        if self.filters_enabled and self.filters:
            surf = surf.copy()
            for filter in self.filters:
                filter(surf)
        return _base.GetReturn(surf, self.size)
    
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]):
        ret = self.get()
        parent_surface.blit(ret.surface, ret.construct_rect(origin))

@dataclass
class FilterArray:
    surfaces: list[SurfacesContainer]
    mask: list[bool]
    active_filters: list[Callable[[pygame.Surface], None]]
    inactive_filters: list[Callable[[pygame.Surface], None]] = field(default_factory=list)
    _applied: list[bool] = field(init=False)
    
    def __post_init__(self):
        self._applied = [None] * len(self.surfaces)
        self.update()
    
    def update(self):
        for i, (surf, mask) in enumerate(zip(self.surfaces, self.mask)):
            if self._applied[i] == mask:
                continue
            self._applied[i] = mask
            surf.filters = self.active_filters if mask else self.inactive_filters
            surf.filters_enabled = bool(surf.filters)
    
    def get(self) -> list[pygame.Surface]:
        return [surf.get() for surf in self.surfaces]