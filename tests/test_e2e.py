import os
import unittest

# Headless-safe pygame before importing app
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import app  # noqa: E402
from bezier import stroke_to_beziers  # noqa: E402


def make_polyline(n=20, step=5.0, ybase=50.0):
    pts = []
    for i in range(n):
        pts.append((10.0 + i * step, ybase + (10.0 if i % 2 else 0.0)))
    return pts


class TestBezierPipelineE2E(unittest.TestCase):
    def test_stroke_to_beziers_respects_max_points(self):
        pts = make_polyline(40)
        segs = stroke_to_beziers(pts, simplify_epsilon=2.5, tension=0.0, max_points=4)
        self.assertTrue(len(segs) >= 1)
        # max_points caps simplified polyline points => segments <= max_points-1
        self.assertLessEqual(len(segs), 4)
        for seg in segs:
            self.assertEqual(len(seg), 4)
            for pt in seg:
                self.assertEqual(len(pt), 2)

    def test_stroke_to_beziers_min_input(self):
        self.assertEqual(stroke_to_beziers([(0, 0)]), [])
        segs = stroke_to_beziers([(0, 0), (10, 10)])
        self.assertEqual(len(segs), 1)


class TestStrokeModelE2E(unittest.TestCase):
    def test_new_stroke_defaults(self):
        segs = [((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))]
        st = app.new_stroke(segs)
        self.assertIs(app.segs_of(st), segs)
        self.assertIn("stroke_color", st)
        self.assertEqual(st["stroke_width"], 3.0)
        self.assertIsNone(st["fill_color"])
        self.assertEqual(st["corner_anchors"], set())

    def test_new_stroke_with_options(self):
        segs = [((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))]
        st = app.new_stroke(segs, stroke_color=(1, 0, 0), stroke_width=7, fill_color=(0, 1, 0), corner_anchors={(0, "p0")})
        self.assertEqual(st["stroke_color"], (1, 0, 0))
        self.assertEqual(st["stroke_width"], 7.0)
        self.assertEqual(st["fill_color"], (0, 1, 0))
        self.assertEqual(st["corner_anchors"], {(0, "p0")})


class TestDrawingAndSnappingE2E(unittest.TestCase):
    def test_create_stroke_from_drawn_points(self):
        pts = make_polyline(25)
        segs = stroke_to_beziers(pts, simplify_epsilon=2.5, tension=0.0, max_points=5)
        st = app._close_path_if_needed(app.new_stroke(segs))
        self.assertTrue(app.segs_of(st))

    def test_nearest_endpoint(self):
        st = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        near = app.nearest_endpoint((2.0, 1.0), [st], radius=10.0)
        self.assertEqual(near, (0.0, 0.0))
        far = app.nearest_endpoint((100.0, 100.0), [st], radius=10.0)
        self.assertIsNone(far)

    def test_stroke_endpoints(self):
        st = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        eps = app.stroke_endpoints([st])
        self.assertIn((0.0, 0.0), eps)
        self.assertIn((30.0, 0.0), eps)


class TestMergeAndClosureE2E(unittest.TestCase):
    def test_merge_connected_strokes_marks_corner(self):
        a = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        b = app.new_stroke([((30.0, 0.0), (40.0, 0.0), (50.0, 10.0), (60.0, 10.0))])
        merged_paths = app.merge_connected_strokes([a, b], eps=6.0)
        self.assertEqual(len(merged_paths), 1)
        merged = merged_paths[0]
        segs = app.segs_of(merged)
        self.assertEqual(len(segs), 2)
        # join between strokes is a corner
        self.assertIn((0, "p3"), merged["corner_anchors"])
        self.assertIn((1, "p0"), merged["corner_anchors"])

    def test_close_path_marks_corner(self):
        segs = [((0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (0.5, 0.5))]
        st = app.new_stroke(segs)
        closed = app._close_path_if_needed(st, eps=6.0)
        csegs = app.segs_of(closed)
        self.assertEqual(csegs[0][0], csegs[-1][3])
        self.assertIn((0, "p0"), closed["corner_anchors"])
        self.assertIn((len(csegs) - 1, "p3"), closed["corner_anchors"])


class TestSelectionAndHitTestE2E(unittest.TestCase):
    def test_hit_test_stroke(self):
        s1 = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        s2 = app.new_stroke([((0.0, 50.0), (10.0, 50.0), (20.0, 50.0), (30.0, 50.0))])
        idx = app.hit_test_stroke((15.0, 0.0), [s1, s2], threshold=8.0)
        self.assertEqual(idx, 0)
        idx2 = app.hit_test_stroke((15.0, 50.0), [s1, s2], threshold=8.0)
        self.assertEqual(idx2, 1)
        none = app.hit_test_stroke((200.0, 200.0), [s1, s2], threshold=8.0)
        self.assertIsNone(none)

    def test_hit_test_point_anchor(self):
        st = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        hit = app.hit_test_point(st, (0.0, 0.0), radius=8.0)
        self.assertIsNotNone(hit)


class TestPointEditingE2E(unittest.TestCase):
    def test_internal_join_handle_mirrors(self):
        segs = [
            ((0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (30.0, 10.0)),
            ((30.0, 10.0), (40.0, 10.0), (50.0, 20.0), (60.0, 20.0)),
        ]
        st = app.new_stroke(segs)  # internal join -> smooth, no corner anchors
        moved = app.set_stroke_point(st, 0, "c2", (25.0, 5.0))
        c1_next = moved["segs"][1][1]
        expected = (2 * 30.0 - 25.0, 2 * 10.0 - 5.0)
        self.assertEqual(c1_next, expected)

    def test_merged_join_handle_independent(self):
        a = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        b = app.new_stroke([((30.0, 0.0), (40.0, 0.0), (50.0, 10.0), (60.0, 10.0))])
        merged = app.merge_connected_strokes([a, b])[0]
        moved = app.set_stroke_point(merged, 0, "c2", (25.0, -5.0))
        self.assertEqual(moved["segs"][1][1], (40.0, 0.0))  # unchanged corner side

    def test_anchor_drag_moves_handles_and_keeps_mirror(self):
        segs = [
            ((0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (30.0, 10.0)),
            ((30.0, 10.0), (40.0, 10.0), (50.0, 20.0), (60.0, 20.0)),
        ]
        st = app.new_stroke(segs)
        moved = app.set_stroke_point(st, 0, "p3", (35.0, 15.0))
        c2 = moved["segs"][0][2]
        c1_next = moved["segs"][1][1]
        anchor = moved["segs"][1][0]
        self.assertEqual(anchor, (35.0, 15.0))
        mid = ((c2[0] + c1_next[0]) / 2, (c2[1] + c1_next[1]) / 2)
        self.assertEqual(mid, anchor)

    def test_translate_stroke(self):
        st = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        moved = app.translate_stroke(st, 5.0, -3.0)
        self.assertEqual(moved["segs"][0][0], (5.0, -3.0))
        self.assertEqual(moved["segs"][0][3], (35.0, -3.0))


class TestRenderE2E(unittest.TestCase):
    def test_draw_scene_smoke(self):
        surf = app.make_cairo_surface(200, 100)
        s1 = app.new_stroke([((10.0, 10.0), (30.0, 10.0), (50.0, 40.0), (70.0, 40.0))])
        s2 = app.new_stroke([((20.0, 60.0), (40.0, 60.0), (60.0, 80.0), (80.0, 80.0))], fill_color=(0.9, 0.8, 0.7))
        # normal
        app.draw_scene(surf, [s1, s2])
        # selected/edit mode with handles
        app.draw_scene(surf, [s1, s2], selected_index=0, edit_mode=True)
        # active drawing stroke and snap
        app.draw_scene(surf, [s1], active_stroke=[(5, 5), (15, 20), (25, 10)], snap_point=(25, 10))

    def test_surface_to_pygame(self):
        import pygame

        pygame.init()
        surf = app.make_cairo_surface(64, 32)
        app.draw_scene(surf, [])
        pg = app.surface_to_pygame(surf)
        self.assertEqual(pg.get_width(), 64)
        self.assertEqual(pg.get_height(), 32)


if __name__ == "__main__":
    unittest.main()
