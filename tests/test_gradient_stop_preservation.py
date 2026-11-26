import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from controllers.app_state import AppState  # noqa: E402
from controllers.dispatch_context import DispatchContext  # noqa: E402
from controllers.mouse_motion.wave_motion import color_picker_drag_move  # noqa: E402
from controllers.panel.gradient_panel import _handle_panel_click_c  # noqa: E402
from models.geometry import (  # noqa: E402
    clamp, color_alpha, get_fill_gradient, get_gradient_stop_color,
    get_gradient_stops, hsv_to_rgb, rgb_to_hsv, set_gradient_stop_color,
)
from models.strokes import _stroke_components  # noqa: E402

FIRST = (0.1, 0.2, 0.3, 1.0)
SECOND = (0.4, 0.5, 0.6, 1.0)
SWATCH = (0.9, 0.2, 0.3, 1.0)
EMPTY = pygame.Rect(0, 0, 0, 0)


def _gradient():
    return {
        "type": "linear",
        "angle": 0.0,
        "stops": [
            {"pos": 0.0, "color": list(FIRST)},
            {"pos": 1.0, "color": list(SECOND)},
        ],
    }


class TestGradientStopPreservation(unittest.TestCase):
    def _make_panel_ctx(self):
        app_state = AppState()
        app_state.tools.tool_mode = "selection"
        app_state.selection.selection_submode = "transform"
        app_state.selection.selected_strokes = {0}
        app_state.ui.color_target = "fill"
        stroke = {
            "fill_color": None,
            "fill_gradient": _gradient(),
            "stroke_color": (0.1, 0.1, 0.15, 1.0),
            "components": [{"stroke_color": (0.1, 0.1, 0.15, 1.0)}],
        }
        app_state.document.strokes = [stroke]
        state = {
            "tab_stroke_rect": EMPTY,
            "tab_fill_rect": EMPTY,
            "sv_rect": EMPTY,
            "hue_rect": EMPTY,
            "alpha_rect": EMPTY,
            "nofill_rect": EMPTY,
            "fill_stop_rects": {},
            "fill_swatch_rects": [pygame.Rect(100, 100, 20, 20)],
            "stroke_swatch_rects": [EMPTY],
            "fill_type_prev_rect": pygame.Rect(200, 100, 20, 20),
            "fill_type_next_rect": pygame.Rect(240, 100, 20, 20),
            "fill_gradient_stop": 1,
            "picker_h": 210.0,
            "picker_s": 0.5,
            "picker_v": 0.8,
        }
        fields = {
            "app_state": app_state,
            "state": state,
            "tool_mode": "selection",
            "selection_submode": "transform",
            "selected_strokes": {0},
            "selected_curve": None,
            "strokes": app_state.document.strokes,
            "color_target": "fill",
            "_stroke_components": _stroke_components,
            "clamp": clamp,
            "get_fill_gradient": get_fill_gradient,
            "rgb_to_hsv": rgb_to_hsv,
            "hsv_to_rgb": hsv_to_rgb,
            "STROKE_SWATCHES": [SWATCH],
        }
        return DispatchContext(app_state, fields), app_state, state

    def test_second_stop_swatch_updates_stop_without_collapsing_gradient(self):
        ctx, app_state, state = self._make_panel_ctx()

        _handle_panel_click_c(ctx, types.SimpleNamespace(pos=(105, 105)))

        stroke = app_state.document.strokes[0]
        self.assertIsNone(stroke["fill_color"])
        gradient = get_fill_gradient(stroke)
        self.assertIsNotNone(gradient)
        stops = get_gradient_stops(gradient)
        self.assertEqual(len(stops), 2)
        self.assertEqual(tuple(stops[0]["color"][:3]), FIRST[:3])
        self.assertEqual(tuple(stops[1]["color"][:3]), SWATCH[:3])
        self.assertEqual(state["fill_gradient_stop"], 1)

    def test_fill_type_cycle_keeps_edited_second_stop(self):
        ctx, app_state, _state = self._make_panel_ctx()
        _handle_panel_click_c(ctx, types.SimpleNamespace(pos=(105, 105)))

        _handle_panel_click_c(ctx, types.SimpleNamespace(pos=(245, 105)))

        stroke = app_state.document.strokes[0]
        gradient = get_fill_gradient(stroke)
        self.assertEqual(gradient["type"], "radial")
        stops = get_gradient_stops(gradient)
        self.assertEqual(tuple(stops[1]["color"][:3]), SWATCH[:3])

    def test_hue_drag_updates_second_stop_without_collapsing_gradient(self):
        stroke = {
            "fill_color": None,
            "fill_gradient": _gradient(),
            "stroke_color": (0.1, 0.1, 0.15, 1.0),
            "components": [{"stroke_color": (0.1, 0.1, 0.15, 1.0)}],
        }
        state = {
            "hue_rect": pygame.Rect(100, 220, 360, 20),
            "fill_gradient_stop": 1,
            "picker_h": 210.0,
            "picker_s": 0.5,
            "picker_v": 0.8,
        }
        ctx = types.SimpleNamespace(
            state=state,
            picker_drag_sv=False,
            picker_drag_hue=True,
            picker_drag_alpha=False,
            selected_strokes={0},
            selected_curve=None,
            selection_submode="transform",
            strokes=[stroke],
            color_target="fill",
            picker_h=210.0,
            picker_s=0.5,
            picker_v=0.8,
            clamp=clamp,
            hsv_to_rgb=hsv_to_rgb,
            color_alpha=color_alpha,
            get_fill_gradient=get_fill_gradient,
            get_gradient_stop_color=get_gradient_stop_color,
            set_gradient_stop_color=set_gradient_stop_color,
        )

        color_picker_drag_move(ctx, types.SimpleNamespace(pos=(280, 230)))

        self.assertIsNone(stroke["fill_color"])
        gradient = get_fill_gradient(stroke)
        self.assertIsNotNone(gradient)
        stops = get_gradient_stops(gradient)
        self.assertEqual(len(stops), 2)
        self.assertEqual(tuple(stops[0]["color"][:3]), FIRST[:3])
        self.assertNotEqual(tuple(stops[1]["color"][:3]), SECOND[:3])


if __name__ == "__main__":
    unittest.main()
