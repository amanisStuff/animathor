import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.app_state import AppState, DocumentState, DragState, SelectionState, ToolState, UiCacheState  # noqa: E402
from controllers.bucket_controller import pick, set_color  # noqa: E402
from controllers import bezier_pen_controller as bp  # noqa: E402
from controllers import text_entry_controller as text_entry  # noqa: E402
from controllers import transform_field_controller as xform  # noqa: E402
from controllers.selection.eyedropper import eyedropper_hit  # noqa: E402


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _hsv(h, s, v):
    return (h / 360.0, s, v, 1.0)


def _rgb(*c):
    return (c[0] * 360.0, c[1], c[2])


class _Rect:
    x, y, w, h = 10, 20, 100, 50


class TestTypedBucketController(unittest.TestCase):
    """Phase 1: bucket helpers operate on typed state, no ctx bag."""

    def test_pick_updates_typed_tools_and_state(self):
        tools = ToolState()
        state = {}
        pick(tools, _Rect(), (59.5, 20), "sv", state, _clamp, _hsv)
        self.assertAlmostEqual(tools.bucket_picker_s, 0.5)
        self.assertEqual(tools.bucket_picker_v, 1.0)
        self.assertEqual(state["bucket_picker_drag"], "sv")
        self.assertEqual(state["bucket_fill_color"], tools.bucket_fill_color)

    def test_set_color_updates_typed_tools(self):
        tools = ToolState()
        state = {}
        set_color(tools, (0.5, 0.25, 0.75), state, _rgb)
        self.assertEqual(tools.bucket_fill_color, (0.5, 0.25, 0.75))
        self.assertEqual(state["bucket_fill_color"], (0.5, 0.25, 0.75))

    def test_text_commit_uses_typed_substates(self):
        doc = DocumentState()
        sel = SelectionState()
        ui = UiCacheState()
        ui.text_entry = {"x": 1, "y": 2, "text": "hello", "family": "Sans", "size": 12}
        calls = []
        result = text_entry.commit(
            sel, doc, ui,
            lambda: calls.append("undo"),
            lambda h, s, v: (h, s, v, 1.0),
            lambda text, x, y, family, size, color=None: {"text": text},
        )
        self.assertTrue(result)
        self.assertEqual(len(doc.strokes), 1)
        self.assertEqual(sel.selected_strokes, {0})
        self.assertIsNone(ui.text_entry)
        self.assertEqual(calls, ["undo"])

    def test_bezier_anchor_and_finish_on_typed_state(self):
        tools = ToolState()
        doc = DocumentState()
        sel = SelectionState()
        bp.add_anchor(tools, (0, 0))
        bp.add_anchor(tools, (10, 10))
        self.assertEqual(len(tools.bezier_pen["anchors"]), 2)
        self.assertTrue(bp.near_first(tools, (1, 1), radius=2))
        bp.update_drag(tools, (5, 5))
        done = bp.finish(tools, doc, sel, lambda: None,
                         lambda segs, algorithm: {"segs": segs},
                         lambda s: s, lambda strokes: strokes)
        self.assertTrue(done)
        self.assertEqual(len(doc.strokes), 1)
        self.assertIsNone(tools.bezier_pen)

    def test_xform_value_from_typed_state(self):
        sel = SelectionState()
        sel.selected_strokes = {0}
        doc = DocumentState()
        doc.strokes = [{"x": 0}]
        bbox = lambda strokes, indices: (5.0, 6.0, 15.0, 26.0)
        self.assertEqual(xform.current_value(sel, doc, "x", bbox), 5.0)
        self.assertEqual(xform.current_value(sel, doc, "w", bbox), 10.0)


    def test_eyedropper_typed_contract_miss_keeps_pick_mode(self):
        tools = ToolState()
        tools.eyedropper_pick = True
        state = {}
        result = eyedropper_hit(
            tools, DocumentState(), SelectionState(), state,
            types.SimpleNamespace(pos=(0, 0)),
            lambda p: p, lambda stroke: [], lambda *a: None, lambda: None,
        )
        self.assertEqual(result, 'handled')
        self.assertTrue(tools.eyedropper_pick)


    def test_guide_commit_typed_clears_drag(self):
        from controllers.commit.guide_commit import commit_guide_drag_typed
        drag = DragState()
        drag.guide_drag = {"index": 0}
        drag.guides = [{"axis": "x", "pos": 10}]
        self.assertEqual(commit_guide_drag_typed(drag, (0, 0), 18, 34), 'continue')
        self.assertIsNone(drag.guide_drag)
        self.assertEqual(drag.guides, [])

    def test_cutter_commit_typed_noop_when_inactive(self):
        from controllers.commit.cutter_commit import commit_cutter_typed
        self.assertIsNone(commit_cutter_typed(
            DragState(), DocumentState(), SelectionState(), ToolState(), {},
            types.SimpleNamespace(pos=(0, 0)), lambda p: p, lambda: None,
        ))

    def test_marquee_commit_typed_noop_when_inactive(self):
        from controllers.commit.selection_commit import commit_marquee_typed
        self.assertIsNone(commit_marquee_typed(
            DragState(), SelectionState(), DocumentState(), ToolState(),
            lambda *a: (0, 0, 0, 0), lambda s: (0, 0, 0, 0),
        ))

    def test_redraw_commit_typed_noop_when_inactive(self):
        import types
        from controllers.commit.redraw_commit import commit_redraw_curve_typed
        self.assertIsNone(commit_redraw_curve_typed(
            DragState(), DocumentState(), types.SimpleNamespace(pos=(0, 0)),
            lambda p: p, lambda: 10, lambda: None,
        ))

    def test_bezier_pen_commit_typed_releases_handle(self):
        from controllers.commit.bezier_pen_commit import commit_bezier_pen_mouseup_typed
        tools = ToolState()
        tools.draw_shape = "pen"
        tools.bezier_pen = {"anchors": [], "mouse_down": True, "dragging": True}
        self.assertEqual(
            commit_bezier_pen_mouseup_typed(tools, lambda close_path: None), 'continue')
        self.assertFalse(tools.bezier_pen["mouse_down"])
        self.assertFalse(tools.bezier_pen["dragging"])

    def test_draw_commit_typed_noop_when_inactive(self):
        import types
        from controllers.commit.draw_commit import commit_draw_typed
        self.assertIsNone(commit_draw_typed(
            DragState(), DocumentState(), SelectionState(), ToolState(),
            types.SimpleNamespace(pos=(0, 0)),
            lambda p: p, lambda: 10, lambda: None, lambda *a, **k: {},
            lambda strokes: strokes, lambda s: s,
        ))

    def test_color_target_typed_noop_without_selection(self):
        import types
        from controllers.panel.color_target import color_target_hit
        self.assertFalse(color_target_hit(
            UiCacheState(), SelectionState(), DocumentState(), {},
            types.SimpleNamespace(pos=(0, 0)), False, None, lambda s: [], (),
        ))

    def test_fill_picker_typed_entry_short_circuits(self):
        from controllers.panel.fill_picker import fill_picker_hit
        calls = []
        def first(ctx, event):
            calls.append('first')
            return True
        def second(ctx, event):
            calls.append('second')
            return True
        result = fill_picker_hit(
            ToolState(), DocumentState(), SelectionState(), UiCacheState(),
            {}, object(), None, (first, second),
        )
        self.assertTrue(result)
        self.assertEqual(calls, ['first'])

    def test_effects_wave_typed_entry_short_circuits(self):
        from controllers.panel.effects_wave import effects_wave_hit
        calls = []
        def first(ctx, event):
            calls.append('first')
            return True
        result = effects_wave_hit(
            ToolState(), DocumentState(), SelectionState(), UiCacheState(),
            {}, object(), None, (first, lambda c, e: calls.append('second')),
        )
        self.assertTrue(result)
        self.assertEqual(calls, ['first'])

    def test_remaining_panel_typed_entries(self):
        from controllers.panel.gradient_stops import gradient_stops_hit
        from controllers.panel.transform_inspector import transform_inspector_hit
        from controllers.panel.tool_options import tool_options_hit
        called = []
        def hit(ctx, event):
            called.append('hit')
            return True
        for entry in (gradient_stops_hit, transform_inspector_hit, tool_options_hit):
            self.assertTrue(entry(
                ToolState(), DocumentState(), SelectionState(), UiCacheState(),
                {}, object(), None, (hit,),
            ))
        self.assertEqual(called, ['hit', 'hit', 'hit'])


if __name__ == "__main__":
    unittest.main()
