from __future__ import annotations

from typing import Any, Literal, Callable, ClassVar
from dataclasses import dataclass

@dataclass
class PlacementToken:
    shape: list[list[bool]]
    type: Literal["obstacle", "flush"] = "obstacle"
    
    def rot_cw(self):
        pass
    
    def rot_ccw(self):
        pass
    
    def flip(self):
        pass
    

@dataclass
class TempModificationToken:
    target_attr: str
    target_val: Any|None
    target_op: Callable|None
    duration: int
    op_only_once: bool = True
    update_dur_on_recast: bool = True
    effective_since: int|None = None
    original_value: Any|None = None
    
    def __post_init__(self, original_value: Any):
        if self.target_val is None and self.target_op is None:
            raise ValueError(f"Must have at least target_val or target_op having a value")

@dataclass
class ActionToken:
    add_cards: list[Card] = []
    remove_cards: list[Card] = []
    do_placement: PlacementToken|None = None
    temporary_modifications: list[TempModificationToken] = []


@dataclass
class Card:
    card_category: ClassVar[Literal["placement", "information", "manipulation"]]
    used_in_recipes: ClassVar[list[list[Card]]] = [] #[if merged with card x, will produce cardy y]
    merging_partners: ClassVar[list[Card]] = []
    get_from_recipes_only: ClassVar[bool] = False
    
    def on_activation(self, bank: list[Card], fetched: list[Card]) -> ActionToken:
        return
    
    def on_merging(self, merge: Card) -> ActionToken:
        return
    
    def on_player_step(self, stepcount: int, max_stepcount: int) -> ActionToken:
        return
    
    def on_ai_step(self, aistepcount: int) -> ActionToken:
        return


@dataclass
class PlacementCard(Card):
    card_category = "placement"
    token: ClassVar[PlacementToken]
    
    def on_activation(self, _, __):
        return ActionToken(do_placement=self.token)
    
        
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