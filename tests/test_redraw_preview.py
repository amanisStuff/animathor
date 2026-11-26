"""Regression coverage for the live curve-redraw preview."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()

import models as m  # noqa: E402
from views.canvas import make_cairo_surface  # noqa: E402
from views.canvas_extra3 import draw_scene, surface_to_pygame  # noqa: E402

PREVIEW_POINTS = [(23.0, 101.0), (57.0, 43.0), (97.0, 101.0)]
PROBE_PIXEL = (57, 43)


class TestRedrawPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def _render(self, points, for_export=False):
        surface = make_cairo_surface(140, 120)
        stroke = m.new_stroke([((23.0, 101.0), (40.0, 101.0),
                                (80.0, 101.0), (97.0, 101.0))])
        redrawing = {
            "stroke_idx": 0,
            "comp_idx": 0,
            "points": list(points or []),
            "started": True,
            "fixed_start": PREVIEW_POINTS[0],
            "fixed_end": PREVIEW_POINTS[-1],
        }
        draw_scene(
            surface, [stroke], active_stroke=list(points or []),
            redrawing_curve=redrawing, edit_mode=True,
            selection_submode="curve", selected_indices={0},
            selected_curve=(0, 0), view_zoom=1.0, view_pan=(0.0, 0.0),
            for_export=for_export,
        )
        return surface_to_pygame(surface)

    def test_redraw_points_are_drawn_over_template(self):
        with_preview = self._render(PREVIEW_POINTS)
        without_preview = self._render([])

        drawn = with_preview.get_at(PROBE_PIXEL)[:3]
        baseline = without_preview.get_at(PROBE_PIXEL)[:3]

        self.assertNotEqual(drawn, baseline)
        # EDITOR_ACCENT is orange; the template/selection colors are yellow/blue.
        self.assertGreater(drawn[0], 210)
        self.assertGreater(drawn[1], 80)
        self.assertLess(drawn[1], 160)
        self.assertLess(drawn[2], 80)

    def test_export_does_not_include_redraw_preview(self):
        with_points = self._render(PREVIEW_POINTS, for_export=True)
        without_points = self._render([], for_export=True)

        self.assertEqual(
            with_points.get_at(PROBE_PIXEL)[:3],
            without_points.get_at(PROBE_PIXEL)[:3],
        )


if __name__ == "__main__":
    unittest.main()
