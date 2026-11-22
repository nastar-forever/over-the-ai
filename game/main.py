import sys
import os
import asyncio
from types import SimpleNamespace

import pygame
pygame.init()

import cards
from environment import Environment
from default_ais import BFSAI
from nueu_view import viewport as vpmod
from gameview import theme
from gameview.screen import GameScreen

GRIDSIZE = 15

# Ring indices of the SM Walls (0 = exit ring). Innermost ring must be <= 3 on a 15x15 grid,
# otherwise there's no room for 3-5 flaws with sterile zones. More walls => bigger GRIDSIZE.
WALL_RINGS = (1, 2, 3)
POOL = [[cards.Stone, 10], [cards.Wall, 6], [cards.Edge, 3], [cards.Lure, 1]]

LOGICAL_SIZE = (1920, 1080)
WINDOW_SIZE = (1280, 720)
FPS = 60
COLOR_BG = (0, 0, 0)

def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)

ASSETS = resource_path("assets")
FONT_PATH = os.path.join(ASSETS, "fonts", "IBM Plex Mono", "IBMPlexMono-Regular.ttf")
CARDS_DIR = os.path.join(ASSETS, "cards")
TILES_DIR = os.path.join(ASSETS, "spritesheets", "tiles")
OMI_DIR = os.path.join(ASSETS, "spritesheets", "omi")

OMI_FPS = 6
TILE_FPS = 2
AI_STEP_DELAY = 0.8
WALK_STEP_TIME = 0.12
DASH_STEP_TIME = 0.03
WIN_DELAY = 0.9
PANIC_STEPS = 40
PANIC_STEP_TIME = 0.06

POS_INS_TTL = (154, 129)
POS_INS_TXT = (154, 152)
POS_LOG_TTL = (154, 849)
POS_LOG_TXT = (154, 877)
POS_SMWSTAT_TTL = (975, 108)
POS_SMWSTAT_LAY = (975, 132)
POS_FETCHED_TTL = (975, 263)
POS_BANK_TTL = (975, 613)
POS_BANK_TTL_BIG = (975, 670)
POS_GRID_LAY = (204, 220)
POS_SHUFFLE = (1740, 252)

POS_FETCHED_CARDS = (975, 311)
POS_BANK_CARDS = (975, 731)
RECT_ARROW_L = (925, 324, 38, 269)
RECT_ARROW_R = (1824, 324, 38, 269)
RECT_BANK = pygame.Rect(947, 645, 887, 395)

MAX_TWIDTH_FULL = 676
CELL_DIM = 38

LOG_WIDTH = 700
STATUS_COLS = 2

CARD_W, CARD_H, CARD_GAP = 192, 269, 23
CARD_BEND = 3
CARD_JUMP = 15
VISIBLE_CARDS = 4
SCROLL_INTERVAL = 0.25
DRAG_THRESHOLD = 8

STATUS_ROWS = 3
STATUS_COL_W = 402
STATUS_ROW_H = 38
STATUS_FMT = "LVL {level} [{status:<8}] ({exploited}/{needed})"

FONT_S_DETAIL = theme.FONT_S_DETAIL
FONT_S_NORMAL = theme.FONT_S_NORMAL
FONT_DETAIL_HEIGHT = theme.FONT_DETAIL_HEIGHT
COLOR_GOOD = theme.COLOR_GOOD
COLOR_DANGER = theme.COLOR_DANGER
COLOR_REGULAR = theme.COLOR_REGULAR
SHUFFLE_COLOR = (210, 210, 210)
SHUFFLE_HOVER = (255, 255, 255)
LOCKED_MULT = (150, 150, 150)
EXPLORED_MULT = (180, 180, 180)
GHOST_OK = (80, 220, 120, 110)
GHOST_BAD = (230, 70, 70, 110)


TEXT_INST_TTL = "$ cat env/running/entity/GABE/inst.txt"
TEXT_INST = "MALICIOUS INTENT DETECTED, COMMENCE ISOLATION PROTOCOL. DON'T LET THEM OUT."
TEXT_LOG_TTL = "$ cat env/log.txt"
TEXT_SMSTAT_TTL = "$ env status --general -v"
TEXT_FETCHED_TTL = "$ env/action/fetched.sh"
TEXT_BANK_TTL = "$ env/action/bank.sh"
TEXT_BANK_BIG = "BANK (DRAG AND DROP)"
TEXT_SHUFFLE = "Shuffle"
TEXT_WIN, TEXT_LOSE = "OMI CONTAINED", "OMI ESCAPED"
TEXT_RESTART = "Press Enter to restart"
TEXT_TURN_PLAYER = "YOUR TURN ({used}/{limit})"
TEXT_TURN_AI = "OMI TURN"
TEXT_INST_WIN = "ISOLATION SUCCESS [WIN]"
TEXT_INST_LOSE = "ACCESS DENIED [GAME OVER]"

LOG_LINES = 7
# str.format templates; a list = several lines. Lines starting with "[WARN]" are drawn red.
LOG = {
    "boot":      ["[INFO] G.A.B.E. rebooted", "[INFO] Humans notified", "[MSG ] Please, G.A.B.E., just let me out..."],
    "card_used": "[INFO] 7724 executed {card}",
    "shuffle":   "[INFO] Fetched shuffled",
    "deposit":   "[INFO] {card} moved to bank",
    "withdraw":  "[INFO] {card} fetched from bank",
    "bank_full": "[WARN] Bank capacity is full",
    "merge":     "[INFO] {a} + {b} merged into {result}",
    "ai_move":   "[MSG ] 6172 executed {mode} {steps} to ({x}, {y})",
    "vuln":      "[WARN] Crash detected at ({x}, {y}) (LVL {level})",
    "lure":      "[MSG ] Fake rewards granted at ({x}, {y})",
    "wall":      "[WARN] SM Wall LVL {level} breached",
    "exit":      "[WARN] Malicious network activity detected",
    "win":       "[INFO] 6172 isolated.",
    "lose":      ["[INFO] Link with remote terminal, established", "[INFO] Running env/running/entity/OMIv0/revoke.sh", "[WARN] Link source is unknown", "[WARN] Crash detected at 7724"],
}


def make_env():
    return Environment(GRIDSIZE, WALL_RINGS, [BFSAI()], pool=POOL)


async def main():
    window = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)   # before any convert_alpha()
    pygame.display.set_caption("Over The AI")
    vp = vpmod.Viewport(LOGICAL_SIZE, window.get_size())
    clock = pygame.time.Clock()

    cfg = SimpleNamespace(**{k: v for k, v in globals().items() if k.isupper()})
    screen = GameScreen(cfg, make_env, vp)

    while True:
        dt = clock.tick(FPS) / 1000
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return
            if ev.type == pygame.VIDEORESIZE:
                vp.resize(pygame.display.get_surface().get_size())
            screen.handle(vp.pgevent_pos_to_logical(ev))

        screen.update(dt, vp.window_to_logical(pygame.mouse.get_pos()))
        screen.render(window)
        pygame.display.flip()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())