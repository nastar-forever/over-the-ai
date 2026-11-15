import pygame
from dataclasses import dataclass

@dataclass
class Viewport:
    logical_size: tuple[int, int]
    cell_size: int
    grid_origin: tuple[int, int]
    window_size: tuple[int, int]
    
    def window_to_logical(self, pos) -> tuple[int, int]: ...
    def logical_to_cell(self, pos) -> tuple[int, int]: ...
    def cell_to_rect(self, pos) -> pygame.rect: ...