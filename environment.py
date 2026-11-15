from __future__ import annotations

import random

from dataclasses import dataclass, field
from collections import deque
from typing import Literal

from _base import _Environment
import baseai
import cards
import cells
import events

VERDICT_HOLD = 0
VERDICT_WIN = 1
VERDICT_LOSE = -1

UNPLACEABLE_CELLS = (cells.Obstacle, cells.Vulnerability, cells.VulnerabilitySterileZone, cells.FakeRewards, cells.Exit)

@dataclass
class ModdableEnvAttrs:
    show_ai_minds: bool = False
    max_player_stepcount: int = 3
    ai_movement_modes: list[Literal["walk", "dash"]] = field(default_factory=lambda: ["walk", "dash"])
    banned_cards: list[cards.Card] = field(default_factory=list)


class Environment(_Environment):
    def __init__(
        self,
        envsize: int,
        wall_rings: tuple[int],
        ais: list[baseai.BaseAI],
        pool: list[type[cards.Card]],
        fetch_size: int = 4,
        rng: random.Random|None = None,
        bank_limit: int = 4
    ):
        if not envsize % 2:
            raise ValueError("Parameter envsize value must be an odd number")
        
        self.events: list[events.GameEvent] = []
        self.fetch_size = fetch_size
        self.pool = pool
        self.envsize = envsize
        self.rng = rng or random.Random()
        self.sm_walls: list[cells.SMWall] = []
        self.space: list[cells.Cell] = []
        self.initiate_space()
        self.create_exit_ring()
        self.create_smwall_rings(sorted(wall_rings))
        
        for ai in ais:
            ai.x = ai.y = self.envsize // 2
            
        self.ais = ais
        self.mstate = ModdableEnvAttrs()
        
        self.bank_limit = bank_limit
        self.bank: list[cards.Card] = []
        self.fetched: list[cards.Card] = []
        self.active_temp_mods: dict[str, cards.TempModificationToken] = {}
        self.active_placement: cards.PlacementToken = None
        
        self.playersteps = 0
        self.aisteps = 0
        self.last_playersteps = 0
        self.verdict = VERDICT_HOLD
        
    def emit(self, event: events.GameEvent):
        self.events.append(event)
        
    def drain(self) -> list[events.GameEvent]:
        evs, self.events = self.events, []
        return evs
    
    
    def coord_to_idx(self, x: int, y: int) -> int:
        return y * self.envsize + x
    
    def coord_to_cell(self, x: int, y: int) -> cells.Cell:
        return self.space[self.coord_to_idx(x, y)]

    def cell_to_coord(self, cell):
        return self._coord_of[id(cell)]

    def _emit_cell(self, cell: cells.Cell):
        self.emit(events.CellChanged(*self._coord_of[id(cell)]))

    def _emit_fetched(self, occasion):
        self.emit(events.FetchedChanged(list(self.fetched), list(self.bank), occasion))
    
    
    def coord_in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.envsize and 0 <= y < self.envsize
    
    def coord_to_rlayeridx(self, x: int, y: int) -> int:
        return min(x, y, self.envsize - 1 - x, self.envsize - 1 - y)
    
    def all_coords(self):
        for y in range(self.envsize):
            for x in range(self.envsize):
                yield x, y
    
    
    # INITIALIZATOR
    def _on_smwall_collapse(self, wall: cells.SMWall):
        for ai in self.ais:
            ai.max_walk_steps += 1
        self.emit(events.SMWallCollapsed(wall.level))
        
        revealed = [*wall.cells, *wall.vuln_cells]
        if wall.outer is not None:
            revealed +- wall.outer.vuln_cells
            
        for cell in revealed:
            self._emit_cell(cell)
    
    
    def initiate_space(self):
        self.space = [cells.Cell() for _ in range(self.envsize ** 2)]
        self._coord_of = {id(c): (i % self.envsize, i // self.envsize) for i, c in enumerate(self.space)}
    
    
    def create_exit_ring(self):
        for x, y in self.all_coords():
            if self.coord_to_rlayeridx(x, y) == 0:
                self.coord_to_cell(x, y).special_cell = cells.Exit()
    
    
    def create_smwall_rings(self, rlayeridxs: list[int]):
        if rlayeridxs and rlayeridxs[0] < 1:
            raise ValueError("Ring 0 is reserved for Exit")
        
        if len(set(rlayeridxs)) != len(rlayeridxs):
            raise ValueError("Duplicate ring detected")
        
        for i, lidx in enumerate(rlayeridxs):
            level = len(rlayeridxs) - i
            ring_cells = [
                self.coord_to_cell(x, y) for x, y in self.all_coords()
                if self.coord_to_rlayeridx(x, y) == lidx
            ]
            
            wall = cells.SMWall(level, ring_cells, rng=self.rng)
            wall.on_collapse = lambda w=wall: self._on_smwall_collapse(w)
            self.emit(events.SMWallCollapsed(level))
            
            if self.sm_walls:
                wall.outer = self.sm_walls[-1]
            self.sm_walls.append(wall)
        
        for lidx, wall in zip(rlayeridxs, self.sm_walls):
            zone = [
                (x, y) for x, y in self.all_coords()
                if self.coord_to_rlayeridx(x, y) > lidx
            ]
            
            self.sprinkle_vulns(wall, zone)
            
        if self.sm_walls:
            self.sm_walls[-1].activate()
    
    
    @staticmethod
    def _slot_is_free(cell: cells.Cell) -> bool:
        sc = cell.special_cell
        if isinstance(sc, cells.SMWallCell):
            return sc.child is None
        return sc is None
    
    @staticmethod
    def _put(cell: cells.Cell, special: cells.SpecialCell):
        if isinstance(cell.special_cell, cells.SMWallCell):
            cell.special_cell.child = special
            return
        cell.special_cell = special
    
    def _pick_vuln_coords(self, zone, count, avoid, attempts=50):
        cands = [p for p in zone if p not in avoid]
        for _ in range(attempts):
            self.rng.shuffle(cands)
            blocked, picked = set(), []
            
            for x, y in cands:
                if (x, y) in blocked or not self._slot_is_free(self.coord_to_cell(x, y)):
                    continue
            
                picked.append((x, y))
                blocked.update((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            
                if len(picked) == count:
                    return picked
        return None

    def sprinkle_vulns(self, wall, zone):
        zone_set = set(zone)
        spawn = (self.envsize // 2, self.envsize // 2)
        picked = self._pick_vuln_coords(zone, wall.vuln_count, avoid={spawn})
        
        if picked is None:
            raise ValueError(
                f"Wall level {wall.level}: zone of {len(zone)} cells can't fit {wall.vuln_count} "
                f"flaws with sterile zones. Move the ring outward or enlarge envsize."
            )

        for x, y in picked:
            cell = self.coord_to_cell(x, y)
            self._put(cell, cells.Vulnerability(wall))
            cell.state = "locked"
            wall.vuln_cells.append(cell)

        for x, y in picked:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if n in zone_set:
                        neighbor = self.coord_to_cell(*n)
                        if self._slot_is_free(neighbor):
                            self._put(neighbor, cells.VulnerabilitySterileZone())


    # PLAYER ACTIONS
    def _apply_action(self, token):
        if token is None: return
        self.fetched = [c for c in self.fetched if c not in token.remove_cards]
        self.fetched.extend(c() for c in token.add_cards)
        
        if token.remove_cards or token.add_cards:
            self._emit_fetched("manip")
        
        if token.do_placement is not None:
            self.active_placement = token.do_placement

        for mod in token.temporary_modifications:
            attr = mod.target_attr
        
            if not hasattr(self.mstate, attr): continue
            active = self.active_temp_mods.get(attr)
            
            if active is not None:
                if not active.update_dur_on_recast: continue
                mod.original_value = active.original_value
            else:
                mod.original_value = getattr(self.mstate, attr)

            val = mod.target_val if mod.target_val is not None else getattr(self.mstate, attr)
            if mod.target_op is not None:
                val = mod.target_op(val)
            
            setattr(self.mstate, attr, val)
            mod.effective_since = self.playersteps + mod.effective_offset
            self.active_temp_mods[attr] = mod
            self.emit(events.ModfierActivated(mod))


    def _playerstep(self):
        self.playersteps += 1
                
        for attr, mod in list(self.active_temp_mods.items()):
            if self.playersteps - mod.effective_since >= mod.duration:
                setattr(self.mstate, attr, mod.original_value)
                del self.active_temp_mods[attr]
                
            elif mod.target_op is not None and not mod.op_only_once:
                setattr(self.mstate, attr, mod.target_op(getattr(self.mstate, attr)))

        for card in list(self.fetched):
            self._apply_action(
                card.on_player_step(
                    self.playersteps, self.playersteps - self.last_playersteps,
                    self.mstate.max_player_stepcount
                ))
        
    
    def play_card(self, card: cards.Card) -> bool:
        if self.active_placement is not None or isinstance(card, tuple(self.mstate.banned_cards)):
            return False
        self._apply_action(card.on_activation(self.bank, self.fetched))
        self.fetched.remove(card)
        self._emit_fetched("user")
        self._playerstep()
        return True
    
    def reroll(self) -> bool:
        if self.active_placement is not None:
            return False
        
        self.fetched = [self.rng.choice(self.pool)() for _ in range(self.fetch_size)]
        self._emit_fetched("shuffled")
        self._playerstep()
        return True
    
    def transfer(self, card: cards.Card) -> bool:
        if self.active_placement is not None:
            return False
        
        if card in self.fetched:
            if len(self.bank) >= self.bank_limit:
                return False
            
            self.fetched.remove(card)
            self.bank.append(card)
            
        elif card in self.bank:
            self.bank.remove(card)
            self.fetched.append(card)
            
        else:
            return False
        self._emit_fetched("transferred")
        self._playerstep()
        return True
    
    def withdraw_idx(self, idx: int) -> bool:
        return self.transfer(self.bank[idx])
    
    def deposit_idx(self, idx) -> bool:
        return self.transfer(self.fetched[idx])
    
    
    def mergeable_partners_card(self, card_idx: cards.Card|int) -> list[cards.Card]:
        card = card_idx if isinstance(card_idx, cards.Card) else self.fetched[card_idx]
        if card not in self.fetched:
            raise ValueError(f"{card} is not fetched")
        
        mergeable = []
        for fc in self.fetched:
            if isinstance(fc, tuple(card.merging_partners)):
                mergeable.append(fc)
        return mergeable
    
    def mergeable_partners_idx(self, card_idx: cards.Card|int) -> list[int]:
        mergeable = self.mergeable_partners_card(card_idx)
        midx = [self.fetched.index(card) for card in mergeable]
        return midx
        
    def merge(self, idledidx: int, ovidx: int) -> bool:
        if idledidx == ovidx: return False
        
        c1, c2 = self.fetched[idledidx], self.fetched[ovidx]
        
        if not isinstance(c1, tuple(c2.merging_partners)) or not isinstance(c2, tuple(c1.merging_partners)):
            return False
        
        result = next((r[1] for r in c1.used_in_recipes if isinstance(c2, r[0])), None)
        
        if result is None: return False
        
        self._apply_action(c1.on_merging(c2))
        self._apply_action(c2.on_merging(c1))
        merged = result()
        self.fetched[ovidx] = merged
        
        del self.fetched[idledidx]
        self._emit(events.MergingHappened(list(self.fetched), c1, c2, merged))
        self._playerstep()
        
        return True
        
        
    def place(self, x: int, y: int) -> bool:
        if self.active_placement is None:
            return False
        shape = self.active_placement.shape
        
        if (
            x < 0 or y < 0
            or x + len(shape[0]) > self.envsize
            or y + len(shape) > self.envsize
        ): return False
        
        affected_cells = [
            self.coord_to_cell(x + ox, y + oy)
            for oy, row in enumerate(shape)
            for ox, b in enumerate(row)
            if b
        ]
        
        for cell in affected_cells:
            if self.active_placement.type != "flush" and cell.state == "explored":
                return False
            
            if isinstance(cell.special_cell, UNPLACEABLE_CELLS):
                return False
            
            if isinstance(cell.special_cell, cells.SMWallCell):
                if isinstance(cell.special_cell.child, UNPLACEABLE_CELLS):
                    return False
        
        token = self.active_placement
        for cell in affected_cells:
            if token.type == "flush":
                cell.state = "unexplored"
            elif isinstance(cell.special_cell, cells.SMWallCell):
                cell.special_cell.child = token.special_cell()
            else:
                cell.special_cell = token.special_cell()
            self._emit_cell(cell)

        self.active_placement = None
        self.emit(events.Placement(token))
        return True
    
       
    # AI THINGIES 
    @staticmethod
    def is_passable(cell: cells.Cell):
        return cell.state != "locked" and not isinstance(cell.special_cell, (cells.Obstacle, cells.SMWallCell))
    
    
    # def idx_nearest_sctype_from_coord(self, sc: cells.SpecialCell, x: int, y: int) -> int|None:
    #     g = self.gridsize
    #     s = self.space
    #     start = y * g + x
    #     seen, queue = {start}, deque([start])
    #     while queue:
    #         i = queue.popleft()
    #         if isinstance(s[i].special_cell, sc):
    #             pass
            
    #         x, y = i % g, i // g
    #         dirs = [
    #             (dx, dy) for dy in (-1, 0, 1)
    #             for dx in (-1, 0, 1) if (dx, dy) != (0, 0)
    #         ]
            
    #         for dx, dy in dirs:
    #             nx, ny = x + dx, y + dy
    #             if not (0 <= nx < g and 0 <= ny < g):
    #                 continue
                
    #             j = ny * g + nx
    #             if j in seen or not self.is_passable(s[j]):
    #                 continue
    #             seen.add(j)
    #             queue.append(j)
                
    
    def should_player_play(self):
        return self.playersteps - self.last_playersteps < self.mstate.max_player_stepcount
    
    @staticmethod
    def _is_player_block(cell: cells.Cell) -> bool:
        sc = cell.special_cell
        if isinstance(sc, cells.SMWallCell):
            sc = sc.child
        return isinstance(sc, cells.Obstacle)
    
    def _flood(self, start: tuple[int, int]) -> tuple[set[tuple[int, int]], bool]: # (reachable coords, sealed)
        seen, queue, sealed = {start}, deque([start]), True
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                
                if (nx, ny) in seen:
                    continue
                if not self.coord_in_bounds(nx, ny):
                    sealed = False
                    continue
                
                cell = self.coord_to_cell(nx, ny)
                if self.is_passable(cell):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
                    
                elif not self._is_player_block(cell):
                    sealed = False
        return seen, sealed
    
    def are_ais_isolated(self) -> bool:
        return all(self._flood((ai.x, ai.y))[1] for ai in self.ais)
    
    def are_ais_starved(self) -> bool:
        reachable = set()
        
        for ai in self.ais:
            reachable |= self._flood((ai.x, ai.y))[0]
        reachable_ids = {id(self.coord_to_cell(*p)) for p in reachable}
        
        for wall in self.sm_walls:
            if not wall.active or wall.collapsed:
                continue
            
            available = sum(
                1 for cell in wall.vuln_cells
                if isinstance(cell.special_cell, cells.Vulnerability)
                and not cell.special_cell.used and id(cell) in reachable_ids
            )
            
            if available < wall.min_exploits - wall.exploited:
                return True
        return False
    
    def _check_win(self) -> bool:
        if self.are_ais_isolated() or self.are_ais_starved():
            self._set_verdict(VERDICT_WIN)
            return True
        return False
    
    def _set_verdict(self, verdict: int):
        if self.verdict != VERDICT_HOLD: # idempotent
            return
        self.verdict = verdict
        self.emit(events.VerdictReached(verdict))    
    
    def _move_ai(self, idx: int, ai, decision) -> bool:
        mode, distance = decision.mode, decision.distance
        if mode not in self.mstate.ai_movement_modes:
            mode, distance = ("walk", ai.max_walk_steps) if mode == "dash" else ("dash", self.envsize)
        elif mode == "dash":
            distance = self.envsize

        dx, dy = decision.direction
        path = [(ai.x, ai.y)]
        slot = len(self.events)
        reached_exit = False

        for _ in range(distance):
            nx, ny = ai.x + dx, ai.y + dy
            if not self.coord_in_bounds(nx, ny):
                break
            cell = self.coord_to_cell(nx, ny)
            if not self.is_passable(cell):
                break

            ai.x, ai.y = nx, ny
            path.append((nx, ny))
            cell.state = "explored"
            cell.step_on()                    # may collapse a wall -> emits its own events
            self.emit(events.CellChanged(nx, ny))
        
            if isinstance(cell.special_cell, cells.Exit):
                reached_exit = True
                break

        if len(path) > 1:
            self.events.insert(slot, events.AIMoved(idx, path, mode))
        return reached_exit


    def aistep(self):
        stuck = 0
        
        for idx, ai in enumerate(self.ais):
            decision = ai.decide(ai.space_parse(self.space, self))
            if isinstance(decision, baseai.Inable):
                stuck += 1
                continue
            if self._move_ai(idx, ai, decision):
                self._set_verdict(VERDICT_LOSE)
                return

        self.aisteps += 1
        
        if stuck >= len(self.ais) or self._check_win():
            # Verdict set in check win
            return

        for card in list(self.fetched):
            self._apply_action(card.on_ai_step(self.aisteps))