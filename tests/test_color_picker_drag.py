import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from controllers.drag.ui_session import UiDragSession  # noqa: E402
from controllers.mouse_motion.wave_motion import color_picker_drag_move  # noqa: E402
from models.geometry import clamp, color_alpha, hsv_to_rgb  # noqa: E402


class TestColorPickerDrag(unittest.TestCase):
    def _make_ctx(self, **flags):
        state = {
            "color_target": "fill",
            "picker_h": 210.0,
            "picker_s": 0.5,
            "picker_v": 0.8,
            "sv_rect": pygame.Rect(100, 100, 200, 100),
            "hue_rect": pygame.Rect(100, 220, 360, 20),
            "alpha_rect": pygame.Rect(100, 260, 200, 20),
        }
        values = dict(
            state=state,
            selected_strokes={0},
            selected_curve=None,
            selection_submode="transform",
            strokes=[{"fill_color": (0.1, 0.2, 0.3, 1.0)}],
            color_target="fill",
            picker_drag_sv=False,
            picker_drag_hue=False,
            picker_drag_alpha=False,
            fill_stop_pos_drag=False,
            wave_custom_drag=None,
            wave_slider_drag=None,
            redrawing_curve=None,
            marquee_select=None,
            drawing=False,
            tool_mode="selection",
            guide_drag=None,
            cutting=False,
            pan_drag=None,
            pivot_drag=None,
            ref_opacity_drag=False,
            reference_image=None,
            obj_opacity_drag=False,
            bucket_picker_drag=None,
            ref_drag=None,
            clamp=clamp,
            hsv_to_rgb=hsv_to_rgb,
            color_alpha=color_alpha,
        )
        values.update(flags)
        return types.SimpleNamespace(**values)

    def test_sv_drag_through_ui_session_updates_picker_and_fill(self):
        ctx = self._make_ctx(picker_drag_sv=True)
        session = UiDragSession()
        session.begin(ctx, None)

        session.move(ctx, types.SimpleNamespace(pos=(200, 150)))

        self.assertAlmostEqual(ctx.state["picker_s"], 0.5, delta=0.01)
        self.assertAlmostEqual(ctx.state["picker_v"], 0.5, delta=0.01)
        self.assertEqual(ctx.state["picker_h"], 210.0)
        self.assertNotEqual(tuple(ctx.strokes[0]["fill_color"][:3]),
                            (0.1, 0.2, 0.3))

    def test_hue_drag_keeps_saturation_and_value(self):
        ctx = self._make_ctx(picker_drag_hue=True)

        color_picker_drag_move(ctx, types.SimpleNamespace(pos=(190, 230)))

        self.assertAlmostEqual(ctx.state["picker_h"], 90.0, delta=0.5)
        self.assertAlmostEqual(ctx.state["picker_s"], 0.5)
        self.assertAlmostEqual(ctx.state["picker_v"], 0.8)
        self.assertEqual(ctx.picker_h, ctx.state["picker_h"])


if __name__ == "__main__":
    unittest.main()
