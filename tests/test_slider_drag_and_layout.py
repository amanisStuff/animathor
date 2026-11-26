import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.font.init()

from controllers.app_state import AppState  # noqa: E402
from controllers.dispatch_context import DispatchContext  # noqa: E402
from controllers.drag.ui_session import UiDragSession, ui_drag_active  # noqa: E402
from controllers.event_loop import _call_handler  # noqa: E402
from controllers.panel.align_distribute import _handle_panel_click_a_p3  # noqa: E402
from controllers.panel.gradient_panel import _handle_panel_click_c  # noqa: E402
from models.appearance import get_appearance, set_appearance  # noqa: E402
from models.geometry import clamp  # noqa: E402
from views.panel_domain_color import render_no_selection_state  # noqa: E402
from views.widgets import make_fonts  # noqa: E402

OPACITY_RECT = pygame.Rect(100, 100, 200, 12)


class TestSliderDragSync(unittest.TestCase):
    def _make_opacity_ctx(self):
        app_state = AppState()
        app_state.tools.tool_mode = "selection"
        app_state.selection.selection_submode = "transform"
        app_state.selection.selected_strokes = {0}
        app_state.document.strokes = [
            set_appearance({"stroke_color": (0.1, 0.1, 0.15, 1.0)}, opacity=1.0)
        ]
        state = {
            "obj_opacity_rect": OPACITY_RECT,
            "obj_opacity_drag": False,
        }
        fields = {
            "state": state,
            "event": types.SimpleNamespace(
                type=pygame.MOUSEBUTTONDOWN, button=1, pos=(150, 105)
            ),
            "push_undo": lambda: None,
            "clamp": clamp,
            "selected_strokes": {0},
            "strokes": app_state.document.strokes,
            "selection_submode": "transform",
            "reference_image": None,
            "guide_drag": None,
            "cutting": False,
            "pan_drag": None,
            "pivot_drag": None,
            "set_appearance": set_appearance,
            "wave_custom_drag": None,
            "wave_slider_drag": None,
            "picker_drag_sv": False,
            "picker_drag_hue": False,
            "picker_drag_alpha": False,
            "fill_stop_pos_drag": False,
            "ref_opacity_drag": False,
            "bucket_picker_drag": None,
            "selected_curve": None,
            "redrawing_curve": None,
            "marquee_select": None,
            "tool_mode": "selection",
            "draw_tool": "pen",
            "draw_shape": "pen",
            "bezier_pen": None,
            "drawing": False,
        }
        return DispatchContext(app_state, fields), app_state, state

    def test_real_opacity_click_activates_ui_drag(self):
        ctx, app_state, state = self._make_opacity_ctx()

        _call_handler(ctx, _handle_panel_click_a_p3)

        self.assertTrue(app_state.ui.obj_opacity_drag)
        self.assertTrue(state["obj_opacity_drag"])
        self.assertTrue(ctx.obj_opacity_drag)
        self.assertTrue(ui_drag_active(ctx))

    def test_real_opacity_click_does_not_jump_the_value(self):
        ctx, app_state, state = self._make_opacity_ctx()
        _call_handler(ctx, _handle_panel_click_a_p3)

        stroke = app_state.document.strokes[0]
        self.assertEqual(get_appearance(stroke)["opacity"], 1.0)
        self.assertEqual(state["obj_opacity_drag_start"], (150, 1.0))

    def test_ui_drag_motion_scrubs_opacity_from_click_position(self):
        ctx, app_state, _state = self._make_opacity_ctx()
        _call_handler(ctx, _handle_panel_click_a_p3)

        session = UiDragSession()
        session.begin(ctx, types.SimpleNamespace(pos=(150, 105)))
        self.assertTrue(session._active)

        session.move(ctx, types.SimpleNamespace(pos=(100, 105)))

        stroke = app_state.document.strokes[0]
        # 50px left across a 200px field => 0.25 below the click's 1.0 value.
        self.assertAlmostEqual(get_appearance(stroke)["opacity"], 0.75, places=4)


class TestEmptySelectionLayout(unittest.TestCase):
    def test_fill_tab_reserves_vertical_space(self):
        screen = pygame.Surface((1200, 800))
        fonts = make_fonts()
        state = {
            "color_target": "fill",
            "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0)],
            "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0)],
        }
        drawn = []

        y = render_no_selection_state(
            screen, fonts[1], state, 100, 100,
            lambda rect, label, **_kwargs: drawn.append(rect),
        )

        tab = state["tab_fill_rect"]
        self.assertEqual(len(drawn), 1)
        self.assertEqual(drawn[0], tab)
        self.assertGreater(tab.h, 0)
        self.assertGreaterEqual(y, tab.bottom)

    def test_fill_tab_click_sets_target_without_a_selection(self):
        app_state = AppState()
        app_state.tools.tool_mode = "selection"
        state = {"tab_fill_rect": pygame.Rect(100, 100, 120, 26)}
        ctx = DispatchContext(app_state, {"state": state})

        _handle_panel_click_c(ctx, types.SimpleNamespace(pos=(150, 110)))

        self.assertEqual(app_state.ui.color_target, "fill")
        self.assertEqual(state["color_target"], "fill")


if __name__ == "__main__":
    unittest.main()
