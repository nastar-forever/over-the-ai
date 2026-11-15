from typing import Literal, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass

import pygame

import environment
import cells
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
    

class GridRenderer(Renderer):
    def __init__(
        self,
        emptytile: assets.SurfaceContainer,
        sctile: dict[type[cells.SpecialCell], assets.SurfaceContainer],
        filters: dict[Literal["locked", "explored", "unexplored"], Callable[[pygame.Surface], None]],
    ):
        self.filters = filters
        self.emptytile = emptytile
        self.sctile = sctile
        self._cache: dict[tuple, pygame.Surface] = {}

    def invalidate(self):
        self._cache.clear()

    @staticmethod
    def _visible_sc(cell: cells.Cell) -> cells.SpecialCell | None:
        sc = cell.special_cell
        if sc is None or getattr(sc, "used", False):
            return None
        return sc

    def _tile(self, sc_type: type | None, state: str, size: int) -> pygame.Surface:
        key = (sc_type, state, size)
        tile = self._cache.get(key)
        if tile is not None:
            return tile

        tile = self.emptytile.get().copy()
        if sc_type is not None and sc_type in self.sctile:
            tile.blit(self.sctile[sc_type].get(), (0, 0))

        tile = pygame.transform.scale(tile, (size, size))
        flt = self.filters.get(state)
        if flt is not None:
            flt(tile)

        self._cache[key] = tile
        return tile

    def draw(self, ctx, env):
        size = ctx.viewport.cell_size
        hidden = ctx.cfdata.hidden_cells

        for x, y in env.all_coords():
            cell = env.coord_to_cell(x, y)
            rect = ctx.viewport.cell_to_rect((x, y))

            if (x, y) in hidden:
                # change not revealed yet: show a plain, unexplored, empty tile
                tile = self._tile(None, "unexplored", size)
            else:
                sc = self._visible_sc(cell)
                tile = self._tile(type(sc) if sc else None, cell.state, size)

            ctx.surf.blit(tile, rect)
    
    
class AIRenderer(Renderer):
    def draw(self, ctx, env):
        for i, ai in enumerate(env.ais):
            rect = ctx.viewport.cell_to_rect((ai.x, ai.y))
            pygame.draw.circle(ctx.surf, (240, 80, 80), rect.center, rect.w // 3)
class HUDRenderer(Renderer): ...