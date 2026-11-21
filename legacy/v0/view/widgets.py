from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Literal

import pygame

from . import assets
from .theme import Theme

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
    
@dataclass
class CancelRequest(UIToken): pass

@dataclass
class ReplayRequest(UIToken): pass
    

CATEGORY_COLOR = {"placement": (70, 110, 180), "information": (80, 160, 120), "manipulation": (180, 100, 70)}

@dataclass
class RerollRequest(UIToken): pass


class Widget(ABC):
    rect: pygame.Rect
    enabled: bool = True
    
    @abstractmethod
    def handle(self, event: pygame.event.Event) -> UIToken|None: ...
    
    @abstractmethod
    def draw(self, surf: pygame.Surface, assets: assets.Assets): ...


class Button(Widget):
    def __init__(self, rect, text, token):
        self.rect, self.text, self.token, self.hover = pygame.Rect(rect), text, token, False

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
            
        elif (event.type == pygame.MOUSEBUTTONUP and event.button == 1
              and self.enabled and self.rect.collidepoint(event.pos)):
            return self.token

    def draw(self, surf, assets):
        pygame.draw.rect(surf, Theme.BUTTON_HOVER if self.hover else Theme.BUTTON, self.rect, border_radius=6)
        label = assets.text(self.text, assets.font(None, 22), Theme.TEXT)
        surf.blit(label, label.get_rect(center=self.rect.center))


class HandView(Widget):
    def __init__(self, area: pygame.Rect, get_cards, get_active=lambda: None, card_h=56, gap=8):
        self.rect, self.get_cards, self.get_active = area, get_cards, get_active
        self.card_h, self.gap = card_h, gap
        self.hover: int | None = None

    def card_rects(self):
        return [pygame.Rect(self.rect.x, self.rect.y + i * (self.card_h + self.gap), self.rect.w, self.card_h)
                for i in range(len(self.get_cards()))]

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = next((i for i, r in enumerate(self.card_rects()) if r.collidepoint(event.pos)), None)
            
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for i, r in enumerate(self.card_rects()):
                if r.collidepoint(event.pos):
                    return PlayCardRequest(i)


    def draw(self, surf, assets):
        font = assets.font(None, 22)
        active = self.get_active()

        for i, (card, r) in enumerate(zip(self.get_cards(), self.card_rects())):
            if card is active:
                color, text_color = Theme.CARD_ACTIVE, Theme.CARD_ACTIVE_TEXT
            else:
                base = Theme.CARD_COLORS.get(card.card_category, Theme.CARD_DEFAULT)
                color = tuple(min(255, c + Theme.CARD_HOVER_BOOST) for c in base) if i == self.hover else base
                text_color = Theme.TEXT

            pygame.draw.rect(surf, color, r, border_radius=8)
            label = assets.text(type(card).__name__, font, text_color)
            surf.blit(label, label.get_rect(midleft=(r.x + 12, r.centery)))


class PlacementInput(Widget):
    def __init__(self, viewport):
        self.vp = viewport

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            return PlaceRequest(*self.vp.logical_to_cell(event.pos))
        
        if event.type == pygame.KEYDOWN:
            return {
                pygame.K_r: RotateRequest("cw"),
                pygame.K_q: RotateRequest("ccw"),
                pygame.K_f: RotateRequest("flip"),
                pygame.K_ESCAPE: CancelRequest()
            }.get(event.key)

    def draw(self, surf, assets): pass


class TextPanel(Widget):
    def __init__(self, rect, title, rows):
        self.rect, self.title, self.rows = pygame.Rect(rect), title, rows

    def handle(self, event): return None

    def draw(self, surf, assets):
        pygame.draw.rect(surf, Theme.PANEL_BG, self.rect, border_radius=8)
        font = assets.font(None, 20)
        surf.blit(assets.text(self.title, font, Theme.PANEL_TITLE), (self.rect.x + 10, self.rect.y + 8))

        for i, (key, desc) in enumerate(self.rows):
            y = self.rect.y + 32 + i * 20
            surf.blit(assets.text(key, font, Theme.PANEL_KEY), (self.rect.x + 10, y))
            surf.blit(assets.text(desc, font, Theme.PANEL_DESC), (self.rect.x + 104, y))


class CardView(Widget): ...
class Tooltip(Widget): ...

@dataclass
class DragState:
    card: CardView | None = None
    offset: pygame.Vector2 = field(default_factory=pygame.Vector2)