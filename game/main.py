import os
import pygame
pygame.init()

import gameview
import nueu_view as view
from gameview import theme

# Got from Figma, TTL = title
POS_INS_TTL = (154, 129)
POS_INS_TXT = (154, 152)
POS_LOG_TTL = (154, 849)
POS_LOG_TXT = (154, 877)

POS_SMWSTAT_TTL = (975, 108)
POS_SMWSTAT_LAY = (975, 132)

POS_FETCHED_TTL = (975, 263)
POS_FETCHED_LAY = (925, 296)

POS_BANK_TTL = (975, 613)
POS_BANK_TTL_BIG = (975, 670)
POS_BANK_LAY = (975, 716)

POS_GRID_LAY = (204, 220)

MAX_TWIDTH_FULL = 676
CELL_DIM = 38.4

GRIDSIZE = 15

##############################
open_img = lambda path: pygame.image.load(path).convert_alpha()
def load_spritesheet(path, size: tuple[int,int], appending: view.asset.SurfacesContainer|None = None) -> view.asset.SurfacesContainer:
    sprites = []
    for img in os.listdir(path):
        if not str.endswith(img, (".png", ".jpg", ".jpeg")): continue
        sprites.append(open_img(path+img))
    
    if appending is not None:
        return appending.surfaces.extend(sprites)
    return view.asset.SurfacesContainer(sprites, size)

ui_slide_bttn = open_img("assets/ui/slidebutton.png")

sprites_empty = load_spritesheet("assets/spritesheet/tiles/empty")
sprites_exit = load_spritesheet("assets/spritesheet/tiles/exit")
sprites_lure = load_spritesheet("assets/spritesheet/tiles/lure")
sprites_obstacle = load_spritesheet("assets/spritesheet/tiles/obstacle")
sprites_sterile = load_spritesheet("assets/spritesheet/tiles/sterile")
sprites_vuln = load_spritesheet("assets/spritesheet/tiles/vuln")
sprites_omi = load_spritesheet("assets/spritesheets/omi/idle", (CELL_DIM, CELL_DIM))
load_spritesheet("assets/spritesheets/omi/dash", None, sprites_omi) # dash and walk has the same anim
load_spritesheet("assets/spritesheets/omi/gotvuln", None, sprites_omi)
load_spritesheet("assets/spritesheets/omi/won", None, sprites_omi)

font = pygame.font.Font("assets/fonts/IBM Plex Mono/IBMPlexMono-Regular.ttf")

def create_text(
    text: str,
    size: int = theme.FONT_S_NORMAL,
    color: tuple[int, int, int] = theme.COLOR_REGULAR,
    max_width: int = MAX_TWIDTH_FULL
):
    return view.renderer.TextRenderer(text, size, color, max_width, font)

text_inst_ttl = create_text("$ cat env/running/entity/GABE/inst.txt", theme.FONT_S_DETAIL)
text_inst = create_text("MALICIOUS INTENT DETECTET, COMMENCE ISOLATION PROTOCOL. DON'T LET THEM OUT.")

text_log_ttl = create_text("$ cat env/log.txt", theme.FONT_S_DETAIL)
text_smstat_ttl = create_text("$ smwall status -v", theme.FONT_S_DETAIL)
text_fetched_ttl = create_text("$ env/action/fetched.sh", theme.FONT_S_DETAIL)
text_bank_ttl = create_text("$ env/action/bank.sh", theme.FONT_S_DETAIL)

logs = view.layout.UniformColumnLayout(view.anim.ArrayAnimationPlayer(), height=theme.FONT_DETAIL_HEIGHT, gap=0)

gridanims = view.anim.ArrayAnimationPlayer()
grid = view.layout.UniformGridLayout(gridanims, height=CELL_DIM, width=CELL_DIM, rows=GRIDSIZE, columns=GRIDSIZE)

grid_allfalse_mask = [False for _ in range(GRIDSIZE * GRIDSIZE)]