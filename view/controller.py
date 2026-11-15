import environment
from . import anim
from . import widgets
import cards

class GameController:
    def __init__(self, env: environment.Environment): 
        self.env = env
        self.anim = anim.Animation()
        self.cfdata = anim.CrossFrameData()
        self.ghost_token: cards.PlacementToken | None   # working copy, so rotation doesn't mutate the card's class-level token

    @property
    def input_locked(self) -> bool: ...

    def apply(self, token: widgets.UIToken) -> None: ...
    def update(self, dt: float) -> None: ...
        # if not should_player_play and not busy: env.aistep()
        # push env.drain_events() into the player, then anim.update(dt, cfdata)