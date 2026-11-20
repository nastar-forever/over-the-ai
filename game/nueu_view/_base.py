import pygame

from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class GetReturn:
    surface: pygame.Surface
    size: tuple[int, int]
    
    def construct_rect(self, origin: tuple[int, int]):
        return pygame.Rect(origin[0], origin[1], self.size[0], self.size[1])

class RefObject(ABC):
    @property
    @abstractmethod
    def source(self): ...
    
    def _general_getter(self, attr):
        return getattr(self.source(id(self)), attr)
    def _general_setter(self, attr, val):
        setattr(id(self), attr, val)

class PrimitiveRenderer(ABC):
    @abstractmethod
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]): ...
    @abstractmethod
    def get(self) -> GetReturn: ...