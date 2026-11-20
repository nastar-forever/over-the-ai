from __future__ import annotations

import pygame
from dataclasses import dataclass, field

from . import _base
from . import layout
from . import asset
from . import viewport


@dataclass
class Scene(_base.PrimitiveRenderer):
    layouts: list[tuple[tuple[int, int], layout.Layout]] # pos, layout
    surface: pygame.Surface # can be a subsurface to save resources
    _cached: bool = field(init=False, default=False)
    
    def __setattr__(self, name, value):
        self._cached = False
        return object().__setattr__(name, value)
    
    def append(self, newlayout: tuple[tuple[int, int], layout.Layout]):
        self.layouts.append(newlayout)
        self.purge_cache()
    
    def purge_cache(self):
        self._cached = False
    
    def get(self):
        if self._cached:
            return self.surface
        
        for offset, layout in self.layouts:
            for surf, pos in layout(offset):
                self.surface.blit(surf, pos)
        self._cached = True
        return self.surface
    
    
    def _draw(self, parent_surface, origin):
        surf = self.get()
        parent_surface.blit(surf, origin)
    

@dataclass
class _RendererSceneObject(_base.RefObject):
    parent: Renderer
    
    @property
    def active(self): return self._general_getter(0)
    @active.setter
    def active(self, val): self._general_setter(val, 0)


@dataclass
class Renderer:
    viewport: viewport.Viewport
    scenes: dict[int, list[tuple[bool, _base.PrimitiveRenderer]]] = field(init=None) # active, renderer
    
    def add_scene(self, scene: _base.PrimitiveRenderer, active: bool = False) -> _RendererSceneObject:
        token = _RendererSceneObject(self)
        self.scenes[id(token)] = (active, scene)
        return token
    
    def render(self, mainwindow: pygame.Surface):
        for active, renderer in self.scenes.values():
            if not active:
                continue
            
            scaled = self.viewport.scale(renderer.get())
            mainwindow.blit(scaled)