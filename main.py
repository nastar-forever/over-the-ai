import asyncio
import pygame

import cells, cards
from view.theme import Theme
from environment import Environment
from default_ais import BFSAI
from view import assets
from view.controller import GameController
from view.viewport import Viewport
from view.renderers import RenderContext, GridRenderer, AIRenderer, GhostRenderer, WallLabelRenderer, VerdictRenderer
from view.widgets import (
    HandView, Button, PlacementInput, TextPanel, RerollRequest, EndTurnRequest, ReplayRequest
)

LOGICAL = (960, 640)
POOL = [
    [cards.Stone, 10],
    [cards.Wall, 6],
    [cards.Edge, 3],
    [cards.Lure, 1]
]

def make_env():
    return Environment(15, (1, 3), [BFSAI()], pool=POOL)


def flat(color):
    s = pygame.Surface((32, 32)); s.fill(color)
    return assets.SurfaceContainer(s, [])


def overlay(draw):
    s = pygame.Surface((32, 32), pygame.SRCALPHA); draw(s)
    return assets.SurfaceContainer(s, [])


def draw_wall(s):
    s.fill(Theme.WALL_FILL); pygame.draw.rect(s, Theme.WALL_BORDER, s.get_rect(), 2)


def draw_obstacle(s):
    pygame.draw.rect(s, Theme.OBSTACLE_OUTER, (3, 3, 26, 26), border_radius=4)
    pygame.draw.rect(s, Theme.OBSTACLE_INNER, (6, 6, 20, 20), border_radius=3)


def draw_vuln(s):
    pygame.draw.circle(s, Theme.VULN_OUTER, (16, 16), 11)
    pygame.draw.circle(s, Theme.VULN_INNER, (16, 16), 9)


def draw_sterile(s):
    s.fill(Theme.STERILE_FILL); pygame.draw.rect(s, Theme.STERILE_BORDER, s.get_rect(), 1)


def draw_lure(s):
    pygame.draw.polygon(s, Theme.LURE, [(16, 4), (28, 16), (16, 28), (4, 16)])


def darken(surf): surf.fill(Theme.LOCKED_MULT, special_flags=pygame.BLEND_RGB_MULT)
def dim(surf):    surf.fill(Theme.EXPLORED_MULT, special_flags=pygame.BLEND_RGB_MULT)


CONTROLS = [
    ("Click card", "select / play"), ("Click grid", "place shape"),
    ("R / Q", "rotate cw / ccw"),    ("F", "flip"),
    ("Esc", "cancel placement"),     ("Reroll", "new hand, 1 step"),
    ("End turn", "AI moves now"),    ("Replay", "restart game"),
]


async def main():
    pygame.init()
    window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    logical = pygame.Surface(LOGICAL)
    clock = pygame.time.Clock()

    controller = GameController(make_env)
    vp = Viewport(LOGICAL, 32, (0, 0), window.get_size())
    vp.fit_grid(controller.env.envsize)

    grid = GridRenderer(
        emptytile=flat(Theme.TILE_EMPTY),
        sctile={
            cells.SMWallCell: overlay(draw_wall),
            cells.Obstacle: overlay(draw_obstacle),
            cells.Vulnerability: overlay(draw_vuln),
            cells.VulnerabilitySterileZone: overlay(draw_sterile),
            cells.FakeRewards: overlay(draw_lure),
            cells.Exit: flat(Theme.TILE_EXIT),
        },
        filters={"locked": darken, "explored": dim, "unexplored": lambda s: None},
    )
    
    renderers = [grid, WallLabelRenderer(), AIRenderer(), GhostRenderer(), VerdictRenderer(lambda: controller.busy)]
    ctx = RenderContext(logical, vp, assets.Assets(), controller.cfdata)

    px = vp.grid_origin[0] + vp.cell_size * controller.env.envsize + 16
    pw = LOGICAL[0] - px - 16
    ui = [
        PlacementInput(vp),
        HandView(pygame.Rect(px, 16, pw, 264), lambda: controller.cfdata.hand, lambda: controller.env.active_card),
        Button((px, 292, pw, 36), "Reroll (1 step)", RerollRequest()),
        Button((px, 336, pw, 36), "End turn", EndTurnRequest()),
        Button((px, 380, pw, 36), "Replay", ReplayRequest()),
        TextPanel(pygame.Rect(px, 428, pw, 196), "Controls", CONTROLS),
    ]

    while True:
        dt = clock.tick(60) / 1000
    
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
    
            if event.type == pygame.VIDEORESIZE:
                vp.resize(window.get_size())
            event = vp.convert(event)
    
            for w in ui:
                token = w.handle(event)
    
                if token:
                    controller.apply(token)

        controller.update(dt)
        env = controller.env                      # changes on Replay
        ctx.mouse = vp.window_to_logical(pygame.mouse.get_pos())

        logical.fill(Theme.BG)
    
        for r in renderers:
            r.draw(ctx, env)
    
        for w in ui:
            w.draw(logical, ctx.assets)
    
        vp.present(logical, window)
        pygame.display.flip()
        await asyncio.sleep(0)
asyncio.run(main())