from typing import Literal, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass

import pygame

import game.environment as environment, game.cells as cells
from . import anim
from . import viewport
from . import assets
from .theme import Theme

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
            pygame.draw.circle(ctx.surf, Theme.AI, center, vp.cell_size // 3)


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
            label = ctx.assets.text(text, font, Theme.LABEL_ACTIVE if wall.active else Theme.LABEL_INACTIVE)

            center = ctx.viewport.cell_to_rect((env.envsize // 2, ring)).center
            box = label.get_rect(center=center).inflate(10, 4)
            bg = pygame.Surface(box.size, pygame.SRCALPHA)
            bg.fill(Theme.LABEL_BG)
            
            ctx.surf.blit(bg, box)
            ctx.surf.blit(label, label.get_rect(center=center))


class VerdictRenderer(Renderer):
    def __init__(self, is_busy: Callable[[], bool]):
        self.is_busy = is_busy

    def draw(self, ctx, env):
        if env.verdict == environment.VERDICT_HOLD or self.is_busy():
            return

        won = env.verdict == environment.VERDICT_WIN
        text, color = ("YOU WON", Theme.WIN) if won else ("YOU LOSE", Theme.LOSE)

        vp = ctx.viewport
        side = vp.cell_size * env.envsize
        area = pygame.Rect(*vp.grid_origin, side, side)

        shade = pygame.Surface(area.size, pygame.SRCALPHA)
        shade.fill(Theme.VERDICT_SHADE)
        ctx.surf.blit(shade, area)

        title = ctx.assets.text(text, ctx.assets.font(None, 96), color)
        sub = ctx.assets.text("Press Replay to restart", ctx.assets.font(None, 24), Theme.TEXT_SOFT)
        ctx.surf.blit(title, title.get_rect(center=area.center))
        ctx.surf.blit(sub, sub.get_rect(center=(area.centerx, area.centery + 60)))


class GhostRenderer(Renderer):
    def draw(self, ctx, env):
        token = env.active_placement
        if token is None:
            return
        
        x, y = ctx.viewport.logical_to_cell(ctx.mouse)
        ok = env.can_place(x, y)
        s = ctx.viewport.cell_size
        tint = pygame.Surface((s, s), pygame.SRCALPHA)
        tint.fill(Theme.GHOST_OK if ok else Theme.GHOST_BAD)
        
        for cx, cy in env.shape_coords(token.shape, x, y):
            if env.coord_in_bounds(cx, cy):
                ctx.surf.blit(tint, ctx.viewport.cell_to_rect((cx, cy)))

class HUDRenderer(Renderer): ...