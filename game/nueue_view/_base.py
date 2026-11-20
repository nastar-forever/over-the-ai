import pygame
from abc import ABC, abstractmethod

class RefObject(ABC):
    @property
    @abstractmethod
    def parent(self): ...
    
    def _general_getter(self, i):
        return self.parent(id(self))[i]
    def _general_setter(self, val, i):
        self.parent[id(self)][i] = val
        

class PrimitiveRenderer(ABC):
    @abstractmethod
    def _draw(self, parent_surface: pygame.Surface, origin: tuple[int, int]): ...
    @abstractmethod
    def get(self) -> pygame.Surface: ...