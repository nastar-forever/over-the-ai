import asyncio
import pygame

import cells, cards
from environment import Environment
from default_ais import BFSAI
from view import assets
from view.controller import GameController
from view.viewport import Viewport
from view.renderers import RenderContext, GridRenderer, AIRenderer, GhostRenderer, WallLabelRenderer
from view.widgets import (
    HandView, Button, PlacementInput, TextPanel, RerollRequest, EndTurnRequest, ReplayRequest
)

LOGICAL = (960, 640)
POOL = [
    [cards.Stone, 10],
    [cards.Wall, 6],
    [cards.Edge, 3],
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
    s.fill((135, 135, 160)); pygame.draw.rect(s, (95, 95, 120), s.get_rect(), 2)


def draw_obstacle(s):       # user-placed block: bright border so it reads over an SM wall
    pygame.draw.rect(s, (235, 235, 245), (3, 3, 26, 26), border_radius=4)
    pygame.draw.rect(s, (25, 25, 32), (6, 6, 20, 20), border_radius=3)


def draw_vuln(s):
    pygame.draw.circle(s, (255, 255, 255), (16, 16), 11)
    pygame.draw.circle(s, (235, 140, 30), (16, 16), 9)


def draw_sterile(s):
    s.fill((90, 200, 255, 55)); pygame.draw.rect(s, (90, 200, 255, 130), s.get_rect(), 1)


def draw_lure(s):
    pygame.draw.polygon(s, (210, 80, 210), [(16, 4), (28, 16), (16, 28), (4, 16)])


def darken(surf): surf.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
def dim(surf):    surf.fill((180, 180, 180), special_flags=pygame.BLEND_RGB_MULT)


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
        emptytile=flat((50, 55, 70)),
        sctile={
            cells.SMWallCell: overlay(draw_wall),
            cells.Obstacle: overlay(draw_obstacle),
            cells.Vulnerability: overlay(draw_vuln),
            cells.VulnerabilitySterileZone: overlay(draw_sterile),
            cells.FakeRewards: overlay(draw_lure),
            cells.Exit: flat((60, 200, 90)),
        },
        filters={"locked": darken, "explored": dim, "unexplored": lambda s: None},
    )
    
    renderers = [grid, WallLabelRenderer(), AIRenderer(), GhostRenderer()]
    ctx = RenderContext(logical, vp, assets.Assets(), controller.cfdata)

    px = vp.grid_origin[0] + vp.cell_size * controller.env.envsize + 16
    pw = LOGICAL[0] - px - 16
    ui = [
        PlacementInput(vp),
        HandView(pygame.Rect(px, 16, pw, 264), lambda: controller.cfdata.hand),
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

        logical.fill((20, 20, 28))
    
        for r in renderers:
            r.draw(ctx, env)
    
        for w in ui:
            w.draw(logical, ctx.assets)
    
        vp.present(logical, window)
        pygame.display.flip()
        await asyncio.sleep(0)
asyncio.run(main())