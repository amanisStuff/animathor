import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from controllers.app_state import AppState  # noqa: E402
from controllers.dispatch_context import DispatchContext  # noqa: E402
from controllers.panel.color_panel import _handle_panel_click_b  # noqa: E402
from controllers.panel.gradient_panel import _handle_panel_click_c  # noqa: E402
from models.geometry import (  # noqa: E402
    clamp, get_fill_gradient, hsv_to_rgb, rgb_to_hsv,
)
from models.strokes import _stroke_components  # noqa: E402
from models.waves import (  # noqa: E402
    _get_distortion_style, _set_distortion_style, default_displacement_params,
    default_wave_params,
)


SWATCH = (0.9, 0.2, 0.3, 1.0)


def _empty_rect():
    return pygame.Rect(0, 0, 0, 0)


class TestFillColorPanelHits(unittest.TestCase):
    def _make_ctx(self, submode, selected_curve=None, fill_swatch_rect=None,
                  stroke_swatch_rect=None):
        app_state = AppState()
        app_state.tools.tool_mode = "selection"
        app_state.selection.selection_submode = submode
        app_state.selection.selected_strokes = {0}
        app_state.selection.selected_curve = selected_curve
        app_state.ui.color_target = "stroke" if selected_curve else "fill"
        app_state.document.strokes = [{
            "fill_color": (0.1, 0.2, 0.3, 1.0),
            "stroke_color": (0.1, 0.2, 0.3, 1.0),
            "components": [{"stroke_color": (0.1, 0.2, 0.3, 1.0)}],
        }]

        state = {
            "wave_active_index": 0,
            "tab_stroke_rect": _empty_rect(),
            "tab_fill_rect": _empty_rect(),
            "sv_rect": _empty_rect(),
            "hue_rect": _empty_rect(),
            "alpha_rect": _empty_rect(),
            "nofill_rect": _empty_rect(),
            "fill_stop_rects": {},
            "fill_swatch_rects": [fill_swatch_rect or _empty_rect()],
            "stroke_swatch_rects": [stroke_swatch_rect or _empty_rect()],
        }
        fields = {
            "app_state": app_state,
            "state": state,
            "tool_mode": "selection",
            "selection_submode": submode,
            "selected_strokes": {0},
            "selected_curve": selected_curve,
            "strokes": app_state.document.strokes,
            "color_target": app_state.ui.color_target,
            "wave_formula_focus": False,
            "_stroke_components": _stroke_components,
            "_get_distortion_style": _get_distortion_style,
            "_set_distortion_style": _set_distortion_style,
            "push_undo": lambda: None,
            "clamp": clamp,
            "get_fill_gradient": get_fill_gradient,
            "rgb_to_hsv": rgb_to_hsv,
            "hsv_to_rgb": hsv_to_rgb,
            "STROKE_SWATCHES": [SWATCH],
        }
        return DispatchContext(app_state, fields), app_state, state

    def test_color_click_in_curve_mode_reaches_part3_without_name_error(self):
        """The reported crash path must not raise before color handlers run."""
        rect = pygame.Rect(100, 100, 20, 20)
        ctx, app_state, state = self._make_ctx(
            "curve", selected_curve=(0, 0), stroke_swatch_rect=rect,
        )
        wave = default_wave_params()
        wave["enabled"] = True
        _set_distortion_style(
            app_state.document.strokes[0]["components"][0], wave, 0,
        )

        _handle_panel_click_b(ctx, types.SimpleNamespace(pos=(105, 105)))

        comp = app_state.document.strokes[0]["components"][0]
        self.assertEqual(tuple(comp["stroke_color"][:3]), SWATCH[:3])
        self.assertTrue(state["wave_active_index"] == 0)

    def test_wave_hit_toggle_in_curve_mode_updates_style(self):
        rect = pygame.Rect(200, 100, 20, 20)
        ctx, app_state, state = self._make_ctx("curve", selected_curve=(0, 0))
        wave = default_displacement_params()
        wave["enabled"] = True
        comp = app_state.document.strokes[0]["components"][0]
        _set_distortion_style(comp, wave, 0)
        comps = _stroke_components(app_state.document.strokes[0])
        self.assertTrue(comps[0]["styles"][0].get("affect_x", True))
        state["displacement_affect_rects"] = {"affect_x": rect}

        _handle_panel_click_b(ctx, types.SimpleNamespace(pos=(205, 105)))

        comps = _stroke_components(app_state.document.strokes[0])
        self.assertFalse(comps[0]["styles"][0].get("affect_x", True))

    def test_fill_swatch_in_transform_mode_sets_fill_color(self):
        rect = pygame.Rect(100, 100, 20, 20)
        ctx, app_state, _state = self._make_ctx(
            "transform", fill_swatch_rect=rect,
        )

        _handle_panel_click_c(ctx, types.SimpleNamespace(pos=(105, 105)))

        self.assertEqual(
            tuple(app_state.document.strokes[0]["fill_color"][:3]), SWATCH[:3],
        )


if __name__ == "__main__":
    unittest.main()
