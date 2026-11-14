from __future__ import annotations

import copy
import random

from dataclasses import dataclass
from typing import Literal

import baseai
import cards
import cells

VERDICT_HOLD = 0
VERDICT_WIN = 1
VERDICT_LOSE = -1

UNPLACEABLE_CELLS = (cells.Obstacle, cells.Vulnerability, cells.VulnerabilitySterileZone, cells.FakeRewards, cells.Exit)

@dataclass
class ModdableEnvAttrs:
    show_ai_minds: bool = False
    max_playersteps: int = 3
    ai_movement_modes: list[Literal["walk", "dash"]] = ["walk", "dash"]


class Environment:
    def __init__(
        self,
        envsize: int,
        wall_rings: tuple[int],
        ais: list[baseai.BaseAI],
        rng: random.Random|None = None,
        bank_limit: int = 4
    ):
        if not envsize % 2:
            raise ValueError("Parameter envsize value must be an odd number")
        
        self.envsize = envsize
        self.gridsize = envsize + 1
        self.rng = rng or random.Random()
        self.sm_walls: list[cells.SMWall] = []
        self.space: list[cells.Cell] = []
        self.initiate_space()
        self.create_exit_ring()
        self.create_smwall_rings(sorted(wall_rings))
        
        for ai in ais:
            ai.x = ai.y = self.gridsize // 2
            
        self.ais = ais
        self.mstate = ModdableEnvAttrs()
        
        self.bank_limit = bank_limit
        self.bank: list[cards.Card] = []
        self.fetched: list[cards.Card] = []
        self.active_temp_mods: dict[str, cards.TempModificationToken] = []
        self.active_placement: cards.PlacementToken = None
        
        self.playersteps = 0
        self.last_playersteps = 0
        self.verdict = VERDICT_HOLD
        
        
    # COORD MANIPS
    def coord_to_idx(self, x: int, y: int) -> int:
        return y * self.envsize + x
    
    def coord_to_cell(self, x: int, y: int) -> cells.Cell:
        return self.space[self.coord_to_idx(x, y)]
    
    def coord_in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.envsize and 0 <= y < self.envsize
    
    def coord_to_rlayeridx(self, x: int, y: int) -> int:
        return min(x, y, self.envsize - 1 - x, self.envsize - 1 - y)
    
    def all_coords(self):
        for y in range(self.envsize):
            for x in range(self.envsize):
                yield x, y
    
    
    # INITIALIZATOR
    def initiate_space(self):
        self.space = [cells.Cell() for _ in range(self.envsize ** 2)]
    
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
                if self.coord_to_rlayeridx(x, y)
            ]
            
            wall = cells.SMWall(level, ring_cells, self.rng)
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
    
    def sprinkle_vulns(self, wall: cells.SMWall, zone: list[tuple[int, int]]):
        zone_set = set(zone)
        candidates = zone[:]
        self.rng.shuffle(candidates)
        
        placed = 0
        for x, y in candidates:
            if placed >= wall.vuln_count:
                break
            
            cell = self.coord_to_cell(x, y)
            if not self._slot_is_free(cell):
                continue
            
            self._put(cell, cells.Vulnerability(wall))
            cell.state = "locked"
            wall.vuln_cells.append(cell)
            placed += 1
            
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    
                    if n not in zone_set:
                        continue
                    
                    neighbor = self.coord_to_cell(*n)
                    if self._slot_is_free(neighbor):
                        self._put(neighbor, cells.VulnerabilitySterileZone())
                        
        if placed < wall.vuln_count:
            raise ValueError("Zone too small for this wall's vulnerability")


    # PLAYER ACTIONS
    def _apply_action(self, token: cards.ActionToken):
        self.fetched = [fcard for fcard in self.fetched if not fcard in token.remove_cards]
        self.fetched.extend([card() for card in token.add_cards])
        self.active_placement = token.do_placement
        
        for mod in token.temporary_modifications:
            attr = mod.target_attr
            
            if not hasattr(self.mstate, attr): continue
            if attr in self.active_temp_mods.keys() and not self.active_temp_mods[attr].update_dur_on_recast: continue
            mod.original_value = getattr(self.mstate, attr)
            
            setattr(self.mstate, attr, mod.target_val if mod.target_val is not None else mod.original_value)
            
            if mod.target_op is not None:
                setattr(self, attr, mod.target_op(getattr(self.mstate, attr)))
                
            mod.effective_since = self.playersteps
            self.active_temp_mods[attr] = mod


    def _playerstep(self):
        self.playersteps += 1
        for mod in self.active_temp_mods.values():
            attr = mod.target_attr
            steps_passed = self.playersteps - mod.effective_since
            
            if mod.duration < steps_passed:
                setattr(self.mstate, attr, mod.original_value)
                del self.active_temp_mods[attr]
                continue
            
            if mod.target_op is not None and not mod.op_only_once:
                setattr(self.mstate, attr, mod.target_op(getattr(self.mstate, attr)))
        
    
    def play_card(self, card: cards.Card):
        self.apply_action(card.on_activation(self.bank, self.fetched))
        self.fetched.remove(card)
        self._playerstep()
        
    def merge(self, idledidx: int, ovidx: int):
        card1, card2 = self.fetched[idledidx], self.fetched[ovidx]
        action1, action2 = card1.on_merging(card2), card2.on_merging(card1)
        
        self.apply_action(action1)
        self.apply_action(action2)
        
        delete_card1 = True
        
        for recipe in card1.used_in_recipes:
            if isinstance(card2, recipe[0]):
                self.fetched[ovidx] = recipe[1]()
                delete_card1 = False
                break
        
        if delete_card1:
            del self.fetched[idledidx]
        del self.fetched[ovidx]
        
        self._playerstep()
        
        
    def place(self, x: int, y: int) -> bool:
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
            if isinstance(cell.special_cell, UNPLACEABLE_CELLS):
                return False
            
            if isinstance(cell.special_cell, cells.SMWallCell):
                if (cell.special_cell.child, UNPLACEABLE_CELLS):
                    return False
        
        for cell in affected_cells:
            if isinstance(cell.special_cell, cells.SMWallCell):
                cell.special_cell.child = cells.Obstacle()
                continue
            cell.special_cell = cells.Obstacle()
        return True
    
       
    # AI THINGIES 
    def should_player_play(self):
        return self.playersteps - self.last_playersteps <= self.mstate.max_playersteps
    
    def aistep(self):
        for ai in self.ais:
            decision = ai.decide(ai.space_parse(self.space))
            distance = decision.distance if decision.mode == "walk" else 9999
            dx, dy = decision.direction
            
            for _ in range(distance):
                ai.x, ai.y = ai.x + dx, ai.y + dy
                cell = self.coord_to_cell(ai.x, ai.y)
                cell.state = "explored"
                
                if cell.special_cell is not None:
                    cell.special_cell.on_corrupted()
                
                if isinstance(cell.special_cell, cells.Exit):
                    self.verdict = VERDICT_LOSE
                    break
                
                if isinstance(cell.special_cell, cells.Obstacle) or cell.state == "locked":
                    ai.x, ai.y = ai.x - dx, ai.y - dy