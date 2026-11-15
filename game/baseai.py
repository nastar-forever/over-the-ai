import math

from abc import ABC, abstractmethod
from typing import Literal, Any
from dataclasses import dataclass

from game._base import _Environment
import game.cells as cells

@dataclass
class DecisionToken:
    direction: tuple[Literal[-1, 0, 1], Literal[-1, 0, 1]]
    mode: Literal["walk", "dash"]
    distance: int # Will only be used when mode == walk

@dataclass
class Inable:
    pass

class BaseAI(ABC):
    def __init__(self):
        self.x = 0
        self.y = 0
        self.max_walk_steps = 1
    
    @abstractmethod
    def space_parse(self, space: list[cells.Cell], env: _Environment): ...
    
    @abstractmethod
    def decide(self, parsed_space) -> DecisionToken|Inable: ...