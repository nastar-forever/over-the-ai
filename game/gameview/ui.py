import pygame
from dataclasses import dataclass, field

import nueu_view as view
from nueu_view import ui

@dataclass
class Button(ui.Widget):
    hoverfilter: view.asset.FilterArray
    clickfilter: view.asset.FilterArray
    idx: int
    trigger_pgevent: pygame.event.Event = field(init=False, default=[
        pygame.MOUSEBUTTONDOWN,
        pygame.MOUSEBUTTONUP
    ])
    
    def on_hover_enter(self, _):
        self.hoverfilter.mask[self.idx] = True
        self.hoverfilter.update()
    
    def on_hover_exit(self, _):
        self.hoverfilter.mask[self.idx] = False
        self.hoverfilter.update()
    
    def handle(self, pgevent):
        self.clickfilter.mask[self.idx] = pgevent == pygame.MOUSEBUTTONDOWN