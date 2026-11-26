"""Regression coverage for canvas relayout on window resize."""

import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()

import config as cfg  # noqa: E402
from controllers.app_frame_controller import process_event_frame  # noqa: E402
from controllers.render.scene_state import canvas_surface_for_context  # noqa: E402
from views.canvas import make_cairo_surface  # noqa: E402


class _StubSlider:
    def handle_event(self, event):
        return False


class TestWindowResizeCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((cfg.WIDTH, cfg.HEIGHT), pygame.RESIZABLE)

    def setUp(self):
        self._layout = {
            name: getattr(cfg, name)
            for name in ("WIDTH", "HEIGHT", "CANVAS_X", "CANVAS_W", "PANEL_X")
        }

    def tearDown(self):
        for name, value in self._layout.items():
            setattr(cfg, name, value)
        pygame.event.clear()
        pygame.display.set_mode((cfg.WIDTH, cfg.HEIGHT), pygame.RESIZABLE)

    def test_videoresize_rebuilds_and_uses_larger_canvas_surface(self):
        old_surface = make_cairo_surface(cfg.CANVAS_W, cfg.canvas_viewport_height())
        holder = types.SimpleNamespace(surface=old_surface)
        loc = {
            "app_state": None,
            "cairo_surface": old_surface,
            "cairo_surface_holder": holder,
            "screen": pygame.display.get_surface(),
            "slider": _StubSlider(),
            "width_slider": _StubSlider(),
            "cut_gap_slider": _StubSlider(),
            "state": {},
            "tool_mode": "draw",
            "draw_tool": "pen",
            "curve_cut_mode": False,
            "selection_submode": "transform",
            "selected_strokes": set(),
            "running": True,
        }

        def relayout():
            cfg.CANVAS_X = cfg.LEFT_BAR_W
            cfg.CANVAS_W = max(200, cfg.WIDTH - cfg.LEFT_BAR_W - cfg.PANEL_W)
            cfg.PANEL_X = cfg.LEFT_BAR_W + cfg.CANVAS_W
            surface = make_cairo_surface(cfg.CANVAS_W, cfg.canvas_viewport_height())
            loc["cairo_surface"] = surface
            holder.surface = surface
            return surface

        loc["relayout"] = relayout

        pygame.event.clear()
        pygame.event.post(pygame.event.Event(
            pygame.VIDEORESIZE,
            {"size": (1600, 1000), "w": 1600, "h": 1000},
        ))
        process_event_frame(frame_locals=loc)

        expected_w = 1600 - cfg.LEFT_BAR_W - cfg.PANEL_W
        expected_h = 1000 - cfg.TOP_BAR_H - cfg.BOTTOM_BAR_H

        self.assertEqual(cfg.WIDTH, 1600)
        self.assertEqual(cfg.HEIGHT, 1000)
        self.assertEqual(cfg.CANVAS_W, expected_w)
        self.assertEqual(holder.surface.get_width(), expected_w)
        self.assertEqual(holder.surface.get_height(), expected_h)
        self.assertEqual(loc["cairo_surface"].get_width(), expected_w)
        self.assertEqual(loc["cairo_surface"].get_height(), expected_h)

        ctx = types.SimpleNamespace(
            cairo_surface=old_surface, cairo_surface_holder=holder)
        self.assertIs(canvas_surface_for_context(ctx), holder.surface)

    def test_surface_helper_accepts_legacy_context(self):
        surface = make_cairo_surface(37, 19)
        ctx = types.SimpleNamespace(cairo_surface=surface)
        self.assertIs(canvas_surface_for_context(ctx), surface)


if __name__ == "__main__":
    unittest.main()
