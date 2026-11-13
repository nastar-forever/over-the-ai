from abc import ABC, abstractmethod
from typing import Literal, Any
from dataclasses import dataclass

import cells

@dataclass
class DecissionToken:
    direction: tuple[Literal[-1, 0, 1], Literal[-1, 0, 1]]
    mode: Literal["walk", "dash"]
    distance: int # Will only be used when mode == walk

class BaseAI(ABC):
    def __init__(self):
        self.x = 0
        self.y = 0
    
    @abstractmethod
    def space_parse(self, space: list[cells.Cell]): ...
    
    @abstractmethod
    def decide(self, parsed_space) -> DecissionToken: ...