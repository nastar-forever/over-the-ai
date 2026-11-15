from __future__ import annotations
import pygame

from typing import Callable, ClassVar, Any
from dataclasses import dataclass

import cells as cells

@dataclass
class SurfaceContainer:
    surface: pygame.Surface
    filters: list[Callable[[pygame.Surface], None]]
    
    def get(self) -> pygame.Surface:
        if len(self.filters) == 0:
            return self.surface
        
        surf = self.surface.copy()
        for filter in self.filters:
            filter(surf)
        return surf
    

class CellStyle(SurfaceContainer):
    def __init__(self, color: tuple[int, int], icon: str|None):
        self.color = color
        self.icon = icon
        self.surface = None

        
CELL_STYLE_BY_TYPE: dict[type[cells.SpecialCell], CellStyle] = {...}
STATE_FILTER: dict[str, Callable[[pygame.Surface]]] = {...}


class Assets:
    def __init__(self):
        self._fonts = {}
        self._images = {}
        self._texts = {}

    def font(self, path, size):
        key = (path, size)
        
        if key not in self._fonts:
            self._fonts[key] = pygame.font.Font(path, size)
        return self._fonts[key]

    def image(self, path):
        if path not in self._images:
            self._images[path] = pygame.image.load(path).convert_alpha()
        return self._images[path]

    def text(self, string, font, color):
        key = (string, id(font), color)
        
        if key not in self._texts:
            self._texts[key] = font.render(string, True, color)
        return self._texts[key]