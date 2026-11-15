from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Literal

import pygame

from . import assets

@dataclass
class UIToken: pass

@dataclass
class PlayCardRequest(UIToken):
    card_idx: int
    
@dataclass
class MergeRequest(UIToken):
    idle_idx: int
    over_idx: int
    
@dataclass
class PlaceRequest(UIToken):
    x: int
    y: int
    
@dataclass
class RotateRequest(UIToken):
    direction: Literal["cw", "ccw", "flip"]
    
@dataclass
class EndTurnRequest(UIToken): pass

@dataclass
class SceneRequest(UIToken):
    scene: str
    
class Widget(ABC):
    rect: pygame.Rect
    enabled: bool = True
    
    @abstractmethod
    def handle(self, event: pygame.event.Event) -> UIToken|None: ...
    
    @abstractmethod
    def draw(self, surf: pygame.Surface, assets: assets.Assets): ...
    
class Button(Widget): ... # onclick -> UIToken
class CardView(Widget): ...
class HandView(Widget): ... # Contains CardView
class Tooltip(Widget): ...

@dataclass
class DragState:
    card: CardView | None = None
    offset: pygame.Vector2 = field(default_factory=pygame.Vector2)
    
