from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import enums


@dataclass
class SpecialCell:
    priority: ClassVar[int] = 0

    def step_on(self) -> None:
        pass


@dataclass
class SMWallCell(SpecialCell):
    level: int = 0
    child: SpecialCell | None = None


@dataclass
class Vulnerability(SpecialCell):
    wall: SMWall | None = None
    used: bool = False

    def step_on(self) -> None:
        if not self.used and self.wall is not None:
            self.used = True
            self.wall.register_vuln_exploit()


@dataclass
class VulnerabilitySterileZone(SpecialCell):
    pass


@dataclass
class FakeRewards(SpecialCell):
    priority: ClassVar[int] = 3


@dataclass
class Exit(SpecialCell):
    priority: ClassVar[int] = 2


@dataclass
class Cell:
    state: int = enums.CELL_STATE_UNEXPLORED
    special_cell: SpecialCell | None = None

    def step_on(self) -> None:
        if self.special_cell is not None:
            self.special_cell.step_on()

    def get_priority(self) -> int:
        visible = self.state in (enums.CELL_STATE_LOCKED, enums.CELL_STATE_EXPLORED)
        return self.special_cell.priority if self.special_cell and visible else 0


class SMWall:
    def __init__(self, level: int, cells: tuple[Cell, ...], rng: random.Random | None = None):
        rng = rng or random.Random()
        self.level = level
        self.cells = cells
        
        for cell in cells:
            cell.special_cell = SMWallCell(level=level, child=cell.special_cell)
            cell.state = enums.CELL_STATE_LOCKED
        
        self.vuln_count = level * rng.randint(1, 2) + 1

    def register_vuln_exploit(self) -> None:
        self.vuln_count -= 1
        if self.vuln_count > 0: return
        
        for cell in self.cells:
            cell.state = enums.CELL_STATE_UNEXPLORED
            cell.special_cell = cell.special_cell.child
            

class Environment:
    def __init__(
        self,
        envsize: int,
        wall_rings: tuple[int],
        rng: random.Random|None = None
    ):
        self.envsize = envsize
        self.rng = rng or random.Random()
        self.sm_walls: list[SMWall] = []
        self.space: list[Cell] = []
        self.initiate_space()
        self.sprinkle_smwalls(sorted(wall_rings))
        
        
    # COORD MANIPS
    def coord_to_idx(self, x: int, y: int) -> int:
        return y * self.envsize + x
    
    def coord_to_cell(self, x: int, y: int) -> Cell:
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
        self.space = [Cell() for _ in range(self.envsize ** 2)]
    
    def sprinkle_smwalls(self, rlayeridxs: list[int]):
        max_ring = (self.envsize - 1) // 2
        
        for i, lidx in enumerate(rlayeridxs):
            inner = rlayeridxs[i + 1] if i + 1 < len(rlayeridxs) else max_ring + 1
            
            if inner - lidx < 2:
                raise ValueError(f"Ring {lidx} has no room for vulnerabilities")
            
            level = len(rlayeridxs) - i
            cells = tuple(self.coord_to_cell(x, y) for x, y in self.all_coords() if self.coord_to_rlayeridx(x, y) == lidx)
            wall = SMWall(level, cells, self.rng)
            self.sm_walls.append(wall)
            zone = [(x, y) for x, y in self.coords() if lidx < self.ring_of(x, y) < inner]
            self.sprinkle_vulns(wall, zone)
            
    def sprinkle_vulns(self, wall: SMWall, zone: list[tuple[int, int]]) -> None:
        placed = 0
        candidates = zone[:]
        
        self.rng.shuffle(candidates)
        for x, y in candidates:
            if placed >= wall.vuln_count: break
            
            cell = self.coord_to_cell(x, y)
            if cell.special_cell is not None:
                continue
            
            cell.special_cell = Vulnerability(wall=wall)
            placed += 1
            
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    cellic = self.coord_to_cell(nx, ny)
                    
                    if self.coord_in_bounds(nx, ny) and cellic.special_cell is None:
                        cellic.special_cell = VulnerabilitySterileZone()
        
        if placed < wall.vuln_count:
            raise ValueError("Zone too small for this wall's vulnerabilities")