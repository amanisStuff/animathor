import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.panel import dispatch  # noqa: E402
from panel_rects import domain_of, publish_rect  # noqa: E402
from controllers.panel.rects import PanelRects, rects_from_state, hit_rect  # noqa: E402


class TestPanelDomainDispatch(unittest.TestCase):
    """Phase 3: panel clicks dispatch through ordered semantic domains."""

    def test_default_domain_order(self):
        self.assertEqual(
            [fn.__name__ for fn in dispatch.DOMAIN_HANDLERS],
            ["tool_options", "fill_picker", "gradient_stops"],
        )

    def test_first_handling_domain_wins(self):
        calls = []

        def tool_options(ctx, event):
            calls.append("tool_options")
            return None

        def fill_picker(ctx, event):
            calls.append("fill_picker")
            return "continue"

        def gradient_stops(ctx, event):
            calls.append("gradient_stops")
            return None

        original = dispatch.DOMAIN_HANDLERS
        try:
            dispatch.DOMAIN_HANDLERS = (tool_options, fill_picker, gradient_stops)
            self.assertEqual(dispatch.handle_panel_click(None, None), "continue")
            self.assertEqual(calls, ["tool_options", "fill_picker"])
        finally:
            dispatch.DOMAIN_HANDLERS = original


class TestPanelRects(unittest.TestCase):
    """Shared typed rect contract between view producers and domain hit handlers."""

    def test_ui_frame_output_typed(self):
        from views.panel_state import UiFrameOutput
        alpha = object()
        out = UiFrameOutput.from_state(
            {"alpha_rect": alpha, "panel_width": 400, "panel_height": 300})
        self.assertIs(out.rects.get("alpha_rect"), alpha)
        self.assertEqual((out.width, out.height), (400, 300))

    def test_get_set(self):
        r = PanelRects()
        r.set("stroke_swatch_rects", [1, 2, 3])
        self.assertEqual(r.get("stroke_swatch_rects"), [1, 2, 3])
        self.assertIsNone(r.get("missing"))

    def test_update_from_state_filters_rect_keys(self):
        state = {"tool_mode": "draw", "stroke_swatch_rect": "S", "fill_stop_rects": "F"}
        r = rects_from_state(state)
        self.assertEqual(r.rects, {"stroke_swatch_rect": "S", "fill_stop_rects": "F"})

    def test_hit_rect_resolves_through_contract(self):
        ctx = types.SimpleNamespace(state={"alpha_rect": "A"})
        self.assertEqual(hit_rect(ctx, "alpha_rect", "D"), "A")
        self.assertEqual(hit_rect(ctx, "missing_rect", "D"), "D")

    def test_rect_domain_schema_and_publication(self):
        self.assertEqual(domain_of("alpha_rect"), "fill_picker")
        self.assertEqual(domain_of("xform_x_rect"), "transform_inspector")
        self.assertIsNone(domain_of("unknown_rect"))
        state = {}
        publish_rect(state, "alpha_rect", "R")
        self.assertEqual(hit_rect(types.SimpleNamespace(state=state), "alpha_rect"), "R")


if __name__ == "__main__":
    unittest.main()
