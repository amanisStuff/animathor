import os
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from controllers.app_frame_controller import process_event_frame  # noqa: E402
from controllers.app_state import AppState  # noqa: E402
from controllers.panel.tool_options import _handle_panel_click_a_p1  # noqa: E402


class _NoBoost:
    def hit(self, pos):
        return False


class TestPanelEventStateSync(unittest.TestCase):
    def _run_click(self, app_state, state, pos):
        event = types.SimpleNamespace(pos=pos)
        results = []

        def fake_process_events(ctx):
            results.append(_handle_panel_click_a_p1(ctx, event))

        loc = {
            "app_state": app_state,
            "state": state,
            "btn_boost": _NoBoost(),
        }
        with patch("controllers.event_loop.process_events", side_effect=fake_process_events):
            process_event_frame(frame_locals=loc)
        return results

    def test_draw_snap_toggle_survives_event_frame_sync(self):
        app_state = AppState()
        app_state.tools.tool_mode = "draw"
        self.assertTrue(app_state.tools.snap_enabled)

        results = self._run_click(
            app_state,
            {"snap_toggle_rect": pygame.Rect(100, 100, 20, 20)},
            (105, 105),
        )

        self.assertEqual(results, ["continue"])
        self.assertFalse(app_state.tools.snap_enabled)

    def test_selection_submode_click_survives_event_frame_sync(self):
        app_state = AppState()
        app_state.tools.tool_mode = "selection"
        self.assertEqual(app_state.selection.selection_submode, "transform")

        results = self._run_click(
            app_state,
            {"nodes_mode_next_rect": pygame.Rect(100, 100, 20, 20)},
            (105, 105),
        )

        self.assertEqual(results, ["continue"])
        self.assertEqual(app_state.selection.selection_submode, "nodes")

    def test_legacy_ctx_field_rebinding_still_reaches_typed_state(self):
        app_state = AppState()
        loc = {"app_state": app_state, "tool_mode": "draw"}

        def fake_process_events(ctx):
            ctx.tool_mode = "selection"

        with patch("controllers.event_loop.process_events", side_effect=fake_process_events):
            process_event_frame(frame_locals=loc)

        self.assertEqual(app_state.tools.tool_mode, "selection")
        self.assertEqual(loc["tool_mode"], "selection")


if __name__ == "__main__":
    unittest.main()
