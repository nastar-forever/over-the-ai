from __future__ import annotations

import pygame
from dataclasses import dataclass, field

from . import _base
from . import layout
from . import asset
from . import viewport


@dataclass
class SceneLayout:
    position: tuple[int, int]
    layout: layout.Layout

@dataclass
class Scene(_base.PrimitiveRenderer):
    layouts: list[SceneLayout] # pos, layout
    surface: pygame.Surface # can be a subsurface to save resources
    
    def get(self):
        for sl in self.layouts:
            lay, offset = sl.layout, sl.position
            
            for lt in lay(offset):
                self.surface.blit(lt.surf, lt.pos)
        return self.surface
    
    
    def _draw(self, parent_surface, origin):
        surf = self.get()
        parent_surface.blit(surf, origin)
    
    

@dataclass
class _RendererSceneObject(_base.RefObject):
    def __init__(self, parent: Renderer):
        self.parent = parent
        self.source = parent.scenes
    
    @property
    def active(self): return self._general_getter("active")
    @active.setter
    def active(self, val): self._general_setter("active", val)

@dataclass
class _RendererSceneElement:
    renderer: _base.PrimitiveRenderer
    active: bool = False

@dataclass
class Renderer:
    viewport: viewport.Viewport
    scenes: dict[int, _RendererSceneElement] = field(init=False, default_factory=[]) # active, renderer
    
    def add_scene(self, renderer: _base.PrimitiveRenderer, active: bool = False) -> _RendererSceneObject:
        token = _RendererSceneObject(self)
        self.scenes[id(token)] = _RendererSceneElement(
            renderer,
            active
        )
        return token
    
    def render(self, mainwindow: pygame.Surface):
        for element in self.scenes.values():
            active, renderer = element.active, element.renderer
            
            if not active:
                continue
            
            scaled = self.viewport.scale_surface(renderer.get())
            mainwindow.blit(scaled, self.viewport.offset)