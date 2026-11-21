import pygame
from dataclasses import dataclass, field

@dataclass
class Viewport:
    logical_size: tuple[int, int]
    window_size: tuple[int, int]
    scale: float = field(init=False, default=1.0)
    offset: tuple[int, int] = field(init=False, default=(0, 0))
    
    def __post_init__(self):
        self.resize(self.window_size)
        
    def resize(self, window_size: tuple[int, int]):
        self.window_size = window_size
        lw, lh = self.logical_size
        ww, wh = window_size
        self.scale = max(min(ww / lw, wh / lh), 1e-6) # no zero division
        self.offset = ((ww - int(lw * self.scale)) // 2, (wh - int(lh * self.scale)) // 2)
    
    def window_to_logical(self, vector) -> tuple[int, int]:
        return (
            int((vector[0] - self.offset[0]) / self.scale),
            int((vector[1] - self.offset[1]) / self.scale),
        )
    
    def logical_to_window(self, vector) -> tuple[int, int]:
        return (
            int(vector[0] * self.scale + self.offset[0]),
            int(vector[1] * self.scale + self.offset[1]),
        )
        
    def windows_to_logical(self, vectors: list[tuple[int, int]]): return [self.window_to_logical(p) for p in vectors]
    def logicals_to_window(self, vectors: list[tuple[int, int]]): return [self.logical_to_window(p) for p in vectors]
    
    def pgevent_pos_to_logical(self, event: pygame.event.Event):
        if hasattr(event, "pos"):
            return pygame.event.Event(event.type, {**event.dict, "pos": self.window_to_logical(event.pos)})
        return event
    
    def scale_surface(self, surface: pygame.Surface) -> pygame.Surface:
        size = (int(self.logical_size[0] * self.scale), int(self.logical_size[1] * self.scale))
        scaled = surface if size == surface.get_size() else pygame.transform.scale(surface, size)
        return scaled