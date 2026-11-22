from __future__ import annotations

import pygame

from enum import IntEnum
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
    link: dict[pygame.event.Event, Widget] = field(init=False, default_factory=dict)
    _next_k: int = field(init=False, default=0)
    
    def _link(self, widget: Widget):
        self.link[widget.trigger_pgevent] = widget
    
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
    
    
    def handle(self, pgevent: pygame.event):
        pgevent = self.viewport.pgevent_pos_to_logical(pgevent)
        
        for trigpgevent, widget in self.link.items():
            if isinstance(pgevent, trigpgevent) and widget.enabled:
                self._log_event(widget.handle(pgevent))
    
    
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
    
    @property
    @abstractmethod
    def trigger_pgevent(self) -> pygame.event.Event: ...
    @abstractmethod
    def handle(self, event: pygame.event.Event) -> WidgetEvent: ...