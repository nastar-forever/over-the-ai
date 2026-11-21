from __future__ import annotations

import pygame
from dataclasses import dataclass, field

from . import _base
from . import layout
from . import anim
from . import viewport


@dataclass
class SceneLayout:
    position: tuple[int, int]
    layout: layout.Layout

@dataclass
class Scene(_base.PrimitiveRenderer):
    layouts: list[SceneLayout] # pos, layout
    surface: pygame.Surface # can be a subsurface to save resources
    size: tuple[int, int] = field(init=False)
    
    def __post_init__(self):
        self.update_size()
    
    def update_size(self):
        grsxs: list[int] = []
        grsys: list[int] = []
        
        for lay in self.layouts:
            lreturns = lay.layout((0, 0))
            
            for lr in lreturns:
                grsxs.append(lr.gr.size[0])
                grsys.append(lr.gr.size[1])
        self.size = (
            max(grsxs),
            max(grsys)
        )
    
    
    def get(self) -> _base.GetReturn:
        for sl in self.layouts:
            lay, offset = sl.layout, sl.position
            
            for lt in lay(offset):
                self.surface.blit(lt.surf, lt.pos)
        return _base.GetReturn(self.surface, self.size)
    
    
    def _draw(self, parent_surface, origin):
        gr = self.get()
        parent_surface.blit(gr.surface, gr.construct_rect(origin))
    
    

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
    
    def update(self, delta: float) -> anim.AnimationFrameContext:
        return [element.renderer.update(delta) for element in self.scenes.values() if element.active]
    
    def render(self, mainwindow: pygame.Surface) -> None:
        for element in self.scenes.values():
            active, renderer = element.active, element.renderer
            
            if not active:
                continue
            
            gr = renderer.get()
            scaled_surf = self.viewport.scale_surface(gr.surface)
            mainwindow.blit(scaled_surf, self.viewport.offset)