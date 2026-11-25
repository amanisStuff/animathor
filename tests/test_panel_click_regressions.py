"""Regression tests for three runtime crashes in panel click/render paths.

Each test reproduces the exact state that produced the traceback and asserts the
call now completes. These paths are not covered by the existing suite: the panel
domain tests replace the real handlers with fakes, and the render tests always
supply ``selected_obj`` alongside ``selected_strokes``.
"""
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import pygame  # noqa: E402

import controllers.panel.gradient_stops as gradient_stops  # noqa: E402
from controllers.panel.gradient_panel import _handle_panel_click_c  # noqa: E402
from controllers.panel.transform_inspector import _handle_panel_click_a_p3  # noqa: E402
from views.panel_domain_color import render_color_section  # noqa: E402

_FAR = (10000, 10000)


class _Font:
    def render(self, *_args, **_kwargs):
        return pygame.Surface((10, 10))


class _Slider:
    def __init__(self):
        self.track = pygame.Rect(0, 0, 100, 10)
        self.width = 100
        self.value = 0
        self.min_v = 0
        self.max_v = 50

    def draw(self, _screen):
        pass


class TestPanelClickRegressions(unittest.TestCase):
    def test_no_rect_match_returns_none_without_unbound_matched(self):
        # _handle_panel_click_a_p3 assigned `_matched` only inside its branches;
        # a click hitting no rect raised UnboundLocalError at the final return.
        ctx = types.SimpleNamespace(
            tool_mode="selection",
            selection_submode="transform",
            selected_strokes=set(),
            state={},
        )
        self.assertIsNone(_handle_panel_click_a_p3(ctx, types.SimpleNamespace(pos=_FAR)))

    def test_render_color_section_without_selected_obj_does_not_crash(self):
        # `stroke` is None when sel_count > 0 but no selected_obj is resolvable;
        # line 149 called `stroke.get(...)` unguarded -> AttributeError.
        out = render_color_section(
            pygame.Surface((400, 600)),
            (_Font(), _Font(), _Font()),
            (0, 0),
            {"width_slider": _Slider()},
            0,
            0,
            lambda *_a, **_k: None,
            lambda *_a, **_k: None,
            [],
            {0},
            1,
            "transform",
            None,
        )
        self.assertIsInstance(out, dict)
        self.assertEqual(out["eff_sw"], 3.0)

    def test_gradient_panel_reaches_real_handler_imports(self):
        # gradient_panel imported the gradient handler aliases from fill_picker,
        # where they do not exist -> ImportError on that click path.
        state = {
            "tab_stroke_rect": pygame.Rect(0, 0, 0, 0),
            "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
            "nofill_rect": pygame.Rect(0, 0, 0, 0),
            "sv_rect": pygame.Rect(0, 0, 0, 0),
            "hue_rect": pygame.Rect(0, 0, 0, 0),
            "alpha_rect": pygame.Rect(0, 0, 0, 0),
            "stroke_swatch_rects": [],
            "fill_swatch_rects": [],
        }
        ctx = types.SimpleNamespace(
            tool_mode="selection",
            selection_submode="transform",
            selected_strokes={0},
            selected_curve=None,
            color_target="stroke",
            strokes=[{}],
            state=state,
            _stroke_components=lambda _s: [],
            STROKE_SWATCHES=[],
            FILL_SWATCHES=[],
        )
        with mock.patch.object(
            gradient_stops, "handle_fill_tabs_and_type", return_value=False
        ) as spy:
            _handle_panel_click_c(ctx, types.SimpleNamespace(pos=_FAR))
            spy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
