import pygame

from dataclasses import dataclass
from abc import ABC, abstractmethod

add2 = lambda a, b: tuple(a[i] + b[i] for i in range(2))

@dataclass
class GetReturn:
    surface: pygame.Surface
    size: tuple[int, int]
    
    def construct_rect(self, origin: tuple[int, int]):
        return pygame.Rect(origin[0], origin[1], self.size[0], self.size[1])

class RefObject:
    def __init__(self, parent, source: dict, key: int):
        self.parent, self.source, self.key = parent, source, key

    def _general_getter(self, attr):
        return getattr(self.source[self.key], attr)
    def _general_setter(self, attr, val):
        setattr(self.source[self.key], attr, val)
    def remove(self): del self.source[self.key]

class PrimitiveRenderer(ABC):
    def update(self, delta: float) -> None: ... # Optional
    
    @abstractmethod
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]): ...
    @abstractmethod
    def get(self) -> GetReturn: ...