from __future__ import annotations

import os
import pygame

import cells
import nueu_view as view
from environment import VERDICT_HOLD, VERDICT_WIN
from gameview import theme
from gameview import layout as glayout
from gameview.controller import GameController

WHITE = (255, 255, 255)
GREY = (90, 90, 90)

FALLBACK = {
    "empty": (24, 24, 32, 255), "wall": (110, 110, 140, 255), "obstacle": (235, 235, 245, 255),
    "vuln": (218, 25, 137, 255), "sterile": (168, 54, 65, 140), "lure": (221, 174, 34, 255),
    "exit": (79, 18, 18, 255), "omi": (255, 0, 0, 255),
}

TILE_KINDS = {
    cells.Obstacle: "obstacle",
    cells.Vulnerability: "vuln",
    cells.VulnerabilitySterileZone: "sterile",
    cells.FakeRewards: "lure",
    cells.Exit: "exit"
}


class Fonts:
    def __init__(self, path):
        self.path, self._fonts, self._texts = path, {}, {}
        
    def text(self, s: str, size: int, color: tuple[int, int, int, int], wrap=0) -> pygame.Surface:
        key = (s, size, tuple(color), wrap)
        surf = self._texts.get(key)
        
        if surf is None:
            if len(self._texts) > 600:
                self._texts.clear()
            font = self._fonts.setdefault(size, pygame.font.Font(self.path, size))
            surf = self._texts[key] = font.render(s, True, tuple(color), None, wrap)
        return surf
    

def load_images(folder: str, size: tuple[int, int], smooth=False):
    imgs = []
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                img = pygame.image.load(os.path.join(folder, f)).convert_alpha()
                imgs.append((pygame.transform.smoothscale if smooth else pygame.transform.scale)(img, size))
    return imgs


class GameScreen:
    def __init__(self, cfg, make_env):
        self.c = cfg
        self.fonts = Fonts(cfg.FONT_PATH)
        self.ctl = GameController(make_env, cfg.LOG, cfg.AI_STEP_DELAY, cfg.LOG_LINES)

        cd = (cfg.CELL_DIM, cfg.CELL_DIM)
        self.sprites = {k: load_images(os.path.join(cfg.TILES_DIR, k), cd, FALLBACK[k]) for k in
                        ("empty", "wall", "obstacle", "vuln", "sterile", "lure", "exit")}
        self.omi = load_images(os.path.join(cfg.OMI_DIR, "idle"), cd, FALLBACK["omi"])
        self._tiles, self._cards = {}, {}

        self.row = glayout.BentRowLayout(
            animations=view.anim.ArrayAnimationPlayer(),
            width=cfg.CARD_W, height=cfg.CARD_H, gap=cfg.CARD_GAP,
            max_bend=cfg.CARD_BEND, jump=cfg.CARD_JUMP,
        )
        self.scroll = 0
        self.press = None   # ("card", fetched_idx, pos) | ("shuffle",)
        self.drag = None    # fetched idx being dragged
        self.mouse = (0, 0)
        self._scroll_t = 0.0
        self._t = 0.0

    # ------------------------------------------------------------ geometry
    @property
    def fetched(self):
        return self.ctl.env.fetched

    @property
    def visible(self):
        return self.fetched[self.scroll:self.scroll + self.c.VISIBLE_CARDS]

    def fetched_layout(self):
        """(rects, rotations) for visible fetched cards; rects are unrotated and include the jump."""
        vis, env = self.visible, self.ctl.env
        self.row.items = vis
        active = env.active_card
        self.row.activeidx = next((i for i, c in enumerate(vis) if c is active), -1) if active else -1
        ox, oy = self.c.POS_FETCHED_CARDS
        rects = [pygame.Rect(ox + p[0], oy + p[1], self.c.CARD_W, self.c.CARD_H) for p in self.row.positions()]
        return rects, self.row.rotations()

    def bank_rects(self):
        ox, oy = self.c.POS_BANK_CARDS
        step = self.c.CARD_W + self.c.CARD_GAP
        return [pygame.Rect(ox + i * step, oy, self.c.CARD_W, self.c.CARD_H) for i in range(len(self.ctl.env.bank))]

    def pos_to_cell(self, p):
        gx, gy = self.c.POS_GRID_LAY
        s, n = self.c.CELL_DIM, self.ctl.env.envsize
        x, y = (p[0] - gx) // s, (p[1] - gy) // s
        return (x, y) if 0 <= x < n and 0 <= y < n else None

    def shuffle_rect(self):
        return self.fonts.text(self.c.TEXT_SHUFFLE, self.c.FONT_S_NORMAL, WHITE).get_rect(topleft=self.c.POS_SHUFFLE)

    # ------------------------------------------------------------ input (events are in logical coords)
    def handle(self, ev):
        c = self.ctl
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                c.cancel()
            elif ev.key == pygame.K_r:
                c.rotate("cw")
            elif ev.key == pygame.K_q:
                c.rotate("ccw")
            elif ev.key == pygame.K_f:
                c.rotate("flip")
            elif ev.key == pygame.K_RETURN and c.env.verdict != VERDICT_HOLD:
                c.restart()
                self.scroll, self.press, self.drag = 0, None, None
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self._down(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._up(ev.pos)
        elif ev.type == pygame.MOUSEMOTION:
            p = self.press
            if p and p[0] == "card" and self.drag is None:
                if (pygame.Vector2(ev.pos) - pygame.Vector2(p[2])).length() > self.c.DRAG_THRESHOLD:
                    self.drag = p[1]

    def _down(self, pos):
        if self.ctl.locked:
            return
        rects, _ = self.fetched_layout()
        for i, r in enumerate(rects):
            if r.collidepoint(pos):
                self.press = ("card", self.scroll + i, pos)
                return
        for card, r in zip(list(self.ctl.env.bank), self.bank_rects()):
            if r.collidepoint(pos):
                self.ctl.withdraw(card)
                return
        if self.shuffle_rect().collidepoint(pos):
            self.press = ("shuffle",)

    def _up(self, pos):
        p, d = self.press, self.drag
        self.press = self.drag = None
        if d is not None:
            self._drop(d, pos)
        elif p and p[0] == "card":
            if p[1] < len(self.fetched):
                self.ctl.play(self.fetched[p[1]])
        elif p and p[0] == "shuffle":
            if self.shuffle_rect().collidepoint(pos):
                self.ctl.shuffle()
        else:
            cell = self.pos_to_cell(pos)
            if cell:
                self.ctl.place(*cell)

    def _drop(self, d, pos):
        if d >= len(self.fetched):
            return
        if self.c.RECT_BANK.collidepoint(pos):
            self.ctl.deposit(self.fetched[d])
            return
        rects, _ = self.fetched_layout()
        for i, r in enumerate(rects):
            if r.collidepoint(pos):
                self.ctl.merge(d, self.scroll + i)
                return

    # ------------------------------------------------------------ update
    def update(self, dt, mouse):
        self.mouse = mouse
        self._t += dt
        self.ctl.update(dt)

        n = len(self.fetched)
        max_scroll = max(0, n - self.c.VISIBLE_CARDS)
        self.scroll = min(self.scroll, max_scroll)

        step = -1 if pygame.Rect(self.c.RECT_ARROW_L).collidepoint(mouse) else \
            1 if pygame.Rect(self.c.RECT_ARROW_R).collidepoint(mouse) else 0
        if step and max_scroll:
            self._scroll_t += dt
            if self._scroll_t >= self.c.SCROLL_INTERVAL:
                self._scroll_t = 0.0
                self.scroll = max(0, min(max_scroll, self.scroll + step))
        else:
            self._scroll_t = self.c.SCROLL_INTERVAL  # first hover step is instant

    # ------------------------------------------------------------ drawing
    def _text(self, s, text, size, pos, color=None, wrap=0):
        surf = self.fonts.text(text, size, color or self.c.COLOR_REGULAR, wrap)
        return s.blit(surf, pos)

    def draw(self, s):
        c, env = self.c, self.ctl.env
        s.fill(c.COLOR_BG)

        self._text(s, c.TEXT_INST_TTL, c.FONT_S_DETAIL, c.POS_INS_TTL)
        self._text(s, c.TEXT_INST, c.FONT_S_NORMAL, c.POS_INS_TXT, wrap=c.MAX_TWIDTH_FULL)
        self._draw_log(s)
        self._draw_status(s)
        self._draw_grid(s)
        self._draw_fetched(s)
        self._draw_bank(s)
        self._draw_drag(s)
        self._draw_verdict(s)

    def _draw_log(self, s):
        c = self.c
        self._text(s, c.TEXT_LOG_TTL, c.FONT_S_DETAIL, c.POS_LOG_TTL)
        for i, line in enumerate(self.ctl.log):
            color = c.COLOR_DANGER if line.startswith("[WARN]") else None
            self._text(s, line, c.FONT_S_DETAIL, (c.POS_LOG_TXT[0], c.POS_LOG_TXT[1] + i * c.FONT_DETAIL_HEIGHT), color)

    def _draw_status(self, s):
        c = self.c
        self._text(s, c.TEXT_SMSTAT_TTL, c.FONT_S_DETAIL, c.POS_SMWSTAT_TTL)
        walls = sorted(self.ctl.env.sm_walls, key=lambda w: w.level)
        for i, w in enumerate(walls):
            col, row = divmod(i, c.STATUS_ROWS)
            status = "BREACHED" if w.collapsed else "ACTIVE" if w.active else "LOCKED"
            text = c.STATUS_FMT.format(level=w.level, status=status, exploited=w.exploited, needed=w.min_exploits)
            color = c.COLOR_DANGER if w.collapsed else c.COLOR_REGULAR if w.active else GREY
            self._text(s, text, c.FONT_S_NORMAL,
                       (c.POS_SMWSTAT_LAY[0] + col * c.STATUS_COL_W, c.POS_SMWSTAT_LAY[1] + row * c.STATUS_ROW_H), color)

    # ---- grid
    @staticmethod
    def _layers(cell):
        sc, out = cell.special_cell, []
        if isinstance(sc, cells.SMWallCell):
            out.append("wall")
            sc = sc.child
        if sc is not None and not getattr(sc, "used", False):
            kind = TILE_KINDS.get(type(sc))
            if kind:
                out.append(kind)
        return tuple(out)

    def _tile(self, seed, layers, state):
        key = (seed, layers, state)
        t = self._tiles.get(key)
        if t is None:
            e = self.sprites["empty"]
            t = e[seed % len(e)].copy()
            for k in layers:
                spr = self.sprites[k]
                t.blit(spr[seed % len(spr)], (0, 0))
            if state == "locked":
                t.fill(self.c.LOCKED_MULT, special_flags=pygame.BLEND_RGB_MULT)
            elif state == "explored":
                t.fill(self.c.EXPLORED_MULT, special_flags=pygame.BLEND_RGB_MULT)
            self._tiles[key] = t
        return t

    def _draw_grid(self, s):
        c, env = self.c, self.ctl.env
        gx, gy, d = *c.POS_GRID_LAY, c.CELL_DIM
        for x, y in env.all_coords():
            cell = env.coord_to_cell(x, y)
            s.blit(self._tile((x * 7 + y * 13) % 12, self._layers(cell), cell.state), (gx + x * d, gy + y * d))

        for ai in env.ais:
            frame = self.omi[int(self._t * c.OMI_FPS) % len(self.omi)]
            s.blit(frame, (gx + ai.x * d, gy + ai.y * d))

        tok, cell = env.active_placement, self.pos_to_cell(self.mouse)
        if tok and cell:
            tint = pygame.Surface((d, d), pygame.SRCALPHA)
            tint.fill(c.GHOST_OK if env.can_place(*cell) else c.GHOST_BAD)
            for cx, cy in env.shape_coords(tok.shape, *cell):
                if env.coord_in_bounds(cx, cy):
                    s.blit(tint, (gx + cx * d, gy + cy * d))

    # ---- cards
    def _card_img(self, card) -> pygame.Surface:
        name = type(card).__name__
        img = self._cards.get(name)
        if img is None:
            size = (self.c.CARD_W, self.c.CARD_H)
            path = os.path.join(self.c.CARDS_DIR, name + ".png")
            if os.path.isfile(path):
                img = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), size)
            else:
                img = pygame.Surface(size, pygame.SRCALPHA)
                img.fill((0, 32, 96))
                img.blit(self.fonts.text(name, self.c.FONT_S_DETAIL, WHITE), (8, 8))
            self._cards[name] = img
        return img

    def _draw_fetched(self, s):
        c, env = self.c, self.ctl.env
        self._text(s, c.TEXT_FETCHED_TTL, c.FONT_S_DETAIL, c.POS_FETCHED_TTL)

        sr = self.shuffle_rect()
        col = c.SHUFFLE_HOVER if sr.collidepoint(self.mouse) else c.SHUFFLE_COLOR
        s.blit(self.fonts.text(c.TEXT_SHUFFLE, c.FONT_S_NORMAL, col), sr)
        pygame.draw.line(s, col, (sr.left, sr.bottom), (sr.right, sr.bottom), 2)

        n, vis = len(self.fetched), c.VISIBLE_CARDS
        self._arrow(s, pygame.Rect(c.RECT_ARROW_L), -1, self.scroll > 0)
        self._arrow(s, pygame.Rect(c.RECT_ARROW_R), 1, self.scroll + vis < n)

        rects, rots = self.fetched_layout()
        partners = {j for j in range(n) if self.drag is not None and self.ctl.can_merge(self.drag, j)}
        hovered = next((self.scroll + i for i, r in enumerate(rects)
                        if self.scroll + i in partners and r.collidepoint(self.mouse)), None)

        for i, (card, r, rot) in enumerate(zip(self.visible, rects, rots)):
            j = self.scroll + i
            if j == self.drag:
                continue  # its slot stays empty while dragging, nothing reflows
            img = self._card_img(card)
            if j in partners:
                img = img.copy()
                if j == hovered:
                    ov = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                    ov.fill((255, 255, 255, 90))
                    img.blit(ov, (0, 0))
                pygame.draw.rect(img, WHITE, img.get_rect(), 3)
            rimg = pygame.transform.rotozoom(img, rot, 1.0)
            s.blit(rimg, rimg.get_rect(center=r.center))
            if card is env.active_card:
                caret = self.fonts.text("^", c.FONT_S_DETAIL, c.COLOR_REGULAR)
                s.blit(caret, caret.get_rect(midtop=(r.centerx, r.bottom + 6)))

    def _arrow(self, s, rect, direction, enabled):
        col = WHITE if enabled else GREY
        pygame.draw.rect(s, col, rect, 2)
        cx, cy = rect.center
        w, h = rect.w * 0.25 * -direction, rect.h * 0.4
        pygame.draw.lines(s, col, False, [(cx + w, cy - h), (cx - w, cy), (cx + w, cy + h)], 2)

    def _draw_bank(self, s):
        c = self.c
        self._text(s, c.TEXT_BANK_TTL, c.FONT_S_DETAIL, c.POS_BANK_TTL)
        over = self.drag is not None and c.RECT_BANK.collidepoint(self.mouse)
        pygame.draw.rect(s, c.COLOR_GOOD if over else WHITE, c.RECT_BANK, 2)
        self._text(s, c.TEXT_BANK_BIG, c.FONT_S_NORMAL, c.POS_BANK_TTL_BIG)
        for card, r in zip(self.ctl.env.bank, self.bank_rects()):
            s.blit(self._card_img(card), r)

    def _draw_drag(self, s):
        if self.drag is not None and self.drag < len(self.fetched):
            img = self._card_img(self.fetched[self.drag])
            s.blit(img, img.get_rect(center=self.mouse))

    def _draw_verdict(self, s):
        c, env = self.c, self.ctl.env
        if env.verdict == VERDICT_HOLD:
            return
        shade = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        s.blit(shade, (0, 0))
        won = env.verdict == VERDICT_WIN
        big = self.fonts.text(c.TEXT_WIN if won else c.TEXT_LOSE, 96, c.COLOR_GOOD if won else c.COLOR_DANGER)
        sub = self.fonts.text(c.TEXT_RESTART, c.FONT_S_NORMAL, c.COLOR_REGULAR)
        cx, cy = s.get_rect().center
        s.blit(big, big.get_rect(center=(cx, cy)))
        s.blit(sub, sub.get_rect(center=(cx, cy + 80)))