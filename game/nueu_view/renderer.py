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
    surface: pygame.Surface # can be a subsurface to save resources (or normal surface, wtvr the user wants)
    clear_color: tuple[int, ...]|None = None
    
    def __post_init__(self):
        self.refresh()
        
    def refresh(self):
        self._compose(None)
    
    def _compose(self, delta: float|None):
        if self.clear_color is not None:
            self.surface.fill(self.clear_color)
            
        for sl in self.layouts:
            for lr in sl.layout(sl.position, delta):
                self.surface.blit(lr.gr.surface, lr.position)
    
    def get(self) -> _base.GetReturn:
        return _base.GetReturn(self.surface, self.surface.get_size())
    
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]):
        gr = self.get()
        parent_surface.blit(gr.surface, gr.construct_rect(origin))
    

class _RendererSceneObject(_base.RefObject):
    active = property(
        lambda self: self._general_getter("active"),
        lambda self, val: self._general_setter("active", val)
    )
    origin = property(
        lambda self: self._general_getter("origin"),
        lambda self, val: self._general_setter("origin", val)
    )


class TextRenderer(_base.PrimitiveRenderer):
    def __init__(
        self,
        text: str,
        size: int,
        color: tuple[int, int, int] = (255, 255, 255),
        max_width: int | None = None, # None = no wrapping
        font: pygame.font.Font | None = None,
    ):
        self._text = text
        self._max_width = max_width
        self.size = size
        self.color = color
        self._font = font
        self._surface: pygame.Surface | None = None

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self._surface = None

    @property
    def max_width(self) -> int | None:
        return self._max_width

    @max_width.setter
    def max_width(self, value: int | None) -> None:
        if value != self._max_width:
            self._max_width = value
            self._surface = None

    def get(self) -> _base.GetReturn:
        if self._surface is None:
            self._surface = self._font.render(
                self._text, True, self.color,
                wraplength=self._max_width or 0,
            )
        return _base.GetReturn(self._surface, self._surface.get_size())

    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]):
        gr = self.get()
        parent_surface.blit(gr.surface, gr.construct_rect(origin))


@dataclass
class _RendererSceneElement:
    renderer: _base.PrimitiveRenderer
    origin: tuple[int, int] = (0, 0)
    active: bool = False

@dataclass
class Renderer:
    viewport: viewport.Viewport
    bg: tuple[int, int, int] = (0, 0, 0)
    scenes: dict[int, _RendererSceneElement] = field(init=False, default_factory=dict) # active, renderer
    _next_k: int = field(init=False, default=0)
    _surface: pygame.Surface = field(init=False)
    
    def __post_init__(self):
        self._surface = pygame.Surface(self.viewport.logical_size)
    
    def add_scene(
        self,
        renderer: _base.PrimitiveRenderer,
        origin: tuple[int, int],
        active: bool = False
    ) -> _RendererSceneObject:
        key, self._next_k = self._next_k, self._next_k + 1
        self.scenes[key] = _RendererSceneElement(renderer, origin, active)
        return _RendererSceneObject(self, self.scenes, key)
    
    def update(self, delta: float) -> None:
        for scene in self.scenes.values():
            if not scene.active: continue
            scene.renderer.update(delta)
    
    def render(self, window: pygame.Surface) -> None:
        self._surface.fill(self.bg)
        
        for scene in self.scenes.values():
            if not scene.active: continue
            scene.renderer._draw(self._surface, scene.origin)
        window.fill(self.bg)
        window.blit(self.viewport.scale_surface(self._surface), self.viewport.offset)