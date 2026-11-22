from __future__ import annotations

import pygame

from typing import Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from . import _base
from . import asset
from . import viewport



class _UIListenerObject(_base.RefObject): pass # Only there for the .remove method


@dataclass
class UI:
    viewport: viewport.Viewport
    inputstack: list[WidgetEvent] = field(init=False, default_factory=list)
    listeners: dict[WidgetEvent, dict[int, Callable[[WidgetEvent], None]]] = field(init=False, default_factory=dict)
    linked: dict[list[pygame.event.Event], Widget] = field(init=False, default_factory=dict)
    _next_k: int = field(init=False, default=0)
    _hovering: list[Widget] = field(init=False, default_factory=list)
    
    def _link(self, widget: Widget):
        self.linked[widget.trigger_pgevent] = widget
    
    def _log_event(self, event: WidgetEvent):
        self.inputstack.append(WidgetEvent)
        if event in self.listeners:
            for listener in self.listeners[event].values(): listener(event)
            
    def add_listener(
        self,
        event: WidgetEvent,
        listener: Callable[[WidgetEvent], None]
    ) -> _UIListenerObject:
        key, self._next_k = self._next_k, self._next_k + 1
        
        if event not in self.listeners:
            self.listeners[event] = {}
        self.listeners[event][key] = listener
        return _UIListenerObject(self, self.listeners[event], key)
    
    
    def drain(self) -> list[WidgetEvent]:
        out = self.inputstack
        self.inputstack = []
        return out
    
    
    def handle(self, pgevent: pygame.event.Event):
        pgevent = self.viewport.pgevent_pos_to_logical(pgevent)
        
        for trigpgevent, widget in self.linked.items():
            if pgevent.type in trigpgevent and widget.enabled:
                self._log_event(widget.handle(pgevent))
            if pgevent.type == pygame.MOUSEMOTION:
                self.handle_mouse(self.viewport.offset)
    
    def handle_mouse(self, origin: tuple[int, int] = (0, 0)):
        lx, ly = self.viewport.window_to_logical(pygame.mouse.get_pos())
        pos = lx - origin[0], ly - origin[1]
        
        for widget in self.linked.values():
            if not widget.enabled: continue
            inside = widget.rect.collidepoint(pos)
            event = None
            
            if inside and widget not in self._hovering:
                self._hovering.append(widget)
                event = widget.on_hover_enter()
                
            elif not inside and widget in self._hovering:
                self._hovering.remove(widget)
                event = widget.on_hover_exit(pos)
                
            if event is not None:
                self._log_event(event)
    
@dataclass
class WidgetEvent: # User can define their own
    source: Widget


@dataclass
class Widget(ABC):
    master: UI
    visual: asset.SurfacesContainer
    rect: pygame.Rect
    enabled: bool = True
    
    def __post_init__(self):
        self.master._link(self)
    
    # OPTIONALS
    def on_hover_enter(self, position: tuple[int, int]) -> WidgetEvent|None: return None
    def on_hover_exit(self, position: tuple[int, int]) -> WidgetEvent|None: return None
    
    @property
    @abstractmethod
    def trigger_pgevent(self) -> list[int]: ...
    @abstractmethod
    def handle(self, event: pygame.event.Event) -> WidgetEvent: ...