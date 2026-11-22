import pygame

def fillfilter(surf: pygame.Surface, color: tuple[int, int, int, int]):
    surf.fill(color)
    
lighten = lambda surf: fillfilter(surf, [255, 255, 50])
dim = lambda surf: fillfilter(surf, [0, 0, 0, 50])