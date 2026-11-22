### CUSTOM LAYOUTS
import math
from dataclasses import dataclass, field

import nueu_view as view
from nueu_view import layout

@dataclass
class InvisRowLayout(layout.RowLayout):
    invisidx: int = field(init=False, default= -1)
    
    def positions(self):
        pos = super().positions()
        pos[self.invisidx][0] = 9999 # Hide it, lol
        return pos

@dataclass
class BentRowLayout(layout.UniformRowLayout):
    max_bend: int = 3
    jump: int = 20
    items_limit: int = field(default=4)
    activeidx: int = field(init=False, default=-1)
    invisidx: int = field(init=False, default=-1)

    def positions(self):
        pos = [list(p) for p in super().positions()]  # tuples are immutable
        if 0 <= self.activeidx < len(pos):
            a = math.radians(self.rotations()[self.activeidx])
            
            pos[self.activeidx][0] += -math.sin(a) * self.jump
            pos[self.activeidx][1] += -math.cos(a) * self.jump
        pos = [(round(x), round(y)) for x, y in pos]
        
        if 0 <= self.invisidx < len(pos):
            pos[self.invisidx][0] = 9999
        return pos

    def rotations(self):
        n = max(len(self.items), 1)
        deg_per_card = (self.max_bend * 2) / n
        return [-self.max_bend + deg_per_card * i for i in range(len(self.items))]