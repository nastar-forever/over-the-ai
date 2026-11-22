from __future__ import annotations

import os
import re
import pygame

import cells
import nueu_view as view
from environment import VERDICT_HOLD, VERDICT_WIN
from gameview import layout as glayout
from gameview import renderer as grenderer
from gameview.controller import GameController

WHITE = (255, 255, 255)
GREY = (90, 90, 90)
FETCH_PAD = (25, 31)   # scene margin around the fetched row so the jump/bend isn't clipped

TILE_KINDS = {
    cells.Obstacle: "obstacle", cells.Vulnerability: "vuln", cells.VulnerabilitySterileZone: "sterile",
    cells.FakeRewards: "lure", cells.Exit: "exit",
}
FALLBACK = {  # used when an asset folder is missing
    "empty": (24, 24, 32, 255), "wall": (110, 110, 140, 255), "obstacle": (235, 235, 245, 255),
    "vuln": (218, 25, 137, 255), "sterile": (168, 54, 65, 140), "lure": (221, 174, 34, 255),
    "exit": (79, 18, 18, 255), "omi": (255, 0, 0, 255), "corrupted": (58, 18, 46, 255),
}


def _natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def load_images(folder, size, fallback):
    """Every image in the folder is a frame (natural sort: f2 before f10).
    A wide strip whose width is a multiple of its height is sliced into square frames."""
    frames = []
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder), key=_natural):
            if not f.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            img = pygame.image.load(os.path.join(folder, f)).convert_alpha()
            w, h = img.get_size()
            parts = [img.subsurface((i * h, 0, h, h)) for i in range(w // h)] if w > h and w % h == 0 else [img]
            frames += [pygame.transform.scale(p, size) for p in parts]
    if not frames:
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill(fallback)
        frames.append(s)
    return frames


class TileRenderer(view._base.PrimitiveRenderer):
    """One grid cell; reads the live env every frame, so Restart needs no rebuild."""
    def __init__(self, screen, x, y):
        self.s, self.x, self.y = screen, x, y

    def get(self):
        s = self.s
        cell = s.ctl.env.coord_to_cell(self.x, self.y)
        layers, state = s.ctl.frozen.get((self.x, self.y)) or (s._layers(cell), cell.state)
        d = s.c.CELL_DIM
        return view._base.GetReturn(s._tile(layers, state), (d, d))

    def _draw(self, parent_surface, origin):
        gr = self.get()
        parent_surface.blit(gr.surface, gr.construct_rect(origin))


class GameScreen:
    def __init__(self, cfg, make_env, viewport):
        c = self.c = cfg
        self.ctl = GameController(
            make_env, 
            c.LOG, 
            c.AI_STEP_DELAY, 
            c.LOG_LINES,
            snapshot=lambda cell: (self._layers(cell), cell.state),
            walk_time=c.WALK_STEP_TIME,
            dash_time=c.DASH_STEP_TIME,
            win_delay=c.WIN_DELAY,
            panic_steps=c.PANIC_STEPS,
            panic_time=c.PANIC_STEP_TIME
        )
        self.renderer = view.renderer.Renderer(viewport, tuple(c.COLOR_BG))
        self._fonts, self._tiles, self._cards = {}, {}, {}

        cd = (c.CELL_DIM, c.CELL_DIM)
        self.sprites = {k: load_images(os.path.join(c.TILES_DIR, k), cd, FALLBACK[k]) for k in
            ("empty", "wall", "obstacle", "vuln", "sterile", "lure", "exit", "corrupted")
        }
        self.omi = load_images(os.path.join(c.OMI_DIR, "idle"), cd, FALLBACK["omi"])

        self.scroll = 0
        self.press = None   # ("card", fetched_idx, pos) | ("shuffle",)
        self.drag = None    # fetched idx being dragged
        self.mouse = (0, 0)
        self._scroll_t = 0.0
        self._t = 0.0
        self._frame = {k: 0 for k in self.sprites}
        self._build()

    # ------------------------------------------------------------ scene graph
    def _font(self, size):
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(self.c.FONT_PATH, size)
        return self._fonts[size]

    def _text(self, text, size, pos, color=None, wrap=None, font=None, active=True):
        tr = view.renderer.TextRenderer(text, size, tuple(color or self.c.COLOR_REGULAR), wrap, font or self._font(size))
        return tr, self.renderer.add_scene(tr, pos, active)

    def _build(self):
        c, add = self.c, self.renderer.add_scene
        D, N = c.FONT_S_DETAIL, c.FONT_S_NORMAL
        W, H, G = c.CARD_W, c.CARD_H, c.CARD_GAP
        anims = view.anim.ArrayAnimationPlayer
        Overlay, LiveScene = grenderer.Overlay, grenderer.LiveScene
        SL, Surf = view.renderer.SceneLayout, pygame.Surface

        # static texts
        self.inst_tr, _ = self._text("", N, c.POS_INS_TXT, wrap=c.MAX_TWIDTH_FULL)
        self._text(c.TEXT_INST_TTL, D, c.POS_INS_TTL)
        # self._text(c.TEXT_INST, N, c.POS_INS_TXT, wrap=c.MAX_TWIDTH_FULL)
        self._text(c.TEXT_LOG_TTL, D, c.POS_LOG_TTL)
        self._text(c.TEXT_SMSTAT_TTL, D, c.POS_SMWSTAT_TTL)
        self._text(c.TEXT_FETCHED_TTL, D, c.POS_FETCHED_TTL)
        self._text(c.TEXT_BANK_TTL, D, c.POS_BANK_TTL)
        self._text(c.TEXT_BANK_BIG, N, c.POS_BANK_TTL_BIG)

        # log + wall status (text items are updated every frame in _sync_text)
        self.log_items = [view.renderer.TextRenderer("", D, tuple(c.COLOR_REGULAR), None, self._font(D))
                          for _ in range(c.LOG_LINES)]
        add(view.layout.UniformColumnLayout(animations=anims(), width=c.LOG_WIDTH, height=c.FONT_DETAIL_HEIGHT,
                                            gap=0, items=self.log_items), c.POS_LOG_TXT, True)
        self.status_items = [view.renderer.TextRenderer("", N, tuple(c.COLOR_REGULAR), None, self._font(N))
                             for _ in range(c.STATUS_ROWS * c.STATUS_COLS)]
        add(view.layout.UniformGridLayout(animations=anims(), width=c.STATUS_COL_W, height=c.STATUS_ROW_H,
                                          rows=c.STATUS_ROWS, columns=c.STATUS_COLS, items=self.status_items),
            c.POS_SMWSTAT_LAY, True)

        # grid + overlays
        n = self.ctl.env.envsize
        add(view.layout.UniformGridLayout(
            animations=anims(), width=c.CELL_DIM, height=c.CELL_DIM, rows=n, columns=n,
            items=[TileRenderer(self, x, y) for y in range(n) for x in range(n)]), c.POS_GRID_LAY, True)
        add(Overlay(self._draw_ai), (0, 0), True)
        add(Overlay(self._draw_ghost), (0, 0), True)

        # fetched row: 4 persistent slots + bend layout + white-border filter for merge partners
        blank = Surf((W, H), pygame.SRCALPHA)
        self.slots = [view.asset.SurfacesContainer([blank, blank], (W, H)) for _ in range(c.VISIBLE_CARDS)]
        self.partner_fx = view.asset.FilterArray(
            self.slots, [False] * len(self.slots),
            [lambda s: pygame.draw.rect(s, WHITE, s.get_rect(), 3)])
        self.row = glayout.BentRowLayout(animations=anims(), width=W, height=H, gap=G, max_bend=c.CARD_BEND,
                                         jump=c.CARD_JUMP, items_limit=0)
        fx, fy = c.POS_FETCHED_CARDS
        sw, sh = c.VISIBLE_CARDS * (W + G) - G + 2 * FETCH_PAD[0], H + 2 * FETCH_PAD[1]
        add(LiveScene([SL(FETCH_PAD, self.row)], Surf((sw, sh), pygame.SRCALPHA), (0, 0, 0, 0)),
            (fx - FETCH_PAD[0], fy - FETCH_PAD[1]), True)
        add(Overlay(self._draw_arrows), (0, 0), True)
        self.caret_tr, self.caret_sc = self._text("^", D, (0, 0), active=False)

        shuf_font = pygame.font.Font(c.FONT_PATH, N)
        shuf_font.set_underline(True)
        self.shuffle_tr, self.sc_shuf = self._text(c.TEXT_SHUFFLE, N, c.POS_SHUFFLE, c.SHUFFLE_COLOR, font=shuf_font)
        _, self.sc_shuf_h = self._text(c.TEXT_SHUFFLE, N, c.POS_SHUFFLE, c.SHUFFLE_HOVER, font=shuf_font, active=False)

        # bank
        add(Overlay(self._draw_bank_frame), (0, 0), True)
        self.bank_slots = [view.asset.SurfacesContainer([blank], (W, H)) for _ in range(self.ctl.env.bank_limit)]
        self.bank_row = view.layout.UniformRowLayout(animations=anims(), width=W, height=H, gap=G, items_limit=0)
        bw = self.ctl.env.bank_limit * (W + G) - G
        add(LiveScene([SL((0, 0), self.bank_row)], Surf((bw, H), pygame.SRCALPHA), (0, 0, 0, 0)),
            c.POS_BANK_CARDS, True)

        # drag + verdict
        add(Overlay(self._draw_drag), (0, 0), True)
        mk = lambda t, col: view.renderer.TextRenderer(t, 96, tuple(col), None, self._font(96))
        self.v_win, self.v_lose = mk(c.TEXT_WIN, c.COLOR_GOOD), mk(c.TEXT_LOSE, c.COLOR_DANGER)
        self.v_sub = view.renderer.TextRenderer(c.TEXT_RESTART, N, tuple(c.COLOR_REGULAR), None, self._font(N))
        add(Overlay(self._draw_verdict), (0, 0), True)

    # ------------------------------------------------------------ cards
    def _card_surfaces(self, card):
        """[plain, hover-filled] surfaces, cached per card class."""
        name = type(card).__name__
        pair = self._cards.get(name)
        if pair is None:
            size = (self.c.CARD_W, self.c.CARD_H)
            path = os.path.join(self.c.CARDS_DIR, name + ".png")
            if os.path.isfile(path):
                img = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), size)
            else:
                img = pygame.Surface(size, pygame.SRCALPHA)
                img.fill((0, 32, 96))
                img.blit(self._font(self.c.FONT_S_DETAIL).render(name, True, WHITE), (8, 8))
            hover = img.copy()
            ov = pygame.Surface(size, pygame.SRCALPHA)
            ov.fill((255, 255, 255, 90))
            hover.blit(ov, (0, 0))
            pair = self._cards[name] = [img, hover]
        return pair

    @property
    def fetched(self):
        return self.ctl.env.fetched

    @property
    def visible(self):
        return self.fetched[self.scroll:self.scroll + self.c.VISIBLE_CARDS]

    def _sync_fetched(self):
        vis, env = self.visible, self.ctl.env
        for slot, card in zip(self.slots, vis):
            slot.surfaces = self._card_surfaces(card)
        self.row.items = self.slots[:len(vis)]
        active = env.active_card
        self.row.activeidx = next((i for i, cd in enumerate(vis) if cd is active), -1) if active else -1
        d = self.drag
        self.row.invisidx = d - self.scroll if d is not None and 0 <= d - self.scroll < len(vis) else -1

    def fetched_rects(self):
        self._sync_fetched()
        ox, oy = self.c.POS_FETCHED_CARDS
        return [pygame.Rect(ox + p[0], oy + p[1], self.c.CARD_W, self.c.CARD_H) for p in self.row.positions()]

    def bank_rects(self):
        bank = self.ctl.env.bank
        self.bank_row.items = self.bank_slots[:len(bank)]
        ox, oy = self.c.POS_BANK_CARDS
        return [pygame.Rect(ox + p[0], oy + p[1], self.c.CARD_W, self.c.CARD_H) for p in self.bank_row.positions()]

    def pos_to_cell(self, p):
        gx, gy = self.c.POS_GRID_LAY
        s, n = self.c.CELL_DIM, self.ctl.env.envsize
        x, y = (p[0] - gx) // s, (p[1] - gy) // s
        return (x, y) if 0 <= x < n and 0 <= y < n else None

    def shuffle_rect(self):
        return self.shuffle_tr.get().surface.get_rect(topleft=self.c.POS_SHUFFLE)

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
            elif ev.key == pygame.K_RETURN and c.verdict != VERDICT_HOLD:
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
        for i, r in enumerate(self.fetched_rects()):
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
        for i, r in enumerate(self.fetched_rects()):
            if r.collidepoint(pos):
                self.ctl.merge(d, self.scroll + i)
                return

    # ------------------------------------------------------------ update / render
    def update(self, dt, mouse):
        c = self.c
        self.mouse = mouse
        self._t += dt
        self._frame = {k: int(self._t * c.TILE_FPS) % len(v) for k, v in self.sprites.items()}
        self.ctl.update(dt)

        max_scroll = max(0, len(self.fetched) - c.VISIBLE_CARDS)
        self.scroll = min(self.scroll, max_scroll)
        step = -1 if pygame.Rect(c.RECT_ARROW_L).collidepoint(mouse) else \
            1 if pygame.Rect(c.RECT_ARROW_R).collidepoint(mouse) else 0
        if step and max_scroll:
            self._scroll_t += dt
            if self._scroll_t >= c.SCROLL_INTERVAL:
                self._scroll_t = 0.0
                self.scroll = max(0, min(max_scroll, self.scroll + step))
        else:
            self._scroll_t = c.SCROLL_INTERVAL  # first hover step is instant

        rects = self.fetched_rects()
        for i in range(len(self.slots)):
            partner = i < len(rects) and self.drag is not None and self.ctl.can_merge(self.drag, self.scroll + i)
            self.partner_fx.mask[i] = partner
            self.slots[i].variant = 1 if partner and rects[i].collidepoint(mouse) else 0
        self.partner_fx.update()

        for slot, card in zip(self.bank_slots, self.ctl.env.bank):
            slot.surfaces = [self._card_surfaces(card)[0]]
        self.bank_rects()  # syncs bank_row.items

        ai = self.row.activeidx
        self.caret_sc.active = ai >= 0
        if ai >= 0:
            r = rects[ai]
            self.caret_sc.origin = (r.centerx - self.caret_tr.get().size[0] // 2, r.bottom + 6)

        hov = self.shuffle_rect().collidepoint(mouse)
        self.sc_shuf.active, self.sc_shuf_h.active = not hov, hov

        self._sync_text()
        self.renderer.update(dt)

    def _sync_text(self):
        c = self.c
        lines = list(self.ctl.log)
        for i, tr in enumerate(self.log_items):
            line = lines[i] if i < len(lines) else ""
            tr.color = tuple(c.COLOR_DANGER if line.startswith("[WARN]") else c.COLOR_REGULAR)
            tr.text = line

        targets = [("", c.COLOR_REGULAR)] * len(self.status_items)
        for i, w in enumerate(sorted(self.ctl.env.sm_walls, key=lambda w: w.level)[:len(targets)]):
            col, row = divmod(i, c.STATUS_ROWS)
            status = "BREACHED" if w.collapsed else "ACTIVE" if w.active else "LOCKED"
            text = c.STATUS_FMT.format(level=w.level, status=status, exploited=w.exploited, needed=w.min_exploits)
            targets[row * c.STATUS_COLS + col] = (
                text, c.COLOR_DANGER if w.collapsed else c.COLOR_REGULAR if w.active else GREY)
        for tr, (text, color) in zip(self.status_items, targets):
            tr.color = tuple(color)
            tr.text = text

        # turn / verdict banner
        ctl, v = self.ctl, self.ctl.verdict
        if v == VERDICT_WIN:
            text, color = c.TEXT_INST_WIN, c.COLOR_GOOD
        elif v != VERDICT_HOLD:
            text, color = c.TEXT_INST_LOSE, c.COLOR_DANGER
        elif ctl.player_turn:
            text = c.TEXT_TURN_PLAYER.format(used=ctl.steps_used, limit=ctl.steps_limit)
            color = c.COLOR_REGULAR
        else:
            text, color = c.TEXT_TURN_AI, c.COLOR_REGULAR
        self.inst_tr.color = tuple(color)   # color first: only a text change clears the cached surface
        self.inst_tr.text = text

    def render(self, window):
        self.renderer.render(window)

    # ------------------------------------------------------------ overlays (callbacks for grenderer.Overlay)
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

    def _tile(self, layers, state):
        f = self._frame
        explored = state == "explored"
        key = (f["empty"], f["corrupted"] if explored else -1,
               tuple((k, f[k]) for k in layers), state)
        t = self._tiles.get(key)
        if t is None:
            t = self.sprites["empty"][f["empty"]].copy()
            for k in layers:
                t.blit(self.sprites[k][f[k]], (0, 0))
            if explored:                                   # always on top, whatever the cell holds
                t.blit(self.sprites["corrupted"][f["corrupted"]], (0, 0))
            elif state == "locked":
                t.fill(self.c.LOCKED_MULT, special_flags=pygame.BLEND_RGB_MULT)
            self._tiles[key] = t
        return t

    def _draw_ai(self, s):
        c = self.c
        gx, gy, d = *c.POS_GRID_LAY, c.CELL_DIM
        frame = self.omi[int(self._t * c.OMI_FPS) % len(self.omi)]
        for i, ai in enumerate(self.ctl.env.ais):
            x, y = self.ctl.ai_pos.get(i, (ai.x, ai.y))
            s.blit(frame, (gx + x * d, gy + y * d))

    def _draw_ghost(self, s):
        c, env = self.c, self.ctl.env
        tok, cell = env.active_placement, self.pos_to_cell(self.mouse)
        if not (tok and cell):
            return
        gx, gy, d = *c.POS_GRID_LAY, c.CELL_DIM
        tint = pygame.Surface((d, d), pygame.SRCALPHA)
        tint.fill(c.GHOST_OK if env.can_place(*cell) else c.GHOST_BAD)
        for cx, cy in env.shape_coords(tok.shape, *cell):
            if env.coord_in_bounds(cx, cy):
                s.blit(tint, (gx + cx * d, gy + cy * d))

    def _draw_arrows(self, s):
        c, n = self.c, len(self.fetched)
        for rect, direction, enabled in (
            (pygame.Rect(c.RECT_ARROW_L), -1, self.scroll > 0),
            (pygame.Rect(c.RECT_ARROW_R), 1, self.scroll + c.VISIBLE_CARDS < n),
        ):
            col = WHITE if enabled else GREY
            pygame.draw.rect(s, col, rect, 2)
            cx, cy = rect.center
            w, h = rect.w * 0.25 * -direction, rect.h * 0.4
            pygame.draw.lines(s, col, False, [(cx + w, cy - h), (cx - w, cy), (cx + w, cy + h)], 2)

    def _draw_bank_frame(self, s):
        c = self.c
        over = self.drag is not None and c.RECT_BANK.collidepoint(self.mouse)
        pygame.draw.rect(s, tuple(c.COLOR_GOOD) if over else WHITE, c.RECT_BANK, 2)

    def _draw_drag(self, s):
        if self.drag is not None and self.drag < len(self.fetched):
            img = self._card_surfaces(self.fetched[self.drag])[0]
            s.blit(img, img.get_rect(center=self.mouse))

    def _draw_verdict(self, s):
        v = self.ctl.verdict
        if v == VERDICT_HOLD:
            return
        env = self.ctl.env
        if env.verdict == VERDICT_HOLD:
            return
        shade = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        s.blit(shade, (0, 0))
        big = (self.v_win if v == VERDICT_WIN else self.v_lose).get().surface
        sub = self.v_sub.get().surface
        cx, cy = s.get_rect().center
        s.blit(big, big.get_rect(center=(cx, cy)))
        s.blit(sub, sub.get_rect(center=(cx, cy + 80)))