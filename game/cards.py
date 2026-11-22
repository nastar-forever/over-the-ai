from __future__ import annotations

from typing import Any, Literal, Callable, ClassVar
from dataclasses import dataclass, field, replace

import cells

@dataclass
class PlacementToken:
    shape: list[list[bool]]
    type: Literal["obstacle", "flush"] = "obstacle"
    special_cell: cells.SpecialCell = cells.Obstacle
    
    def rot_cw(self):
        self.shape = [list(r) for r in zip(*self.shape[::-1])]
    
    def rot_ccw(self):
        self.shape = [list(r) for r in zip(*self.shape)][::-1]
    
    def flip(self):
        self.shape = [r[::-1] for r in self.shape]
    

@dataclass
class TempModificationToken:
    target_attr: str
    target_val: Any|None
    target_op: Callable|None
    duration: int
    op_only_once: bool = True
    update_dur_on_recast: bool = True
    effective_offset: int = 0
    effective_since: int|None = None
    original_value: Any|None = None
    
    def __post_init__(self):
        if self.target_val is None and self.target_op is None:
            raise ValueError(f"Must have at least target_val or target_op having a value")

@dataclass
class ActionToken:
    add_cards: list[Card] = field(default_factory=list)
    remove_cards: list[Card] = field(default_factory=list)
    do_placement: PlacementToken|None = None
    temporary_modifications: list[TempModificationToken] = field(default_factory=list)


@dataclass(eq=False)
class Card:
    card_category: ClassVar[Literal["placement", "information", "manipulation"]]
    used_in_recipes: ClassVar[list[list[Card]]] = [] #[if merged with card x, will produce cardy y]
    merging_partners: ClassVar[list[Card]] = []
    get_from_recipes_only: ClassVar[bool] = False
    
    def __post_init__(self): pass
    
    def on_activation(self, bank: list[Card], fetched: list[Card]) -> ActionToken:
        return
    
    def on_merging(self, merge: Card) -> ActionToken:
        return
    
    def on_player_step(self, total_playersteps: int, stepcount: int, max_stepcount: int) -> ActionToken:
        return
    
    def on_ai_step(self, aistepcount: int) -> ActionToken:
        return


@dataclass(eq=False)
class PlacementCard(Card):
    card_category = "placement"
    token: ClassVar[PlacementToken]
    
    def on_activation(self, _, __):
        t = self.token
        return ActionToken(do_placement=replace(t, shape=[r[:] for r in t.shape]))
    
        
class GreatWall(PlacementCard):
    get_from_recipes_only = True
    token = PlacementToken([[True, True, True, True, True, True]])
    
class Edge(PlacementCard):
    token = PlacementToken([
        [True, True, True],
        [True, False, False]
    ])
    
class Wall(PlacementCard):
    token = PlacementToken([[True, True, True]])
    
    def __post_init__(self):
        self.used_in_recipes = [[Stone, Edge], [Wall, GreatWall]]
        self.merging_partners = [Stone, Wall]

class Stone(PlacementCard):
    token = PlacementToken([[True]])
    
    def __post_init__(self):
        self.used_in_recipes = [[Stone, Wall], [Wall, Edge]]
        self.merging_partners = [Stone, Wall]

class Lure(PlacementCard):
    token = PlacementToken([[True]], special_cell=cells.FakeRewards)
    card_category = "manipulation"