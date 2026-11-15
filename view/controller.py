import environment
from environment import VERDICT_HOLD
from . import anim, widgets

class GameController:
    def __init__(self, make_env):
        self.make_env = make_env
        self.cfdata = anim.CrossFrameData()     # same object for the app's lifetime (ctx holds it)
        self.restart()

    def restart(self):
        self.env = self.make_env()
        self.player = anim.AnimationPlayer()
        self.cfdata.reset()

    @property
    def busy(self) -> bool:
        return not self.player.is_done()

    @property
    def input_locked(self) -> bool:
        e = self.env
        return self.busy or e.verdict != VERDICT_HOLD or not e.should_player_play()

    def apply(self, token: widgets.UIToken) -> None:
        if isinstance(token, widgets.ReplayRequest):
            self.restart()
            return
        
        if self.input_locked:
            return
        env = self.env

        
        match token:
            case widgets.PlayCardRequest(card_idx=i) if 0 <= i < len(env.fetched):
                env.play_card(env.fetched[i])
        
            case widgets.MergeRequest(idle_idx=a, over_idx=b):
                env.merge(a, b)
        
            case widgets.PlaceRequest(x=x, y=y):
                env.place(x, y)
        
            case widgets.RotateRequest(direction=d):
                t = env.active_placement
                if t:
                    {"cw": t.rot_cw, "ccw": t.rot_ccw, "flip": t.flip}[d]()
            
            case widgets.RerollRequest():
                env.reroll()
        
            case widgets.EndTurnRequest():
                env.end_turn()
                
            case widgets.CancelRequest():
                env.cancel_placement()

    def update(self, dt: float) -> None:
        env = self.env
        
        if env.verdict == VERDICT_HOLD and not self.busy and not env.should_player_play():
            env.aistep()
        self.player.push_events(env.drain(), env, self.cfdata)
        self.player.update(dt, self.cfdata)