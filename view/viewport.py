import pygame
from dataclasses import dataclass

import pygame
from dataclasses import dataclass, field


@dataclass
class Viewport:
    logical_size: tuple[int, int]
    cell_size: int
    grid_origin: tuple[int, int]
    window_size: tuple[int, int]
    scale: float = field(init=False, default=1.0)
    offset: tuple[int, int] = field(init=False, default=(0, 0))  # letterbox offset, in window px

    def __post_init__(self):
        self.resize(self.window_size)


    def resize(self, window_size: tuple[int, int]): # Call on startup and on every VIDEORESIZE
        self.window_size = window_size
        lw, lh = self.logical_size
        ww, wh = window_size
        self.scale = min(ww / lw, wh / lh)
        self.offset = ((ww - int(lw * self.scale)) // 2, (wh - int(lh * self.scale)) // 2)


    def fit_grid(self, n_cells, margin=16):
        lw, lh = self.logical_size
        self.cell_size = (min(lw, lh) - 2 * margin) // n_cells
        side = self.cell_size * n_cells
        self.grid_origin = (margin, (lh - side) // 2)


    def convert(self, event):
        if hasattr(event, "pos"):
            return pygame.event.Event(event.type, {**event.dict, "pos": self.window_to_logical(event.pos)})
        return event


    def window_to_logical(self, pos) -> tuple[int, int]:
        return (
            int((pos[0] - self.offset[0]) / self.scale),
            int((pos[1] - self.offset[1]) / self.scale),
        )


    def logical_to_cell(self, pos) -> tuple[int, int]:
        return (
            (pos[0] - self.grid_origin[0]) // self.cell_size,
            (pos[1] - self.grid_origin[1]) // self.cell_size,
        )
        

    def cell_to_rect(self, pos) -> pygame.Rect:
        return pygame.Rect(
            self.grid_origin[0] + pos[0] * self.cell_size,
            self.grid_origin[1] + pos[1] * self.cell_size,
            self.cell_size,
            self.cell_size,
        )

    def present(self, logical: pygame.Surface, window: pygame.Surface):
        window.fill((0, 0, 0))
        
        size = (int(self.logical_size[0] * self.scale), int(self.logical_size[1] * self.scale))
        scaled = logical if size == logical.get_size() else pygame.transform.scale(logical, size)
        
        window.blit(scaled, self.offset)