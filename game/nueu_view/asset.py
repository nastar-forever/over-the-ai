import pygame

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Callable

from . import _base

@dataclass
class SurfacesContainer(_base.PrimitiveRenderer):
    surfaces: list[pygame.Surface]
    size: tuple[int, int]
    filters: list[Callable[[pygame.Surface], None]] = None
    filters_enabled: bool = False
    
    def get(self) -> _base.GetReturn:
        surface = self.surfaces[self.variant]

        if not self.filters_enabled:
            return _base.GetReturn(
                surface, self.size
            )
        
        surf = surface.copy()
        for filter in self.filters:
            filter(surf)
        return _base.GetReturn(surf, self.size)
    
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]):
        ret = self.get()
        parent_surface.blit(ret.surface, ret.construct_rect(origin))


vanilla = lambda surf: surf

@dataclass
class FilterArray:
    surfaces: list[SurfacesContainer]
    mask: list[bool]
    active_filters: list[Callable[[pygame.Surface], None]]
    inactive_filters: list[Callable[[pygame.Surface], None]] = field(default=[vanilla])
    _applied: list[bool] = field(init=False)
    
    def __post_init__(self):
        self._applied = [False] * len(self.surfaces)
        for surf in self.surfaces:
            surf.filters = self.inactive_filters
            surf.filters_enabled = True
    
    def update(self):
        for i, (surf, applied, mask) in enumerate(zip(self.surfaces, self._applied, self.mask)):
            if mask == applied: continue
            self._applied[i] = mask
            surf.filters = self.active_filters if mask else self.inactive_filters 
    
    def get(self) -> list[pygame.Surface]:
        return [surf.get() for surf in self.surfaces]