import os
import types
import unittest

# Headless-safe pygame before importing app controllers
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.app_frame_controller import _build_ctx  # noqa: E402
from controllers.app_state import AppState  # noqa: E402


class TestAppStateSync(unittest.TestCase):
    """Typed-state bridge tests (semantic split plan, Phase 1)."""

    def test_sync_from_locals_seeds_substates(self):
        st = AppState()
        ns = {"panel_collapsed": True, "tool_mode": "select", "strokes": []}
        st.sync_from_locals(ns)
        self.assertTrue(st.viewport.panel_collapsed)
        self.assertEqual(st.tools.tool_mode, "select")
        self.assertEqual(st.document.strokes, [])

    def test_to_locals_dict_roundtrip_covers_all_typed_fields(self):
        st = AppState()
        st.viewport.panel_collapsed = True
        st.viewport.zoom = 2.5
        st.tools.tool_mode = "select"
        d = st.to_locals_dict()
        # Every auto-derived typed field must round-trip through the bridge.
        for f in st._SYNC_FIELDS:
            self.assertIn(f, d, f"missing typed field in bridge output: {f}")
        self.assertTrue(d["panel_collapsed"])
        self.assertEqual(d["zoom"], 2.5)
        self.assertEqual(d["tool_mode"], "select")

    def test_viewport_substate_defaults(self):
        st = AppState()
        vp = st.viewport
        self.assertEqual(vp.width, 1400)
        self.assertEqual(vp.height, 900)
        self.assertEqual(vp.canvas_x, 0)
        self.assertEqual(vp.canvas_w, 0)
        self.assertEqual(vp.panel_x, 0)
        self.assertFalse(vp.panel_collapsed)
        self.assertEqual(vp.zoom, 1.0)
        self.assertEqual(vp.pan_x, 0.0)
        self.assertEqual(vp.pan_y, 0.0)

    def test_document_state_sync_from_locals(self):
        st = AppState()
        ns = {
            "strokes": [{"pts": [(0, 0), (1, 1)]}],
            "shape_states": {"s1": {"name": "x"}},
            "artboards": [],
            "active_artboard": -1,
            "symbols": {},
            "document_path": None,
            "clipboard_strokes": [],
            "undo_stack": [],
            "redo_stack": [],
            "max_undo": 100,
        }
        st.sync_from_locals(ns)
        self.assertEqual(st.document.strokes, [{"pts": [(0, 0), (1, 1)]}])
        self.assertEqual(st.document.shape_states, {"s1": {"name": "x"}})
        self.assertEqual(st.document.artboards, [])
        self.assertEqual(st.document.active_artboard, -1)
        self.assertEqual(st.document.symbols, {})
        self.assertIsNone(st.document.document_path)
        self.assertEqual(st.document.clipboard_strokes, [])
        self.assertEqual(st.document.undo_stack, [])
        self.assertEqual(st.document.redo_stack, [])
        self.assertEqual(st.document.max_undo, 100)

    def test_history_flows_through_typed_document_state(self):
        from controllers.history_controller import push_undo, do_undo, do_redo
        st = AppState()
        st.document.strokes = [{"pts": [(0, 0), (1, 1)]}]
        push_undo(st.document.undo_stack, st.document.redo_stack, st.document.strokes, st.document.max_undo)
        st.document.strokes.append({"pts": [(2, 2)]})
        self.assertTrue(do_undo(st.document.undo_stack, st.document.redo_stack, st.document.strokes))
        self.assertEqual(st.document.strokes, [{"pts": [(0, 0), (1, 1)]}])
        self.assertTrue(do_redo(st.document.undo_stack, st.document.redo_stack, st.document.strokes))
        # redo restores the pre-undo state (original + appended stroke).
        self.assertEqual(st.document.strokes, [{"pts": [(0, 0), (1, 1)]}, {"pts": [(2, 2)]}])


    def test_typed_state_is_authoritative_at_dispatch(self):
        st = AppState()
        st.sync_from_locals({"tool_mode": "draw"})
        st.tools.tool_mode = "select"  # typed-owned change
        frame = types.SimpleNamespace(f_globals={})
        loc = {"app_state": st, "tool_mode": "draw"}
        ctx = _build_ctx(frame, loc)
        self.assertEqual(ctx.tool_mode, "select")


if __name__ == "__main__":
    unittest.main()
