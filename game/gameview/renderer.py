import pygame
import nueu_view as view


class LiveScene(view.renderer.Scene):
    def update(self, delta: float) -> None:
        self._compose(delta)


class Overlay(view._base.PrimitiveRenderer):
    def __init__(self, draw):
        self._fn = draw

    def get(self):
        raise NotImplementedError("Overlay can't live inside a Layout")

    def _draw(self, parent_surface, origin):
        self._fn(parent_surface)