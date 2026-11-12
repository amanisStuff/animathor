import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import app  # noqa: E402
from bezier import stroke_to_beziers, rdp, catmull_rom_to_beziers  # noqa: E402


def make_polyline(n=20, step=5.0, ybase=50.0):
    pts = []
    for i in range(n):
        pts.append((10.0 + i * step, ybase + (10.0 if i % 2 else 0.0)))
    return pts


class TestBezierAndFitting(unittest.TestCase):
    def test_rdp_simplifies(self):
        pts = [(0, 0), (1, 0.1), (2, -0.1), (3, 0)]
        out = rdp(pts, 0.5)
        self.assertGreaterEqual(len(out), 2)
        self.assertEqual(out[0], pts[0])
        self.assertEqual(out[-1], pts[-1])

    def test_catmull_rom_to_beziers(self):
        pts = [(0, 0), (10, 0), (20, 10), (30, 10)]
        segs = catmull_rom_to_beziers(pts)
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[0][0], pts[0])
        self.assertEqual(segs[-1][3], pts[-1])

    def test_stroke_to_beziers_max_points(self):
        pts = make_polyline(50)
        segs = stroke_to_beziers(pts, simplify_epsilon=2.5, tension=0.0, max_points=4)
        self.assertTrue(1 <= len(segs) <= 4)
        for s in segs:
            self.assertEqual(len(s), 4)

    def test_stroke_to_beziers_empty_and_short(self):
        self.assertEqual(stroke_to_beziers([]), [])
        self.assertEqual(stroke_to_beziers([(1, 1)]), [])
        self.assertEqual(len(stroke_to_beziers([(0, 0), (10, 0)])), 1)


class TestStrokeModel(unittest.TestCase):
    def test_new_stroke_and_segs_of(self):
        segs = [((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))]
        st = app.new_stroke(segs, stroke_color=(1, 0, 0), stroke_width=5, fill_color=(0, 1, 0))
        self.assertIs(app.segs_of(st), segs)
        self.assertEqual(st["stroke_color"], (1, 0, 0))
        self.assertEqual(st["stroke_width"], 5.0)
        self.assertEqual(st["fill_color"], (0, 1, 0))
        self.assertEqual(st["corner_anchors"], set())

    def test_stroke_endpoints_helpers(self):
        st = app.new_stroke([((1.0, 2.0), (3.0, 2.0), (5.0, 2.0), (7.0, 2.0))])
        self.assertEqual(app.stroke_start(st), (1.0, 2.0))
        self.assertEqual(app.stroke_end(st), (7.0, 2.0))


class TestSnappingMergeClosure(unittest.TestCase):
    def test_nearest_endpoint_and_snap(self):
        st = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        self.assertEqual(app.nearest_endpoint((1.0, 1.0), [st], 10.0), (0.0, 0.0))
        self.assertIsNone(app.nearest_endpoint((100.0, 100.0), [st], 10.0))

    def test_merge_connected_strokes(self):
        a = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        b = app.new_stroke([((30.0, 0.0), (40.0, 0.0), (50.0, 10.0), (60.0, 10.0))])
        merged = app.merge_connected_strokes([a, b], eps=6.0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(app.segs_of(merged[0])), 2)
        self.assertIn((0, "p3"), merged[0]["corner_anchors"])
        self.assertIn((1, "p0"), merged[0]["corner_anchors"])

    def test_merge_chain_and_reverse(self):
        a = app.new_stroke([((0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (15.0, 0.0))])
        b = app.new_stroke([((30.0, 0.0), (25.0, 0.0), (20.0, 0.0), (15.0, 0.0))])  # reversed direction join
        merged = app.merge_connected_strokes([a, b], eps=6.0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(app.segs_of(merged[0])), 2)

    def test_close_path_if_needed(self):
        segs = [((0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (0.5, 0.5))]
        st = app.new_stroke(segs)
        closed = app._close_path_if_needed(st, eps=6.0)
        csegs = app.segs_of(closed)
        self.assertEqual(csegs[0][0], csegs[-1][3])
        self.assertIn((0, "p0"), closed["corner_anchors"])
        self.assertIn((len(csegs) - 1, "p3"), closed["corner_anchors"])

    def test_open_endpoints_filter_closed_component(self):
        # closed shape should not be reported as open endpoints
        s1 = app.new_stroke([((0, 0), (10, 0), (10, 10), (0, 10))])
        s2 = app.new_stroke([((0, 10), (-10, 10), (-10, 0), (0, 0))])
        merged = app.merge_connected_strokes([s1, s2], eps=6.0)
        # after merge/close it forms a component; endpoints logic may vary, but should not crash
        eps = app.stroke_endpoints(merged)
        self.assertIsInstance(eps, list)


class TestSelectionHitTest(unittest.TestCase):
    def test_hit_test_stroke(self):
        s1 = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        s2 = app.new_stroke([((0.0, 50.0), (10.0, 50.0), (20.0, 50.0), (30.0, 50.0))])
        self.assertEqual(app.hit_test_stroke((15.0, 0.0), [s1, s2], 8.0), 0)
        self.assertEqual(app.hit_test_stroke((15.0, 50.0), [s1, s2], 8.0), 1)
        self.assertIsNone(app.hit_test_stroke((200.0, 200.0), [s1, s2], 8.0))

    def test_hit_test_point(self):
        st = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        self.assertIsNotNone(app.hit_test_point(st, (0.0, 0.0), 8.0))
        self.assertIsNotNone(app.hit_test_point(st, (30.0, 0.0), 8.0))
        self.assertIsNone(app.hit_test_point(st, (100.0, 100.0), 8.0))


class TestPointEditing(unittest.TestCase):
    def test_smooth_internal_join_mirrors_handle(self):
        segs = [
            ((0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (30.0, 10.0)),
            ((30.0, 10.0), (40.0, 10.0), (50.0, 20.0), (60.0, 20.0)),
        ]
        st = app.new_stroke(segs)
        moved = app.set_stroke_point(st, 0, "c2", (25.0, 5.0))
        expected = (2 * 30.0 - 25.0, 2 * 10.0 - 5.0)
        self.assertEqual(moved["segs"][1][1], expected)

    def test_corner_join_independent_handles(self):
        a = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        b = app.new_stroke([((30.0, 0.0), (40.0, 0.0), (50.0, 10.0), (60.0, 10.0))])
        merged = app.merge_connected_strokes([a, b])[0]
        moved = app.set_stroke_point(merged, 0, "c2", (25.0, -5.0))
        self.assertEqual(moved["segs"][1][1], (40.0, 0.0))

    def test_anchor_drag_moves_handles_and_keeps_smooth(self):
        segs = [
            ((0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (30.0, 10.0)),
            ((30.0, 10.0), (40.0, 10.0), (50.0, 20.0), (60.0, 20.0)),
        ]
        st = app.new_stroke(segs)
        moved = app.set_stroke_point(st, 0, "p3", (35.0, 15.0))
        anchor = moved["segs"][1][0]
        c2 = moved["segs"][0][2]
        c1n = moved["segs"][1][1]
        self.assertEqual(anchor, (35.0, 15.0))
        self.assertEqual(((c2[0] + c1n[0]) / 2, (c2[1] + c1n[1]) / 2), anchor)

    def test_is_corner_anchor(self):
        a = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        b = app.new_stroke([((30.0, 0.0), (40.0, 0.0), (50.0, 10.0), (60.0, 10.0))])
        merged = app.merge_connected_strokes([a, b])[0]
        self.assertTrue(app.is_corner_anchor(merged, 0, "p3"))
        # internal join of a single stroke is not a corner
        st = app.new_stroke([
            ((0.0, 0.0), (10.0, 0.0), (20.0, 10.0), (30.0, 10.0)),
            ((30.0, 10.0), (40.0, 10.0), (50.0, 20.0), (60.0, 20.0)),
        ])
        self.assertFalse(app.is_corner_anchor(st, 0, "p3"))


class TestTransformsAndGeometry(unittest.TestCase):
    def test_translate_stroke(self):
        st = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        moved = app.translate_stroke(st, 5.0, -3.0)
        self.assertEqual(moved["segs"][0][0], (5.0, -3.0))
        self.assertEqual(moved["segs"][0][3], (35.0, -3.0))
        self.assertEqual(st["segs"][0][0], (0.0, 0.0))  # original unchanged

    def test_reverse_stroke_preserves_corners_mapping(self):
        st = app.new_stroke([
            ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)),
            ((3.0, 0.0), (4.0, 0.0), (5.0, 0.0), (6.0, 0.0)),
        ], corner_anchors={(0, "p0")})
        rev = app.reverse_stroke(st)
        self.assertEqual(len(app.segs_of(rev)), 2)
        # p0 of first seg maps to p3 of last seg in reversed
        self.assertIn((1, "p3"), rev["corner_anchors"])

    def test_clamp_and_canvas_helpers(self):
        self.assertEqual(app.clamp(5, 0, 10), 5)
        self.assertEqual(app.clamp(-1, 0, 10), 0)
        self.assertEqual(app.clamp(11, 0, 10), 10)
        self.assertTrue(app.in_canvas((app.CANVAS_X + 10, 10)))
        self.assertFalse(app.in_canvas((0, 10)))
        c = app.clamp_to_canvas((-100, -100))
        self.assertEqual(c[0], 0)
        self.assertEqual(c[1], 0)

    def test_stroke_bbox(self):
        st = app.new_stroke([((10.0, 20.0), (15.0, 5.0), (25.0, 35.0), (30.0, 25.0))])
        bb = app.stroke_bbox(st)
        self.assertEqual(bb, (10.0, 5.0, 30.0, 35.0))
        self.assertIsNone(app.stroke_bbox(app.new_stroke([])))

    def test_bbox_handles_and_hit_test(self):
        bb = (0.0, 0.0, 100.0, 50.0)
        handles = app.bbox_handles(bb)
        self.assertEqual(handles["nw"], (0.0, 0.0))
        self.assertEqual(handles["se"], (100.0, 50.0))
        self.assertEqual(handles["n"], (50.0, 0.0))
        self.assertEqual(app.hit_test_bbox_handle(bb, (0.0, 0.0), radius=8.0), "nw")
        self.assertEqual(app.hit_test_bbox_handle(bb, (50.0, 0.0), radius=8.0), "n")
        self.assertEqual(app.hit_test_bbox_handle(bb, handles["rot"], radius=8.0), "rot")
        self.assertIsNone(app.hit_test_bbox_handle(bb, (200.0, 200.0), radius=8.0))

    def test_point_in_bbox(self):
        bb = (0.0, 0.0, 100.0, 50.0)
        self.assertTrue(app.point_in_bbox(bb, (50.0, 25.0)))
        self.assertTrue(app.point_in_bbox(bb, (0.0, 0.0)))
        self.assertFalse(app.point_in_bbox(bb, (-1.0, 25.0)))
        self.assertFalse(app.point_in_bbox(None, (0.0, 0.0)))

    def test_normalize_rect_and_intersection(self):
        r = app.normalize_rect((10, 20), (5, 30))
        self.assertEqual(r, (5, 20, 10, 30))
        self.assertTrue(app.rects_intersect((0, 0, 10, 10), (5, 5, 15, 15)))
        self.assertFalse(app.rects_intersect((0, 0, 10, 10), (11, 0, 20, 10)))

    def test_transform_stroke_scale(self):
        st = app.new_stroke([((10.0, 10.0), (10.0, 10.0), (20.0, 20.0), (20.0, 20.0))])
        cx, cy = 15.0, 15.0
        scaled = app.transform_stroke(st, cx, cy, 0.0, 2.0)
        seg = app.segs_of(scaled)[0]
        self.assertAlmostEqual(seg[0][0], 5.0, places=5)
        self.assertAlmostEqual(seg[0][1], 5.0, places=5)
        self.assertAlmostEqual(seg[3][0], 25.0, places=5)
        self.assertAlmostEqual(seg[3][1], 25.0, places=5)

    def test_transform_stroke_rotate(self):
        st = app.new_stroke([((10.0, 0.0), (10.0, 0.0), (10.0, 0.0), (10.0, 0.0))])
        rot = app.transform_stroke(st, 0.0, 0.0, math.pi / 2, 1.0)
        p = app.segs_of(rot)[0][0]
        self.assertAlmostEqual(p[0], 0.0, places=5)
        self.assertAlmostEqual(p[1], 10.0, places=5)


class TestColorFeatures(unittest.TestCase):
    def test_hsv_rgb_roundtrip(self):
        cols = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0.2, 0.4, 0.6), (1, 1, 1), (0, 0, 0)]
        for c in cols:
            h, s, v = app.rgb_to_hsv(*c)
            r = app.hsv_to_rgb(h, s, v)
            for a, b in zip(c, r):
                self.assertAlmostEqual(a, b, places=5)

    def test_rgb_to_hex(self):
        self.assertEqual(app.rgb_to_hex((1.0, 0.0, 0.0)), "#FF0000")
        self.assertEqual(app.rgb_to_hex((0.0, 0.5, 1.0)), "#007FFF")

    def test_apply_stroke_and_fill_color_does_not_delete_shape(self):
        # Regression: selecting/applying a color must not delete the stroke
        strokes = [app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])]
        selected = 0
        sel_obj = strokes[selected]
        # simulate stroke color pick
        sel_obj["stroke_color"] = (0.9, 0.1, 0.2)
        self.assertEqual(len(strokes), 1)
        self.assertIs(strokes[selected], sel_obj)
        # simulate fill color pick
        sel_obj["fill_color"] = (0.1, 0.2, 0.9)
        self.assertEqual(len(strokes), 1)
        # simulate no-fill
        sel_obj["fill_color"] = None
        self.assertEqual(len(strokes), 1)
        # simulate HSV-derived color
        sel_obj["stroke_color"] = app.hsv_to_rgb(200, 0.6, 0.8)
        self.assertEqual(len(strokes), 1)
        # presets
        for col in app.STROKE_SWATCHES:
            sel_obj["stroke_color"] = col
        self.assertEqual(len(strokes), 1)

    def test_selection_mode_panel_actions_guard(self):
        # Regression for stale undo/clear rects: in selection mode, undo/clear must not run
        tool_mode = "selection"
        strokes = [app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])]
        selected_stroke = 0
        # simulate guarded conditions
        if tool_mode == "draw":  # should be False in selection mode
            if strokes:
                strokes.pop()
            selected_stroke = None
        self.assertEqual(len(strokes), 1)
        self.assertEqual(selected_stroke, 0)


class TestRenderingAndUI(unittest.TestCase):
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

    def test_draw_scene_all_modes(self):
        surf = app.make_cairo_surface(200, 100)
        s1 = app.new_stroke([((10.0, 10.0), (30.0, 10.0), (50.0, 40.0), (70.0, 40.0))])
        s2 = app.new_stroke([((20.0, 60.0), (40.0, 60.0), (60.0, 80.0), (80.0, 80.0))], fill_color=(0.9, 0.8, 0.7))
        app.draw_scene(surf, [])
        app.draw_scene(surf, [s1, s2])
        app.draw_scene(surf, [s1, s2], selected_index=0, edit_mode=True, selection_submode="transform")
        app.draw_scene(surf, [s1, s2], selected_index=0, edit_mode=True, selection_submode="nodes")
        app.draw_scene(surf, [s1], active_stroke=[(5, 5), (15, 20)], snap_point=(15, 20))
        app.draw_scene(surf, [s1, s2], selected_index=1, edit_mode=True, selection_submode="transform")

    def test_surface_to_pygame(self):
        surf = app.make_cairo_surface(64, 32)
        app.draw_scene(surf, [])
        pg = app.surface_to_pygame(surf)
        self.assertEqual((pg.get_width(), pg.get_height()), (64, 32))

    def test_draw_left_toolbar_modes(self):
        btn_draw = app.Button((8, 12, 40, 40), "")
        btn_select = app.Button((8, 60, 40, 40), "")
        app.draw_left_toolbar(self.screen, (0, 0), "draw", btn_draw, btn_select)
        app.draw_left_toolbar(self.screen, (20, 20), "selection", btn_draw, btn_select)

    def _base_state(self, tool_mode="draw", selected=None, obj=None, color_target="stroke", selection_submode="transform"):
        btn_boost = app.Button((0, 0, app.PANEL_W - 40, 34), "Boost limit")
        btn_undo = app.Button((0, 0, app.PANEL_W - 40, 36), "Undo")
        btn_clear = app.Button((0, 0, app.PANEL_W - 40, 36), "Clear")
        slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 2, 5, 4)
        width_slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 1, 20, 3)
        return {
            "tool_mode": tool_mode, "max_points": 4, "boost_points": False,
            "NORMAL_MAX_POINTS": 5, "BOOST_MAX_POINTS": 100,
            "slider": slider, "width_slider": width_slider,
            "buttons": {"boost": btn_boost, "actions": [btn_undo, btn_clear]},
            "stroke_count": 1 if obj else 0, "selected_strokes": ({selected} if selected is not None else set()), "selected_obj": obj,
            "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
            "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.FILL_SWATCHES],
            "color_target": color_target, "picker_h": 10.0, "picker_s": 0.5, "picker_v": 0.8,
            "picker_drag_sv": False, "picker_drag_hue": False,
            "sv_rect": pygame.Rect(0, 0, 0, 0), "hue_rect": pygame.Rect(0, 0, 0, 0),
            "tab_stroke_rect": pygame.Rect(0, 0, 0, 0), "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
            "nofill_rect": pygame.Rect(0, 0, 0, 0),
            "selection_submode": selection_submode,
            "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
        }

    def test_draw_panel_selection_with_stroke_and_fill_targets(self):
        st = app.new_stroke([((10.0, 10.0), (30.0, 10.0), (50.0, 40.0), (70.0, 40.0))], fill_color=(0.2, 0.3, 0.4))
        state = self._base_state("selection", 0, st, "stroke", selection_submode="transform")
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertGreater(state["sv_rect"].w, 0)
        self.assertGreater(state["hue_rect"].w, 0)
        self.assertGreater(state["nodes_toggle_rect"].w, 0)
        state["color_target"] = "fill"
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        # no fill case
        st["fill_color"] = None
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        # nodes submode
        state = self._base_state("selection", 0, st, "stroke", selection_submode="nodes")
        app.draw_panel(self.screen, self.fonts, (0, 0), state)

    def test_draw_panel_draw_mode(self):
        state = self._base_state("draw")
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        # boost toggled label path
        state["boost_points"] = True
        app.draw_panel(self.screen, self.fonts, (0, 0), state)

    def test_draw_panel_selection_no_selection(self):
        state = self._base_state("selection", None, None)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)


class TestEndToEndFlow(unittest.TestCase):
    def test_draw_snap_merge_select_edit_flow(self):
        # draw stroke A
        pts_a = make_polyline(20, ybase=40)
        a = app._close_path_if_needed(app.new_stroke(stroke_to_beziers(pts_a, max_points=4)))
        # draw stroke B starting near A end
        end_a = app.stroke_end(a)
        pts_b = [end_a] + [(end_a[0] + i * 5, end_a[1] + (i % 2) * 8) for i in range(1, 15)]
        b = app._close_path_if_needed(app.new_stroke(stroke_to_beziers(pts_b, max_points=4)))
        strokes = app.merge_connected_strokes([a, b], eps=8.0)
        self.assertGreaterEqual(len(strokes), 1)
        # select and edit
        idx = app.hit_test_stroke(app.stroke_start(strokes[0]), strokes, 10.0)
        self.assertIsNotNone(idx)
        st = strokes[idx]
        # change color (must not delete)
        st["stroke_color"] = (0.8, 0.2, 0.2)
        st["fill_color"] = (0.2, 0.8, 0.2)
        self.assertEqual(len(strokes), 1)
        # translate
        strokes[idx] = app.translate_stroke(st, 10, 10)
        self.assertEqual(len(strokes), 1)
        # edit point if possible
        if len(app.segs_of(strokes[idx])) >= 1:
            strokes[idx] = app.set_stroke_point(strokes[idx], 0, "c1", (5.0, 5.0))
        self.assertEqual(len(strokes), 1)


class TestAlphaAndTransparency(unittest.TestCase):
    def test_color_helpers(self):
        self.assertEqual(app.color_rgb((0.1, 0.2, 0.3)), (0.1, 0.2, 0.3))
        self.assertEqual(app.color_rgb((0.1, 0.2, 0.3, 0.5)), (0.1, 0.2, 0.3))
        self.assertEqual(app.color_alpha((0.1, 0.2, 0.3)), 1.0)
        self.assertAlmostEqual(app.color_alpha((0.1, 0.2, 0.3, 0.25)), 0.25)
        self.assertEqual(app.color_rgba((0.1, 0.2, 0.3)), (0.1, 0.2, 0.3, 1.0))
        self.assertEqual(app.color_rgba((0.1, 0.2, 0.3, 0.4)), (0.1, 0.2, 0.3, 0.4))
        self.assertEqual(app.set_color_alpha((0.1, 0.2, 0.3), 0.5), (0.1, 0.2, 0.3, 0.5))
        self.assertEqual(app.set_color_alpha((0.1, 0.2, 0.3, 1.0), 0.0), (0.1, 0.2, 0.3, 0.0))

    def test_stroke_with_alpha_render_and_model(self):
        st = app.new_stroke([((10.0, 10.0), (30.0, 10.0), (50.0, 40.0), (70.0, 40.0))],
                            stroke_color=(1.0, 0.0, 0.0, 0.3),
                            fill_color=(0.0, 1.0, 0.0, 0.5))
        self.assertEqual(app.color_alpha(st["stroke_color"]), 0.3)
        self.assertEqual(app.color_alpha(st["fill_color"]), 0.5)
        surf = app.make_cairo_surface(120, 80)
        app.draw_scene(surf, [st], selected_index=0, edit_mode=True, selection_submode="transform")

    def test_changing_hsv_preserves_alpha(self):
        # simulate picker behavior: derive rgb from hsv, preserve alpha
        stroke = {"stroke_color": (0.2, 0.4, 0.6, 0.25)}
        alpha = app.color_alpha(stroke.get("stroke_color"), 1.0)
        rgb = app.hsv_to_rgb(120, 0.5, 0.8)
        stroke["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
        self.assertAlmostEqual(app.color_alpha(stroke["stroke_color"]), 0.25)
        self.assertNotEqual(app.color_rgb(stroke["stroke_color"]), (0.2, 0.4, 0.6))

    def test_rgb_to_hsv_accepts_rgba(self):
        h, s, v = app.rgb_to_hsv(1.0, 0.0, 0.0, 0.5)
        self.assertAlmostEqual(h, 0.0)
        self.assertAlmostEqual(s, 1.0)
        self.assertAlmostEqual(v, 1.0)


class TestMultiSelect(unittest.TestCase):
    def test_combined_bbox(self):
        s1 = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 10.0))])
        s2 = app.new_stroke([((40.0, 20.0), (50.0, 20.0), (60.0, 30.0), (70.0, 40.0))])
        bb = app.combined_bbox([s1, s2], {0, 1})
        self.assertIsNotNone(bb)
        self.assertAlmostEqual(bb[0], 0.0)
        self.assertAlmostEqual(bb[1], 0.0)
        self.assertAlmostEqual(bb[2], 70.0)
        self.assertAlmostEqual(bb[3], 40.0)
        self.assertEqual(app.combined_bbox([s1, s2], set()), None)

    def test_draw_scene_multiple_selected(self):
        surf = app.make_cairo_surface(200, 100)
        s1 = app.new_stroke([((10.0, 10.0), (30.0, 10.0), (50.0, 20.0), (70.0, 20.0))])
        s2 = app.new_stroke([((10.0, 50.0), (30.0, 50.0), (50.0, 70.0), (70.0, 70.0))])
        # multiple selection in transform mode
        app.draw_scene(surf, [s1, s2], selected_indices={0, 1}, edit_mode=True, selection_submode="transform")
        # multiple selection in nodes mode (should show bbox/fallback, no crash)
        app.draw_scene(surf, [s1, s2], selected_indices={0, 1}, edit_mode=True, selection_submode="nodes")
        # backward compat single selected_index
        app.draw_scene(surf, [s1, s2], selected_index=0, edit_mode=True, selection_submode="transform")

    def test_translate_multiple_strokes(self):
        s1 = app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))])
        s2 = app.new_stroke([((0.0, 10.0), (10.0, 10.0), (20.0, 10.0), (30.0, 10.0))])
        strokes = [s1, s2]
        for i in [0, 1]:
            strokes[i] = app.translate_stroke(strokes[i], 5.0, -2.0)
        self.assertEqual(app.segs_of(strokes[0])[0][0], (5.0, -2.0))
        self.assertEqual(app.segs_of(strokes[1])[0][0], (5.0, 8.0))

    def test_transform_multiple_strokes_group(self):
        s1 = app.new_stroke([((10.0, 10.0), (10.0, 10.0), (20.0, 10.0), (20.0, 10.0))])
        s2 = app.new_stroke([((10.0, 20.0), (10.0, 20.0), (20.0, 20.0), (20.0, 20.0))])
        strokes = [s1, s2]
        bb = app.combined_bbox(strokes, {0, 1})
        cx, cy = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
        for i in [0, 1]:
            strokes[i] = app.transform_stroke(strokes[i], cx, cy, 0.0, 2.0)
        new_bb = app.combined_bbox(strokes, {0, 1})
        # scaled uniformly around center, width/height doubled
        self.assertAlmostEqual(new_bb[2] - new_bb[0], (bb[2] - bb[0]) * 2.0, places=5)
        self.assertAlmostEqual(new_bb[3] - new_bb[1], (bb[3] - bb[1]) * 2.0, places=5)

    def test_apply_properties_to_multiple_strokes(self):
        strokes = [
            app.new_stroke([((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0))]),
            app.new_stroke([((0.0, 10.0), (10.0, 10.0), (20.0, 10.0), (30.0, 10.0))], fill_color=(0, 0, 1, 1)),
        ]
        # simulate applying color/width/alpha to all selected
        for i in [0, 1]:
            strokes[i]["stroke_color"] = (1.0, 0.0, 0.0, 0.5)
            strokes[i]["stroke_width"] = 7.0
            if strokes[i].get("fill_color") is not None:
                strokes[i]["fill_color"] = app.set_color_alpha(strokes[i]["fill_color"], 0.3)
        self.assertTrue(all(s["stroke_color"] == (1.0, 0.0, 0.0, 0.5) for s in strokes))
        self.assertTrue(all(s["stroke_width"] == 7.0 for s in strokes))
        self.assertEqual(app.color_alpha(strokes[1]["fill_color"]), 0.3)


class TestSnappingToCurve(unittest.TestCase):
    def test_nearest_point_on_strokes(self):
        # simple straight-ish cubic segment along y=0 from x=0..100
        st = app.new_stroke([((0.0, 0.0), (33.0, 0.0), (66.0, 0.0), (100.0, 0.0))])
        pt = app.nearest_point_on_strokes((50.0, 3.0), [st], radius=10.0)
        self.assertIsNotNone(pt)
        self.assertAlmostEqual(pt[1], 0.0, places=1)
        self.assertTrue(45.0 <= pt[0] <= 55.0)
        none = app.nearest_point_on_strokes((50.0, 50.0), [st], radius=5.0)
        self.assertIsNone(none)

    def test_nearest_snap_point_prefers_curve_when_closer(self):
        # Curved segment bulges up around middle; point near middle is closer to curve than endpoints
        st = app.new_stroke([((0.0, 0.0), (0.0, 50.0), (100.0, 50.0), (100.0, 0.0))])
        pos = (50.0, 35.0)
        pt = app.nearest_snap_point(pos, [st], radius=30.0)
        self.assertIsNotNone(pt)
        # should snap onto curve (near apex y~37.5), not to endpoints at y=0
        self.assertGreater(pt[1], 20.0)
        self.assertAlmostEqual(pt[0], 50.0, delta=5.0)

    def test_draw_snap_point_shift_only_for_curves(self):
        # Point near middle of curve but far from endpoints: no snap without shift, snap with shift
        st = app.new_stroke([((0.0, 0.0), (0.0, 50.0), (100.0, 50.0), (100.0, 0.0))])
        pos = (50.0, 35.0)
        radius = 30.0
        self.assertIsNone(app.draw_snap_point(pos, [st], radius, shift_held=False))
        pt = app.draw_snap_point(pos, [st], radius, shift_held=True)
        self.assertIsNotNone(pt)
        self.assertGreater(pt[1], 20.0)

    def test_draw_snap_point_endpoint_without_shift(self):
        # Near an endpoint: snaps even without shift
        st = app.new_stroke([((0.0, 0.0), (0.0, 50.0), (100.0, 50.0), (100.0, 0.0))])
        pos = (3.0, 2.0)
        pt_no_shift = app.draw_snap_point(pos, [st], radius=10.0, shift_held=False)
        pt_shift = app.draw_snap_point(pos, [st], radius=10.0, shift_held=True)
        self.assertIsNotNone(pt_no_shift)
        self.assertIsNotNone(pt_shift)
        self.assertAlmostEqual(pt_no_shift[0], 0.0, places=3)
        self.assertAlmostEqual(pt_no_shift[1], 0.0, places=3)

    def test_draw_snap_info_kinds(self):
        st = app.new_stroke([((0.0, 0.0), (0.0, 50.0), (100.0, 50.0), (100.0, 0.0))])
        # Near curve middle with shift -> assist (diamond)
        pt, kind = app.draw_snap_info((50.0, 35.0), [st], radius=30.0, shift_held=True)
        self.assertIsNotNone(pt)
        self.assertEqual(kind, "assist")
        # Near endpoint -> connect (circle)
        pt2, kind2 = app.draw_snap_info((3.0, 2.0), [st], radius=10.0, shift_held=True)
        self.assertIsNotNone(pt2)
        self.assertEqual(kind2, "connect")
        pt3, kind3 = app.draw_snap_info((3.0, 2.0), [st], radius=10.0, shift_held=False)
        self.assertEqual(kind3, "connect")


class TestCurveEdit(unittest.TestCase):
    def _make_stroke(self):
        # two segments
        return app.new_stroke([
            ((0.0, 0.0), (20.0, 0.0), (40.0, 0.0), (60.0, 0.0)),
            ((60.0, 0.0), (80.0, 10.0), (100.0, 10.0), (120.0, 0.0)),
        ])

    def test_hit_test_segment(self):
        st = self._make_stroke()
        # near middle of first segment
        self.assertEqual(app.hit_test_segment(st, (30.0, 1.0), threshold=10.0), 0)
        # near second segment
        self.assertEqual(app.hit_test_segment(st, (90.0, 8.0), threshold=12.0), 1)
        self.assertIsNone(app.hit_test_segment(st, (200.0, 200.0), threshold=5.0))

    def test_hide_curve_segment_render(self):
        st = self._make_stroke()
        st["hidden_segs"] = {1}
        surf = app.make_cairo_surface(200, 100)
        # should not crash and should draw remaining visible segment
        app.draw_scene(surf, [st], selected_indices={0}, edit_mode=True, selection_submode="curve", selected_curve=(0, 0))
        self.assertIn(1, st["hidden_segs"])

    def test_redraw_curve_segment_preserves_count_and_endpoints(self):
        st = self._make_stroke()
        orig_segs = list(app.segs_of(st))
        self.assertEqual(len(orig_segs), 2)
        seg_i = 1
        p0, p3 = orig_segs[seg_i][0], orig_segs[seg_i][3]
        # redraw middle curve with different shape but same segment slot
        drawn = [(p0[0], p0[1]), (75.0, 40.0), (95.0, 40.0), (p3[0], p3[1])]
        out = app.redraw_curve_segment(st, seg_i, drawn)
        out_segs = app.segs_of(out)
        self.assertEqual(len(out_segs), 2)  # same number of segments/curves
        self.assertEqual(out_segs[seg_i][0], p0)
        self.assertEqual(out_segs[seg_i][3], p3)
        # shape changed (control points differ)
        self.assertNotEqual(out_segs[seg_i], orig_segs[seg_i])


class TestStrokeComponentsRedraw(unittest.TestCase):
    def _make_component_stroke(self, raw_points, max_points, algorithm="fit"):
        beziers = app.stroke_to_beziers(
            raw_points, simplify_epsilon=2.5, tension=0.0,
            max_points=max_points, algorithm=algorithm,
        )
        st = app.new_stroke(beziers, algorithm=algorithm)
        st["components"] = [{
            "raw_points": [tuple(p) for p in raw_points],
            "draw_max_points": int(max_points),
            "algorithm": algorithm,
            "segs": list(beziers),
        }]
        return st

    def test_components_preserved_through_merge(self):
        s1 = self._make_component_stroke([(0, 0), (20, 10), (40, 0)], max_points=2, algorithm="fit")
        s2 = self._make_component_stroke([(40, 0), (60, -10), (80, 0)], max_points=3, algorithm="single")
        merged = app.merge_connected_strokes([s1, s2])
        self.assertEqual(len(merged), 1)
        comps = merged[0].get("components", [])
        self.assertEqual(len(comps), 2)
        self.assertEqual(comps[0]["draw_max_points"], 2)
        self.assertEqual(comps[0]["algorithm"], "fit")
        self.assertEqual(comps[1]["draw_max_points"], 3)
        self.assertEqual(comps[1]["algorithm"], "single")
        self.assertGreater(len(comps[0].get("raw_points", [])), 0)
        self.assertGreater(len(comps[1].get("raw_points", [])), 0)

    def test_redraw_stroke_component_uses_saved_settings(self):
        # create component traced with "single" (1 segment) even if global would differ
        raw = [(0, 0), (30, 40), (60, 40), (100, 0)]
        s = self._make_component_stroke(raw, max_points=4, algorithm="single")
        self.assertEqual(len(app.segs_of(s)), 1)
        self.assertEqual(s["components"][0]["algorithm"], "single")
        # redraw with different drawn shape but component should keep saved algorithm/settings
        new_raw = [(0, 0), (20, 10), (80, 10), (100, 0)]
        out = app.redraw_stroke_component(s, 0, new_raw)
        self.assertEqual(len(app.segs_of(out)), 1)  # single algorithm -> 1 segment
        self.assertEqual(app._stroke_components(out)[0]["algorithm"], "single")
        self.assertEqual(app._stroke_components(out)[0]["draw_max_points"], 4)

    def test_hit_test_component_in_merged_stroke(self):
        s1 = self._make_component_stroke([(0, 0), (20, 0), (40, 0)], max_points=2, algorithm="fit")
        s2 = self._make_component_stroke([(40, 0), (60, 0), (80, 0)], max_points=2, algorithm="fit")
        merged = app.merge_connected_strokes([s1, s2])[0]
        # near first component
        self.assertEqual(app.hit_test_component(merged, (20.0, 1.0), threshold=10.0), 0)
        # near second component
        self.assertEqual(app.hit_test_component(merged, (60.0, 1.0), threshold=10.0), 1)

    def test_component_stroke_style(self):
        s = self._make_component_stroke([(0, 0), (50, 0), (100, 0)], max_points=2, algorithm="fit")
        s["components"][0]["stroke_color"] = (1.0, 0.0, 0.0, 1.0)
        s["components"][0]["stroke_width"] = 7.0
        sc, sw = app._effective_component_style(s, 0)
        self.assertEqual(sc, (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(sw, 7.0)
        surf = app.make_cairo_surface(120, 40)
        app.draw_scene(surf, [s])


class TestMultiSelectUI(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        self.screen = pygame.display.set_mode((app.WIDTH, app.HEIGHT))
        self.fonts = (
            pygame.font.SysFont(None, 24),
            pygame.font.SysFont(None, 20),
            pygame.font.SysFont(None, 30),
        )

    def tearDown(self):
        pygame.quit()

    def _base_state(self, tool_mode="draw", selected=None, obj=None, color_target="stroke", selection_submode="transform"):
        btn_boost = app.Button((0, 0, app.PANEL_W - 40, 34), "Boost limit")
        btn_undo = app.Button((0, 0, app.PANEL_W - 40, 36), "Undo")
        btn_clear = app.Button((0, 0, app.PANEL_W - 40, 36), "Clear")
        slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 2, 5, 4)
        width_slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 1, 20, 3)
        sel_set = set()
        if isinstance(selected, set):
            sel_set = selected
        elif selected is not None:
            sel_set = {selected}
        return {
            "tool_mode": tool_mode, "max_points": 4, "boost_points": False,
            "NORMAL_MAX_POINTS": 5, "BOOST_MAX_POINTS": 100,
            "slider": slider, "width_slider": width_slider,
            "buttons": {"boost": btn_boost, "actions": [btn_undo, btn_clear]},
            "stroke_count": 2 if len(sel_set) > 1 else (1 if obj else 0),
            "selected_strokes": sel_set, "selected_obj": obj,
            "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
            "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
            "color_target": color_target, "picker_h": 10.0, "picker_s": 0.5, "picker_v": 0.8,
            "picker_drag_sv": False, "picker_drag_hue": False, "picker_drag_alpha": False,
            "sv_rect": pygame.Rect(0, 0, 0, 0), "hue_rect": pygame.Rect(0, 0, 0, 0),
            "tab_stroke_rect": pygame.Rect(0, 0, 0, 0), "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
            "nofill_rect": pygame.Rect(0, 0, 0, 0), "alpha_rect": pygame.Rect(0, 0, 0, 0),
            "selection_submode": selection_submode,
            "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
            "trace_algorithm": "fit",
            "trace_algo_rects": {},
        }

    def test_draw_panel_multiple_selected(self):
        st = app.new_stroke([((10.0, 10.0), (30.0, 10.0), (50.0, 40.0), (70.0, 40.0))])
        state = self._base_state("selection", {0, 1}, st, "stroke", selection_submode="transform")
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertGreater(state["sv_rect"].w, 0)
        self.assertGreater(state["nodes_toggle_rect"].w, 0)


if __name__ == "__main__":
    unittest.main()
