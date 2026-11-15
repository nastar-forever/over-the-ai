from dataclasses import dataclass
from collections import deque
from typing import Literal
from enum import IntEnum

import cells as cells
from baseai import BaseAI, DecisionToken, Inable
from environment import Environment

class CellState(IntEnum):
    FREE = 0
    BLOCKED = 1

class PrioClass(IntEnum): # lower value = higher tier
    LURE = 0
    EXIT = 1
    FLAW = 2

KIND_BY_TYPE = {
    cells.FakeRewards: PrioClass.LURE,
    cells.Exit: PrioClass.EXIT,
    cells.Vulnerability: PrioClass.FLAW,
}

@dataclass
class NeighbourToken:
    mode: Literal["walk", "dash"]
    direction: tuple[int, int]
    swept: list[tuple[int, int]]
    
    @property
    def end(self): return self.swept[-1]

@dataclass
class TargetToken:
    x: int
    y: int
    kind: PrioClass

class BFSAI(BaseAI):
    def space_parse(self, space, env: Environment) -> tuple[list[list[CellState]], list[TargetToken]]:
        n = env.envsize
        grid = [[CellState.FREE] * n for _ in range(n)]
        targets = []

        for i, cell in enumerate(space):
            y, x = divmod(i, n)

            if not env.is_passable(cell):
                grid[y][x] = CellState.BLOCKED
                continue

            sc = cell.special_cell
            kind = KIND_BY_TYPE.get(type(sc))
            
            if kind is None:
                continue
            if kind is PrioClass.LURE and sc.used:
                continue
            if isinstance(sc, cells.Vulnerability) and sc.used:
                continue

            targets.append(TargetToken(x, y, kind))

        return grid, targets
    
    
    def get_neighbours(self, pos, grid) -> list[NeighbourToken]:
        neighbours = []
        h, w = len(grid), len(grid[0])
        dirs = [(1, 0), (0, 1), (-1, 0), (0, -1)] # (dx, dy)

        for dx, dy in dirs:
            swept = []
            i = 0
            
            while True:
                i += 1
                nx, ny = pos[0] + i * dx, pos[1] + i * dy

                if not (0 <= nx < w and 0 <= ny < h) or grid[ny][nx] == CellState.BLOCKED:
                    if swept:                        # travelled at least one cell
                        neighbours.append(NeighbourToken("dash", (dx, dy), swept.copy()))
                    break

                swept.append((nx, ny))
                if i <= self.max_walk_steps:
                    neighbours.append(NeighbourToken("walk", (dx, dy), swept.copy()))
        return neighbours
    
    
    def calc_bfs_path(self, start: tuple[int, int], goals: list[TargetToken], grid: list[list[CellState]]) -> list[NeighbourToken]|None:
        goal_set = {(t.x, t.y) for t in goals}
        queue = deque([start])
        parents = {start: None}
        
        while queue:
            pos = queue.popleft()
            
            for token in self.get_neighbours(pos, grid):
                if any(cell in goal_set for cell in token.swept):
                    moves = [token]
                    curr = pos
                    
                    while parents[curr] is not None:
                        prev, t = parents[curr]
                        moves.append(t)
                        curr = prev
                    moves.reverse()
                    return moves
                
                if token.end in parents:
                    continue
                
                parents[token.end] = (pos, token)
                queue.append(token.end)
        return None
    
    
    def decide(self, parsed_space: tuple[list[list[CellState]], list[TargetToken]]) -> DecisionToken|Inable:
        grid, targets = parsed_space
        start = (self.x, self.y)
        
        for tier in PrioClass:
            tier_targets = [t for t in targets if t.kind == tier]
            if not tier_targets:
                continue
            
            moves = self.calc_bfs_path(start, tier_targets, grid)
            if moves is None:
                continue
            
            first = moves[0]
            return DecisionToken(first.direction, first.mode, len(first.swept))
        return Inable()