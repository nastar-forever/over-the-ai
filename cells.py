from __future__ import annotations

import random

from dataclasses import dataclass
from typing import ClassVar, Literal

@dataclass
class SpecialCell:
    priority: ClassVar[int] = 0

    def on_corrupted(self) -> None:
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
    wall: SMWall | None = None
    used: bool = False

    def on_corrupted(self) -> None:
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
    state: Literal["locked", "unexplored", "explored"] = "unexplored"
    special_cell: SpecialCell | None = None

    def step_on(self) -> None:
        if self.special_cell is not None:
            self.special_cell.on_corrupted()

    def get_priority(self) -> int:
        visible = self.state in ("locked", "explored")
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

    def register_vuln_exploit(self) -> None:
        self.vuln_count -= 1
        if self.vuln_count > 0: return
        
        for cell in self.cells:
            cell.state = "unexplored"
            cell.special_cell = cell.special_cell.child