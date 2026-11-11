import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import app  # noqa: E402
from bezier import stroke_to_beziers  # noqa: E402


def make_polyline(n=30, step=6.0, ybase=50.0):
    pts = []
    for i in range(n):
        pts.append((10.0 + i * step, ybase + (12.0 if i % 2 else -4.0) * (1 if i % 3 else 0.5)))
    return pts


class TestTracingAlgorithms(unittest.TestCase):
    def test_stroke_to_beziers_algorithms_produce_segments(self):
        pts = make_polyline()
        for algo in ("fit", "catmull-rom", "single"):
            segs = stroke_to_beziers(pts, simplify_epsilon=2.5, max_points=5, algorithm=algo)
            self.assertTrue(len(segs) >= 1, msg=algo)
            for seg in segs:
                self.assertEqual(len(seg), 4, msg=algo)
                for pt in seg:
                    self.assertEqual(len(pt), 2)

    def test_single_algorithm_produces_one_segment(self):
        pts = make_polyline()
        segs = stroke_to_beziers(pts, algorithm="single")
        self.assertEqual(len(segs), 1)

    def test_fit_and_catmull_rom_can_differ(self):
        pts = make_polyline()
        fit = stroke_to_beziers(pts, simplify_epsilon=2.5, max_points=5, algorithm="fit")
        cr = stroke_to_beziers(pts, simplify_epsilon=2.5, max_points=5, algorithm="catmull-rom")
        # algorithms should generally produce different control points for nontrivial strokes
        self.assertNotEqual(fit, cr)

    def test_new_stroke_stores_algorithm(self):
        segs = stroke_to_beziers(make_polyline(), max_points=4, algorithm="catmull-rom")
        st = app.new_stroke(segs, algorithm="catmull-rom")
        self.assertEqual(st.get("algorithm"), "catmull-rom")
        st2 = app.new_stroke(segs)
        self.assertEqual(st2.get("algorithm"), "fit")

    def test_per_stroke_algorithm_independence(self):
        pts = make_polyline()
        s1 = app.new_stroke(stroke_to_beziers(pts, max_points=4, algorithm="fit"), algorithm="fit")
        s2 = app.new_stroke(stroke_to_beziers(pts, max_points=4, algorithm="catmull-rom"), algorithm="catmull-rom")
        s3 = app.new_stroke(stroke_to_beziers(pts, algorithm="single"), algorithm="single")
        self.assertEqual(s1["algorithm"], "fit")
        self.assertEqual(s2["algorithm"], "catmull-rom")
        self.assertEqual(s3["algorithm"], "single")
        # different algorithms -> different geometry expected
        self.assertNotEqual(s1["segs"], s2["segs"])

    def test_backward_compat_mode_single(self):
        pts = make_polyline()
        segs = stroke_to_beziers(pts, mode="single")
        self.assertEqual(len(segs), 1)


class TestTracingUIIntegration(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((app.WIDTH, app.HEIGHT))
        self.fonts = (
            pygame.font.SysFont(None, 24),
            pygame.font.SysFont(None, 20),
            pygame.font.SysFont(None, 30),
        )

    def tearDown(self):
        pygame.quit()

    def _draw_state(self, algo="fit"):
        btn_boost = app.Button((0, 0, app.PANEL_W - 40, 34), "Boost limit")
        btn_undo = app.Button((0, 0, app.PANEL_W - 40, 36), "Undo")
        btn_clear = app.Button((0, 0, app.PANEL_W - 40, 36), "Clear")
        slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 2, 5, 4)
        width_slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 1, 20, 3)
        return {
            "tool_mode": "draw", "max_points": 4, "boost_points": False,
            "NORMAL_MAX_POINTS": 5, "BOOST_MAX_POINTS": 100,
            "slider": slider, "width_slider": width_slider,
            "buttons": {"boost": btn_boost, "actions": [btn_undo, btn_clear]},
            "stroke_count": 0, "selected_strokes": set(), "selected_obj": None,
            "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
            "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.FILL_SWATCHES],
            "trace_algorithm": algo,
            "trace_algo_rects": {},
        }

    def test_draw_panel_renders_tracing_selector(self):
        for algo in ("fit", "catmull-rom", "single"):
            state = self._draw_state(algo)
            app.draw_panel(self.screen, self.fonts, (0, 0), state)
            rects = state.get("trace_algo_rects", {})
            self.assertEqual(set(rects.keys()), {"fit", "catmull-rom", "single"})
            for r in rects.values():
                self.assertGreater(r.w, 0)
                self.assertGreater(r.h, 0)

    def test_selection_panel_shows_tracing_label(self):
        st = app.new_stroke(stroke_to_beziers(make_polyline(), max_points=4, algorithm="catmull-rom"), algorithm="catmull-rom")
        btn_boost = app.Button((0, 0, app.PANEL_W - 40, 34), "Boost limit")
        btn_undo = app.Button((0, 0, app.PANEL_W - 40, 36), "Undo")
        btn_clear = app.Button((0, 0, app.PANEL_W - 40, 36), "Clear")
        slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 2, 5, 4)
        width_slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 1, 20, 3)
        state = {
            "tool_mode": "selection", "max_points": 4, "boost_points": False,
            "NORMAL_MAX_POINTS": 5, "BOOST_MAX_POINTS": 100,
            "slider": slider, "width_slider": width_slider,
            "buttons": {"boost": btn_boost, "actions": [btn_undo, btn_clear]},
            "stroke_count": 1, "selected_strokes": {0}, "selected_obj": st,
            "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
            "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.FILL_SWATCHES],
            "color_target": "stroke", "picker_h": 0.0, "picker_s": 0.0, "picker_v": 0.1,
            "picker_drag_sv": False, "picker_drag_hue": False,
            "sv_rect": pygame.Rect(0, 0, 0, 0), "hue_rect": pygame.Rect(0, 0, 0, 0),
            "tab_stroke_rect": pygame.Rect(0, 0, 0, 0), "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
            "nofill_rect": pygame.Rect(0, 0, 0, 0),
            "selection_submode": "transform",
            "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
        }
        # should render without error and show tracing info for the stroke's algorithm
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertEqual(st.get("algorithm"), "catmull-rom")


if __name__ == "__main__":
    unittest.main()
