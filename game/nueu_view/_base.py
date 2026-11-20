import pygame
from abc import ABC, abstractmethod

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
    def get(self) -> pygame.Surface: ...