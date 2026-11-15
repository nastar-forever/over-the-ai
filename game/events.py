from typing import Literal
from dataclasses import dataclass

import game.cards as cards

@dataclass
class GameEvent:
    pass

@dataclass
class AIMoved(GameEvent):
    ai_idx: int
    path: list[tuple[int, int]]
    mode: Literal["walk", "dash"]
    
@dataclass
class CellChanged(GameEvent):
    x: int
    y: int
    
@dataclass
class SMWallCollapsed(GameEvent):
    level: int
    cells: list[tuple[int, int]]
    
    
@dataclass
class FetchedChanged(GameEvent):
    fetched: list[cards.Card]
    bank: list[cards.Card]
    occassion: Literal["shuffled", "transferred", "used", "manip"]

@dataclass
class MergingHappened(GameEvent):
    fetched: list[cards.Card]
    idle: cards.Card
    over: cards.Card
    result: cards.Card

@dataclass
class Placement(GameEvent):
    token: cards.PlacementToken

@dataclass
class ModfierActivated(GameEvent):
    token: cards.TempModificationToken


@dataclass
class VerdictReached(GameEvent):
    verdict: int