import os
import types
import unittest

# Headless-safe pygame before importing app controllers
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.dispatch_context import DispatchContext  # noqa: E402
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
        fields = {**frame.f_globals, **loc, **st.to_locals_dict()}
        ctx = DispatchContext(st, fields)
        self.assertEqual(ctx.tool_mode, "select")

    def test_narrow_sync_does_not_clobber_typed_fields(self):
        st = AppState()
        st.tools.tool_mode = "select"
        st.sync_from_locals(
            {"tool_mode": "draw", "selected_strokes": {1}},
            fields={"selected_strokes"},
        )
        self.assertEqual(st.tools.tool_mode, "select")
        self.assertEqual(st.selection.selected_strokes, {1})

    def test_extended_tool_and_drag_fields_sync(self):
        st = AppState()
        ns = {
            "max_points_per_curve": 8,
            "rect_variant": "square",
            "cut_gap": 4,
            "guides": [{"axis": "x", "pos": 10}],
            "pivot_pos": (1.0, 2.0),
            "prev_selection_set": {1},
        }
        st.sync_from_locals(ns)
        self.assertEqual(st.tools.max_points_per_curve, 8)
        self.assertEqual(st.tools.rect_variant, "square")
        self.assertEqual(st.drag.cut_gap, 4)
        self.assertEqual(st.drag.guides, [{"axis": "x", "pos": 10}])
        self.assertEqual(st.drag.pivot_pos, (1.0, 2.0))
        self.assertEqual(st.selection.prev_selection_set, {1})


    def test_appstate_covers_main_rect_cache_locals(self):
        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "src", "controllers", "app_controller.py")
        with open(path, encoding="utf-8") as handle:
            src = handle.read()
        locals_rect = set(re.findall(
            r'^    ([a-z][a-z0-9_]*(?:_cache|_rects|_rect))\s*=', src, re.M))
        fields = set(AppState()._SYNC_FIELDS)
        self.assertEqual(locals_rect - fields, set(),
                         "rect-cache locals missing from typed AppState")

    def test_command_context_covers_menu_action_fields(self):
        import os
        import re
        import dataclasses
        from controllers.commands.context import CommandContext
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "src", "controllers", "app_controller.py")
        with open(path, encoding="utf-8") as handle:
            src = handle.read()
        start = src.index("s = CommandContext(")
        end = src.index("result = _menu_dispatch.run_menu_action", start)
        used = set(re.findall(r"^\s+([a-z_][A-Za-z0-9_]*)\s*=", src[start:end], re.M))
        fields = {f.name for f in dataclasses.fields(CommandContext)}
        self.assertEqual(used - fields, set(),
                         "run_menu_action kwargs missing from CommandContext")

    def test_dispatch_context_writes_typed_state(self):
        from controllers.dispatch_context import DispatchContext
        st = AppState()
        ctx = DispatchContext(st, {"tool_mode": "draw", "service_value": 1})
        ctx.tool_mode = "select"
        self.assertEqual(st.tools.tool_mode, "select")
        ctx.service_value = 2
        self.assertEqual(ctx.service_value, 2)


if __name__ == "__main__":
    unittest.main()
