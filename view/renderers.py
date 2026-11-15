from abc import ABC, abstractmethod
from dataclasses import dataclass

import pygame

import environment
import viewport
import assets
import anim

@dataclass
class RenderContext:
    surf: pygame.Surface
    viewport: viewport.Viewport
    assets: assets.Assets
    cfdata: anim.CrossFrameData
    
class Renderer(ABC):
    @abstractmethod
    def draw(self, ctx: RenderContext, env: environment.Environment): ...
    
class GridRenderer(Renderer): ...
class AIRenderer(Renderer): ...
class HUDRenderer(Renderer): ...