class Theme:
    # general
    BG = (20, 20, 28)
    TEXT = (255, 255, 255)
    TEXT_SOFT = (210, 210, 220)
    TEXT_DIM = (150, 150, 160)

    # board tiles
    TILE_EMPTY = (50, 55, 70)
    TILE_EXIT = (79, 18, 18)

    WALL_FILL = (135, 135, 160)
    WALL_BORDER = (95, 95, 120)

    OBSTACLE_OUTER = (235, 235, 245)
    OBSTACLE_INNER = (25, 25, 32)

    VULN_OUTER = (190, 19, 119)
    VULN_INNER = (218, 25, 137)

    STERILE_FILL = (168, 54, 65)
    STERILE_BORDER = (120, 37, 45)

    LURE = (221, 174, 34)

    # cell state filters (multiplier, 255 = unchanged)
    LOCKED_MULT = (150, 150, 150)
    EXPLORED_MULT = (180, 180, 180)

    # entities / overlays
    AI = (255, 0, 0)
    GHOST_OK = (80, 220, 120, 110)
    GHOST_BAD = (230, 70, 70, 110)
    LABEL_BG = (0, 0, 0, 160)
    LABEL_ACTIVE = (255, 255, 255)
    LABEL_INACTIVE = (150, 150, 160)

    # verdict screen
    WIN = (110, 230, 140)
    LOSE = (240, 90, 90)
    VERDICT_SHADE = (0, 0, 0, 160)

    # buttons
    BUTTON = (60, 60, 90)
    BUTTON_HOVER = (90, 90, 120)

    # cards
    CARD_COLORS = {
        "placement": (70, 110, 180),
        "information": (80, 160, 120),
        "manipulation": (180, 100, 70),
    }
    CARD_DEFAULT = (90, 90, 90)
    CARD_HOVER_BOOST = 30
    CARD_ACTIVE = (80, 80, 90)
    CARD_ACTIVE_TEXT = (140, 140, 150)

    # text panel
    PANEL_BG = (32, 34, 46)
    PANEL_TITLE = (170, 175, 200)
    PANEL_KEY = (255, 220, 120)
    PANEL_DESC = (210, 210, 220)