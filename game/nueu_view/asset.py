import pygame

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Callable

from . import _base

class SurfacesContainer(_base.PrimitiveRenderer):
    def __init__(
        self,
        surfaces: list[pygame.Surface],
        rect: pygame.Rect,
        filters: list[Callable[[pygame.Surface], None]] = None,
        filter_enabled: bool = False
    ):
        self._surfaces = surfaces
        self._filters = filters or []
        self._variant: int = 0
        self._cachestats = {}
        self._cached_surf: pygame.Surface = None
        self._filter_enabled = filter_enabled
        self._rect = rect
    
    def _setattr(self, attrname: str, value):
        setattr(self, attrname, value)
        self._cachestats[attrname] = False
        
    def _cacheupdt(self, cch):
        self._cached_surf = cch
        for key in self._cachestats.keys():
            self._cachestats[key] = True
        return cch
    
    @property
    def variants_count(self) -> int:
        return len(self.surfaces)
    
    @property
    def rect(self): return self._rect
    @rect.setter
    def rect(self, val): self._setattr("_rect", val)
    
    @property
    def surfaces(self): return self._surfaces
    @surfaces.setter
    def surfaces(self, val): self._setattr("_surfaces", val)
        
    @property
    def filters(self): return self._filters
    @filters.setter
    def filters(self, val): self._setattr("_filters", val)
    
    @property
    def variant(self): return self._variant
    @variant.setter
    def variant(self, val): self._setattr("_variant", val)
    
    @property
    def filter_enabled(self): return self._filter_enabled
    @filter_enabled.setter
    def filter_enabled(self, val): self._setattr("_filter_enabled", val)
    
    
    def purge_cache(self):
        self._cached_surf = None
        self._cachestats = {}
    
    def get(self) -> pygame.Surface:
        cached = all([accounted for accounted in self._cachestats.values()] or [False])
        surfaces = self.surfaces[self.variant]
        
        if cached:
            return self._cachestats
        
        if len(self.filters) == 0:
            return self._cacheupdt(surfaces)
        
        surf = surfaces.copy()
        for filter in self.filters:
            filter(surf)
        return self._cacheupdt(surf)
    
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]):
        parent_surface.blit(self.get(), origin)


@dataclass
class FilterArray:
    surfaces: list[SurfacesContainer]
    mask: list[bool]
    active_filters: list[Callable[[pygame.Surface], None]]
    inactive_filters: list[Callable[[pygame.Surface], None]]
    _applied: list[bool] = field(init=False)
    
    def __post_init__(self):
        self._applied = [False] * len(self.surfaces)
    
    def update(self):
        for i, (surf, applied, mask) in enumerate(zip(self.surfaces, self._applied, self.mask)):
            if mask == applied: continue # prevents unnecessary recache
            self._applied[i] = mask
            surf.filters = self.active_filters if mask else self.inactive_filters
    
    def purge_cache(self):
        for surf in self.surfaces:
            surf.purge_cache()    
    
    def get(self) -> list[pygame.Surface]:
        return [surf.get() for surf in self.surfaces]