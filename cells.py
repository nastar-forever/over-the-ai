from __future__ import annotations

import random

from dataclasses import dataclass
from typing import ClassVar, Literal, Callable

@dataclass
class SCDestruct:
    pass

@dataclass
class SpecialCell:
    priority: ClassVar[int] = 0

    def on_corrupted(self) -> None|SCDestruct:
        pass


@dataclass
class SMWallCell(SpecialCell):
    level: int = 0
    child: SpecialCell | None = None

@dataclass
class Obstacle(SpecialCell):
    pass

@dataclass
class Vulnerability(SpecialCell):
    priority: ClassVar[int] = 1
    wall: SMWall | None = None
    used: bool = False

    def on_corrupted(self) -> None:
        if self.used or self.wall is None or not self.wall.active:
            return
        self.used = True
        self.wall.register_vuln_exploit()


@dataclass
class VulnerabilitySterileZone(SpecialCell):
    pass


@dataclass
class FakeRewards(SpecialCell):
    priority: ClassVar[int] = 3
    used: bool = False
    
    def on_corrupted(self):
        self.priority = 0
        used = True

@dataclass
class Exit(SpecialCell):
    priority: ClassVar[int] = 2


@dataclass
class Cell:
    state: Literal["locked", "unexplored", "explored"] = "unexplored"
    special_cell: SpecialCell | None = None

    def step_on(self) -> None:
        if self.special_cell is not None:
            res = self.special_cell.on_corrupted()
            
            if isinstance(res, SCDestruct):
                self.special_cell = None

    def get_priority(self) -> int:
        visible = self.state not in ("locked", "explored")
        return self.special_cell.priority if self.special_cell and visible else 0
    

class SMWall:
    def __init__(self, level: int, cells: tuple[Cell, ...], rng: random.Random | None = None):
        rng = rng or random.Random()
        self.level = level
        self.cells = cells
        
        for cell in cells:
            cell.special_cell = SMWallCell(level=level, child=cell.special_cell)
            cell.state = "locked"
        
        self.vuln_count = level * rng.randint(1, 2) + 1
        self.active = False
        self.outer: SMWall|None = None
        self.vuln_cells: list[Cell] = []
        self.on_collapse: Callable = lambda: None
    
    
    def activate(self):
        self.active = True
        for cell in self.vuln_cells:
            if cell.state == "locked" and not isinstance(cell.special_cell, SMWallCell):
                cell.state = "unexplored"


    def register_vuln_exploit(self) -> None:
        self.vuln_count -= 1
        if self.vuln_count > 0: return
        
        for cell in self.cells:
            sc = cell.special_cell
            cell.special_cell = sc.child
            
            future = isinstance(sc, Vulnerability) and sc.wall is not None and not sc.wall.active
            cell.state = "locked" if future else "unexplored"
            
        if self.outer is not None:
            self.outer.activate()
            
        self.on_collapse()