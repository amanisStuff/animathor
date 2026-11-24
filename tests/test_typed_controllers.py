import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.app_state import AppState, DocumentState, SelectionState, ToolState, UiCacheState  # noqa: E402
from controllers.bucket_controller import pick, set_color  # noqa: E402
from controllers import bezier_pen_controller as bp  # noqa: E402
from controllers import text_entry_controller as text_entry  # noqa: E402
from controllers import transform_field_controller as xform  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
