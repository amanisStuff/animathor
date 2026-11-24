import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()

from controllers.drag.bezier_session import BezierPenSession  # noqa: E402
from controllers.drag.ui_session import (  # noqa: E402
    UiDragSession,
    _UI_DRAG_FLAGS,
    ui_drag_active,
)


class TestDragSessions(unittest.TestCase):
    """Phase 4: sessions own drag lifecycle state (setup/cleanup)."""

    def setUp(self):
        pygame.init()

    def test_ui_session_owns_flag_cleanup(self):
        ctx = types.SimpleNamespace(state={})
        for k in _UI_DRAG_FLAGS:
            setattr(ctx, k, "active" if k in ("bucket_picker_drag", "wave_slider_drag") else True)
        self.assertTrue(ui_drag_active(ctx))
        session = UiDragSession()
        self.assertTrue(session.end(ctx, None))
        self.assertFalse(ui_drag_active(ctx))
        for k in _UI_DRAG_FLAGS:
            value = getattr(ctx, k)
            if k in ("bucket_picker_drag", "wave_slider_drag"):
                self.assertIsNone(value)
            else:
                self.assertFalse(bool(value))
        for k in ("obj_opacity_drag", "picker_drag_sv", "picker_drag_hue",
                  "picker_drag_alpha", "fill_stop_pos_drag"):
            self.assertFalse(ctx.state[k])

    def test_bezier_applies_encapsulates_tool_condition(self):
        ctx = types.SimpleNamespace(tool_mode="draw", draw_tool="pen",
                                    draw_shape="pen", bezier_pen={})
        self.assertTrue(BezierPenSession.applies(ctx))
        ctx.draw_tool = "eraser"
        self.assertFalse(BezierPenSession.applies(ctx))
        ctx.draw_tool, ctx.bezier_pen = "pen", None
        self.assertFalse(BezierPenSession.applies(ctx))

    def test_bezier_begin_places_anchor(self):
        added = []
        ctx = types.SimpleNamespace(
            clamp_to_canvas=lambda p: p,
            draw_snap_point=lambda c, s, r, sh: None,
            snap_world=lambda p: p,
            snap_radius=lambda: 10,
            strokes=[],
            bezier_pen=None,
            drawing=True,
            current_points=[(1, 1)],
            _bezier_last_click={"time": 0, "pos": (1e9, 1e9)},
            _bezier_pen_near_first=lambda *a: False,
            _bezier_pen_add_anchor=lambda p: added.append(p),
            _bezier_pen_finish=lambda close_path=False: None,
        )
        event = types.SimpleNamespace(pos=(4, 5))
        BezierPenSession().begin(ctx, event)
        self.assertEqual(added, [(4, 5)])
        self.assertFalse(ctx.drawing)
        self.assertEqual(ctx.current_points, [])
        self.assertEqual(ctx._bezier_last_click["pos"], (4, 5))

    def test_transform_end_owns_toggle(self):
        ctx = types.SimpleNamespace(
            pan_drag=None, pivot_drag="P", pending_transform_toggle={"moved": False},
            tool_mode="selection", selection_submode="transform",
            selected_strokes={1}, transform_handle_mode="scale",
            transform_drag="T", gradient_drag="G",
        )
        from controllers.drag.transform_session import TransformDragSession
        self.assertTrue(TransformDragSession().end(ctx, None))
        self.assertEqual(ctx.transform_handle_mode, "rotate")
        self.assertIsNone(ctx.pending_transform_toggle)
        self.assertIsNone(ctx.transform_drag)
        self.assertIsNone(ctx.gradient_drag)


if __name__ == "__main__":
    unittest.main()
