import pygame

from typing import Callable
from abc import ABC, abstractmethod

class _PrimitiveRenderer(ABC):
    @abstractmethod
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]): ...
    

class SurfacesContainer(_PrimitiveRenderer):
    def __init__(
        self,
        surfaces: list[pygame.Surface],
        filters: list[Callable[[pygame.Surface], None]],
        filter_enabled: bool = False
    ):
        self._surfaces = surfaces
        self._filters = filters
        self._variant: int = 0
        self._cachestats = {}
        self._cached_surf: pygame.Surface = None
        self._filter_enabled = filter_enabled
    
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
    def filter_enabled(self): return self._variant
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