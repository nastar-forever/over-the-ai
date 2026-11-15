from typing import Literal, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass

import pygame

import environment, cells
from . import viewport, assets, anim

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
        self._shown: dict[tuple[int, int], tuple] = {}

    def invalidate(self):
        self._cache.clear()
        self._shown.clear()

    @staticmethod
    def _visible_sc(cell: cells.Cell) -> cells.SpecialCell | None:
        sc = cell.special_cell
        if sc is None or getattr(sc, "used", False):
            return None
        return sc

    @staticmethod
    def _layers(cell) -> tuple[type, ...]:
        sc = cell.special_cell
        
        if sc is None:
            return ()
        
        if isinstance(sc, cells.SMWallCell):
            child = sc.child
            if child is None or getattr(child, "used", False):
                return (cells.SMWallCell,)
            return (cells.SMWallCell, type(child))
        
        return () if getattr(sc, "used", False) else (type(sc),)

    def _tile(self, layers, state, size):
        key = (layers, state, size)
        tile = self._cache.get(key)
        
        if tile is not None:
            return tile

        tile = self.emptytile.get().copy()
        for t in layers:
            if t in self.sctile:
                tile.blit(self.sctile[t].get(), (0, 0))
        
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
            if (x, y) in hidden:
                layers, state = self._shown.get((x, y), ((), "unexplored"))
        
            else:
                cell = env.coord_to_cell(x, y)
                layers, state = self._layers(cell), cell.state
                self._shown[(x, y)] = (layers, state)
            ctx.surf.blit(self._tile(layers, state, size), ctx.viewport.cell_to_rect((x, y)))
    
    
class AIRenderer(Renderer):
    def draw(self, ctx, env):
        vp = ctx.viewport
        for i, ai in enumerate(env.ais):
            p = ctx.cfdata.ai_pos.get(i) or pygame.Vector2(ai.x, ai.y)
            center = (vp.grid_origin[0] + (p.x + 0.5) * vp.cell_size,
                      vp.grid_origin[1] + (p.y + 0.5) * vp.cell_size)
            pygame.draw.circle(ctx.surf, (240, 80, 80), center, vp.cell_size // 3)


class WallLabelRenderer(Renderer):
    @staticmethod
    def _vuln(cell):
        sc = cell.special_cell
        if isinstance(sc, cells.SMWallCell):
            sc = sc.child
        return sc if isinstance(sc, cells.Vulnerability) else None

    def draw(self, ctx, env):
        font = ctx.assets.font(None, 17)
        for wall in env.sm_walls:
            if wall.collapsed:
                continue
            
            ring = env.coord_to_rlayeridx(*env.cell_to_coord(wall.cells[0]))
            left = sum(1 for c in wall.vuln_cells if (v := self._vuln(c)) and not v.used)
            text = f"L{wall.level} | {wall.exploited}/{wall.min_exploits} | left {left}"
            label = ctx.assets.text(text, font, (255, 255, 255) if wall.active else (150, 150, 160))

            center = ctx.viewport.cell_to_rect((env.envsize // 2, ring)).center
            box = label.get_rect(center=center).inflate(10, 4)
            bg = pygame.Surface(box.size, pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            
            ctx.surf.blit(bg, box)
            ctx.surf.blit(label, label.get_rect(center=center))


class GhostRenderer(Renderer):
    def draw(self, ctx, env):
        token = env.active_placement
        if token is None:
            return
        
        x, y = ctx.viewport.logical_to_cell(ctx.mouse)
        ok = env.can_place(x, y)
        s = ctx.viewport.cell_size
        tint = pygame.Surface((s, s), pygame.SRCALPHA)
        tint.fill((80, 220, 120, 110) if ok else (230, 70, 70, 110))
        
        for cx, cy in env.shape_coords(token.shape, x, y):
            if env.coord_in_bounds(cx, cy):
                ctx.surf.blit(tint, ctx.viewport.cell_to_rect((cx, cy)))

class HUDRenderer(Renderer): ...