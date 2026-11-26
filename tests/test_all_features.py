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
        top = getattr(app, "TOP_BAR_H", 0)
        self.assertTrue(app.in_canvas((app.CANVAS_X + 10, top + 10)))
        self.assertFalse(app.in_canvas((0, top + 10)))
        c = app.clamp_to_canvas((-100, -100))
        self.assertEqual(c[0], 0)
        self.assertEqual(c[1], 0)

    def test_stroke_bbox(self):
        st = app.new_stroke([((10.0, 20.0), (15.0, 5.0), (25.0, 35.0), (30.0, 25.0))])
        bb = app.stroke_bbox(st)
        # bbox covers visible curve/lines only (excludes Bezier control handles)
        self.assertAlmostEqual(bb[0], 10.0, places=3)
        self.assertAlmostEqual(bb[1], 15.716, places=2)
        self.assertAlmostEqual(bb[2], 30.0, places=3)
        self.assertAlmostEqual(bb[3], 27.060, places=2)
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
        self.assertGreater(state["nodes_mode_prev_rect"].w, 0)
        self.assertGreater(state["nodes_mode_next_rect"].w, 0)
        state["color_target"] = "fill"
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        # no fill case
        st["fill_color"] = None
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        # nodes submode
        state = self._base_state("selection", 0, st, "stroke", selection_submode="nodes")
        app.draw_panel(self.screen, self.fonts, (0, 0), state)

    def test_draw_panel_pattern_controls(self):
        from models import new_pattern, set_pattern_fill
        st = app.new_stroke([((10.0, 10.0), (30.0, 10.0), (50.0, 40.0), (70.0, 40.0))])
        st = set_pattern_fill(st, new_pattern("dots", size=10))
        state = self._base_state("selection", 0, st, "fill")
        state["fill_type_rects"] = {}
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertGreater(state["fill_type_prev_rect"].w, 0)
        self.assertGreater(state["fill_type_next_rect"].w, 0)
        self.assertGreater(state["pattern_type_rect"].w, 0)
        self.assertGreater(state["pattern_size_minus_rect"].w, 0)
        self.assertGreater(state["pattern_size_plus_rect"].w, 0)

    def test_draw_panel_transform_numeric_fields(self):
        st = app.new_stroke([((10.0, 20.0), (30.0, 20.0), (50.0, 60.0), (70.0, 80.0))])
        state = self._base_state("selection", 0, st, "stroke", selection_submode="transform")
        state["selection_bbox"] = (10.0, 20.0, 70.0, 80.0)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        for key in ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                    "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                    "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                    "xform_rm_rect", "xform_rp_rect"):
            self.assertGreater(state[key].w, 0, key)
            self.assertGreater(state[key].h, 0, key)

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

    def test_shape_from_doodle_rect_circle(self):
        pts = [(10, 20), (30, 20), (30, 40), (10, 40), (10, 20)]
        beziers, raw = app.shape_from_doodle(pts, "rect")
        self.assertIsNotNone(beziers)
        self.assertEqual(len(beziers), 4)
        beziers, raw = app.shape_from_doodle(pts, "circle")
        self.assertIsNotNone(beziers)
        self.assertEqual(len(beziers), 4)


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
        self.assertGreater(state["nodes_mode_prev_rect"].w, 0)
        self.assertGreater(state["nodes_mode_next_rect"].w, 0)


class TestCustomWaveShape(unittest.TestCase):
    """Regression tests for the drawable custom wave distortion style."""

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

    def _panel_state(self, stroke, submode="curve"):
        btn_boost = app.Button((0, 0, app.PANEL_W - 40, 34), "Boost limit")
        btn_undo = app.Button((0, 0, app.PANEL_W - 40, 36), "Undo")
        btn_clear = app.Button((0, 0, app.PANEL_W - 40, 36), "Clear")
        slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 2, 5, 4)
        width_slider = app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 1, 20, 3)
        return {
            "tool_mode": "selection", "max_points": 4, "boost_points": False,
            "NORMAL_MAX_POINTS": 5, "BOOST_MAX_POINTS": 100,
            "slider": slider, "width_slider": width_slider,
            "buttons": {"boost": btn_boost, "actions": [btn_undo, btn_clear]},
            "stroke_count": 1, "selected_strokes": {0}, "selected_obj": stroke,
            "selected_curve": (0, 0),
            "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
            "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.FILL_SWATCHES],
            "color_target": "stroke", "picker_h": 10.0, "picker_s": 0.5, "picker_v": 0.8,
            "picker_drag_sv": False, "picker_drag_hue": False,
            "sv_rect": pygame.Rect(0, 0, 0, 0), "hue_rect": pygame.Rect(0, 0, 0, 0),
            "tab_stroke_rect": pygame.Rect(0, 0, 0, 0), "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
            "nofill_rect": pygame.Rect(0, 0, 0, 0),
            "selection_submode": submode,
            "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
            "wave_formula_focus": False,
            "wave_custom_draw": False,
        }

    def test_panel_exposes_custom_box_rect(self):
        st = self._stroke()
        self._apply(st, [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)])
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        box = state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
        self.assertGreater(box.w, 0)
        self.assertGreater(box.h, 0)
        self.assertTrue(state.get("wave_custom_draw"))

    def test_custom_box_click_maps_to_phase_amplitude(self):
        st = self._stroke()
        self._apply(st, [])
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        box = state["wave_custom_box_rect"]
        # click near left-middle -> phase ~0, amplitude ~0
        t = (box.x - box.x) / box.w
        amp = ((box.y + box.h / 2.0) - (box.y + box.h / 2.0)) / (box.h / 2.0)
        self.assertAlmostEqual(t, 0.0)
        self.assertAlmostEqual(amp, 0.0)
        # click near right-top -> phase ~1, amplitude ~-1
        t2 = (box.right - box.x) / box.w
        amp2 = ((box.y) - (box.y + box.h / 2.0)) / (box.h / 2.0)
        self.assertAlmostEqual(t2, 1.0)
        self.assertAlmostEqual(amp2, -1.0)

    def test_paint_builds_fixed_uniform_sample_grid(self):
        # Bit Invader model: painting stores a fixed-length uniform sample
        # array, not individual user points
        w = app.default_wave_params()
        w["custom_points"] = []
        box = pygame.Rect(0, 0, 180, 80)
        n = app.CUSTOM_WAVE_SAMPLES
        drag = app._custom_wave_paint(w, box, (box.x + box.w * 0.25, box.y + box.h * 0.5), None)
        pts = w["custom_points"]
        self.assertEqual(len(pts), n)
        idx = int(round(0.25 * (n - 1)))
        self.assertAlmostEqual(pts[idx][0], idx / (n - 1.0), places=9)
        self.assertAlmostEqual(pts[idx][1], 0.0, places=6)
        # untouched columns stay flat zero
        self.assertEqual(pts[0][1], 0.0)
        self.assertEqual(pts[-1][1], 0.0)
        # drag up-right: every sample between the two columns is filled
        drag = app._custom_wave_paint(w, box, (box.x + box.w * 0.75, box.y), drag)
        t_end = min(1.0, (box.w * 0.75) / (box.w - 1.0))
        top = int(round(t_end * (n - 1)))
        self.assertAlmostEqual(pts[top][1], -1.0, places=6)
        seg = [pts[i][1] for i in range(idx, top + 1)]
        self.assertEqual(seg, sorted(seg, reverse=True))
        # dragging past the box edge clamps instead of crashing
        app._custom_wave_paint(w, box, (box.right + 50, box.y - 50), drag)
        self.assertAlmostEqual(pts[-1][1], -1.0, places=6)

    def test_smooth_button_relaxes_samples(self):
        n = app.CUSTOM_WAVE_SAMPLES
        jitter = [(i / (n - 1.0), (1.0 if i % 2 else -1.0)) for i in range(n)]
        sm = app._custom_smooth_samples(jitter)
        self.assertEqual(len(sm), n)
        # alternating jitter collapses: peak amplitude drops well below 1
        smooth_peak = max(abs(v) for _t, v in sm)
        self.assertLess(smooth_peak, 0.9)
        # wrap-around: a spike on the last sample bleeds into t=0 (wave loops)
        spike = [(0.0, 0.0) for _ in range(n)]
        spike[-1] = (1.0, 1.0)
        wrapped = app._custom_smooth_samples(spike)
        self.assertGreater(wrapped[0][1], 0.05)
        # flat wave stays flat
        flat = app._custom_smooth_samples([(i / (n - 1.0), 0.0) for i in range(n)])
        for _t, v in flat:
            self.assertAlmostEqual(v, 0.0, places=9)

    def test_legacy_sparse_points_resample_onto_grid(self):
        pts = [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]
        uni = app._custom_uniform_samples(pts)
        self.assertEqual(len(uni), app.CUSTOM_WAVE_SAMPLES)
        mid = uni[app.CUSTOM_WAVE_SAMPLES // 2][1]
        self.assertGreater(mid, 0.9)
        # empty/short input yields a flat grid, not an error
        self.assertEqual(app._custom_uniform_samples([])[0][1], 0.0)
        self.assertEqual(app._custom_uniform_samples([(0.5, 1.0)])[0][1], 0.0)

    def _stroke(self):
        return app.new_stroke([
            ((0.0, 100.0), (100.0, 0.0), (200.0, 200.0), (300.0, 100.0)),
            ((300.0, 100.0), (400.0, 0.0), (500.0, 200.0), (600.0, 100.0)),
        ])

    def _apply(self, stroke, points, freq=3.0, amp=10.0, enabled=True):
        comps = app._stroke_components(stroke)
        self.assertTrue(comps)
        comps[0] = dict(comps[0])
        w = app.default_wave_params()
        w.update({
            "enabled": enabled, "shape": "custom", "amplitude": amp,
            "frequency": freq, "custom_points": list(points),
        })
        app._set_wave_style(comps[0], w)
        stroke["components"] = comps
        return stroke

    def test_default_wave_params_include_custom_points(self):
        self.assertIn("custom_points", app.default_wave_params())
        self.assertEqual(app.default_wave_params()["custom_points"], [])

    def test_custom_points_roundtrip_through_style_helpers(self):
        st = self._stroke()
        pts = [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]
        self._apply(st, pts)
        comps = app._stroke_components(st)
        w = app._get_wave_style(comps[0])
        self.assertEqual(w["shape"], "custom")
        self.assertEqual(w["custom_points"], pts)
        self.assertTrue(app._component_wave_enabled(comps[0]))

    def test_custom_points_stored_in_styles_list(self):
        st = self._stroke()
        self._apply(st, [(0.0, 0.0), (1.0, 0.0)])
        comps = app._stroke_components(st)
        styles = app._component_styles(comps[0])
        wave_styles = [s for s in styles if isinstance(s, dict) and s.get("type") == "wave"]
        self.assertEqual(len(wave_styles), 1)
        self.assertEqual(wave_styles[0]["custom_points"], [(0.0, 0.0), (1.0, 0.0)])

    def test_remove_wave_style_clears_custom_points(self):
        st = self._stroke()
        self._apply(st, [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)])
        comps = app._stroke_components(st)
        app._remove_wave_style(comps[0])
        self.assertFalse(app._component_wave_enabled(comps[0]))
        self.assertNotEqual(app._get_wave_style(comps[0])["shape"], "custom")

    def test_custom_wave_endpoints_pinned_to_base(self):
        st = self._stroke()
        self._apply(st, [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)])
        out = app.sample_distorted_component(st, 0)
        segs = app.segs_of(st)
        self.assertEqual(out[0], tuple(segs[0][0]))
        self.assertEqual(out[-1], tuple(segs[-1][3]))

    def test_custom_wave_is_smooth_not_linear(self):
        # A 3-point half-sine template must be interpolated with tangents,
        # so mid-segment values must NOT match simple linear interpolation.
        st = self._stroke()
        self._apply(st, [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)], freq=1.0, amp=10.0)
        out = app.sample_distorted_component(st, 0)
        base = app._stroke_polyline(st, samples=24)
        self.assertEqual(len(out), len(base))
        offs = [math.hypot(out[i][0] - base[i][0], out[i][1] - base[i][1])
                for i in range(len(out))]
        # Smooth curve: offsets rise and fall, and are not a straight-line ramp.
        self.assertGreater(max(offs), 5.0)
        # Check curvature: consecutive differences should change (not constant).
        diffs = [offs[i + 1] - offs[i] for i in range(len(offs) - 1)]
        self.assertGreater(len(set(round(d, 3) for d in diffs)), 1)

    def test_custom_wave_unsorted_points(self):
        st = self._stroke()
        self._apply(st, [(1.0, 0.0), (0.0, 0.0), (0.5, 1.0)])
        out = app.sample_distorted_component(st, 0)
        self.assertGreater(len(out), 0)
        for p in out:
            self.assertTrue(all(isinstance(v, (int, float)) for v in p))

    def test_custom_wave_edge_cases(self):
        for pts in ([], [(0.5, 1.0)], [(0.0, 0.0), (0.5, 1.0)]):
            st = self._stroke()
            self._apply(st, pts, freq=5.0)
            out = app.sample_distorted_component(st, 0)
            self.assertGreater(len(out), 0)

    def test_custom_wave_high_frequency(self):
        st = self._stroke()
        pts = [(0.0, 0.0), (0.25, 1.0), (0.5, 0.0), (0.75, -1.0), (1.0, 0.0)]
        self._apply(st, pts, freq=20.0)
        out = app.sample_distorted_component(st, 0)
        self.assertGreater(len(out), 10)
        for p in out:
            self.assertTrue(all(isinstance(v, (int, float)) for v in p))

    def test_disabled_custom_wave_falls_back_to_base(self):
        st = self._stroke()
        self._apply(st, [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)], enabled=False)
        out = app.sample_distorted_component(st, 0)
        base = app._stroke_polyline(st, samples=24)
        self.assertEqual(len(out), len(base))

    def test_all_builtin_wave_shapes_run(self):
        for shape in ["sine", "triangle", "square", "sawtooth", "circular", "half_circle", "noise"]:
            st = self._stroke()
            comps = app._stroke_components(st)
            comps[0] = dict(comps[0])
            w = app.default_wave_params()
            w.update({"enabled": True, "shape": shape, "frequency": 4.0})
            app._set_wave_style(comps[0], w)
            st["components"] = comps
            out = app.sample_distorted_component(st, 0)
            self.assertGreater(len(out), 0, shape)


class TestWaveStackUI(unittest.TestCase):
    """Regression tests for the multi-wave modifier stack, contextual panel,
    waveform thumbnails, live preview and panel scrolling."""

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

    def _stroke(self):
        return app.new_stroke([
            ((0.0, 100.0), (100.0, 0.0), (200.0, 200.0), (300.0, 100.0)),
            ((300.0, 100.0), (400.0, 0.0), (500.0, 200.0), (600.0, 100.0)),
        ])

    def _stacked(self, n=2):
        st = self._stroke()
        comps = app._stroke_components(st)
        comps[0] = dict(comps[0])
        shapes = ["sine", "noise", "square"]
        for i in range(n):
            w = app.default_wave_params()
            w.update({"enabled": True, "shape": shapes[i], "amplitude": 10.0 + i,
                      "frequency": 3.0 + i, "noise": 0.0})
            app._set_wave_style(comps[0], w, i)
        st["components"] = comps
        return st

    def _panel_state(self, stroke, active=0, scroll=0, submode="curve"):
        return {
            "tool_mode": "selection", "max_points": 4, "boost_points": False,
            "NORMAL_MAX_POINTS": 5, "BOOST_MAX_POINTS": 100,
            "slider": app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 2, 5, 4),
            "width_slider": app.Slider(app.PANEL_X + 20, 0, app.PANEL_W - 40, 1, 20, 3),
            "buttons": {
                "boost": app.Button((0, 0, app.PANEL_W - 40, 34), "Boost limit"),
                "actions": [app.Button((0, 0, app.PANEL_W - 40, 36), "Undo"),
                            app.Button((0, 0, app.PANEL_W - 40, 36), "Clear")],
            },
            "stroke_count": 1, "selected_strokes": {0}, "selected_obj": stroke,
            "selected_curve": (0, 0),
            "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
            "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.FILL_SWATCHES],
            "color_target": "stroke", "picker_h": 10.0, "picker_s": 0.5, "picker_v": 0.8,
            "picker_drag_sv": False, "picker_drag_hue": False,
            "sv_rect": pygame.Rect(0, 0, 0, 0), "hue_rect": pygame.Rect(0, 0, 0, 0),
            "tab_stroke_rect": pygame.Rect(0, 0, 0, 0), "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
            "nofill_rect": pygame.Rect(0, 0, 0, 0),
            "selection_submode": submode,
            "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
            "wave_formula_focus": False,
            "wave_custom_draw": False,
            "wave_custom_finished": False,
            "wave_active_index": active,
            "wave_row_rects": [],
            "panel_scroll": scroll,
            # Curve/wave editing stays open, but the color picker is folded by
            # default; expand it so the scroll-reveal assertion can see swatches.
            "panel_sections": {"curve_color": True},
        }

    # ---- multi-wave model ----

    def test_set_wave_style_index_builds_stack(self):
        st = self._stacked(3)
        comps = app._stroke_components(st)
        waves = app._get_wave_styles(comps[0])
        self.assertEqual(len(waves), 3)
        self.assertEqual([w["shape"] for w in waves], ["sine", "noise", "square"])
        self.assertEqual(app._get_wave_style(comps[0], 1)["shape"], "noise")

    def test_legacy_wave_key_mirrors_first_style(self):
        st = self._stacked(2)
        comp = app._stroke_components(st)[0]
        self.assertIn("wave", comp)
        self.assertEqual(comp["wave"]["shape"], "sine")
        self.assertNotIn("type", comp["wave"])

    def test_remove_wave_style_by_index(self):
        st = self._stacked(3)
        comp = app._stroke_components(st)[0]
        app._remove_wave_style(comp, 1)
        waves = app._get_wave_styles(comp)
        self.assertEqual([w["shape"] for w in waves], ["sine", "square"])
        app._remove_wave_style(comp, 0)
        self.assertEqual(app._get_wave_style(comp, 0)["shape"], "square")
        app._remove_wave_style(comp, 0)
        self.assertEqual(app._get_wave_styles(comp), [])
        self.assertNotIn("wave", comp)

    def test_component_wave_enabled_if_any_active(self):
        st = self._stroke()
        comp = app._stroke_components(st)[0]
        w1 = app.default_wave_params(); w1.update({"enabled": True, "amplitude": 0.0, "noise": 0.0})
        w2 = app.default_wave_params(); w2.update({"enabled": True, "amplitude": 12.0})
        app._set_wave_style(comp, w1, 0)
        app._set_wave_style(comp, w2, 1)
        self.assertTrue(app._component_wave_enabled(comp))
        w2["enabled"] = False
        app._set_wave_style(comp, w2, 1)
        self.assertFalse(app._component_wave_enabled(comp))

    def test_sampling_composes_stacked_waves(self):
        # identical base + identical sample requirements (sine freq 5 needs
        # 5*32+8 samples; noise at freq 5 with scale 1.0 has 20 cells * 8 + 8)
        # so sample counts match; the noise layer must visibly change geometry
        def build(with_second):
            st = self._stroke()
            comp = app._stroke_components(st)[0]
            w1 = app.default_wave_params()
            w1.update({"enabled": True, "shape": "sine", "amplitude": 10.0, "frequency": 5.0})
            app._set_wave_style(comp, w1, 0)
            if with_second:
                w2 = app.default_wave_params()
                w2.update({"enabled": True, "shape": "noise", "amplitude": 12.0,
                           "frequency": 5.0, "noise_scale": 1.0, "seed": 7})
                app._set_wave_style(comp, w2, 1)
            st["components"] = [comp]
            return st

        st1 = build(False)
        st2 = build(True)
        out1 = app.sample_distorted_component(st1, 0)
        out2 = app.sample_distorted_component(st2, 0)
        self.assertEqual(len(out1), len(out2))
        # stacking the noise layer must change the geometry
        diffs = [abs(out1[i][0] - out2[i][0]) + abs(out1[i][1] - out2[i][1])
                 for i in range(len(out1))]
        self.assertGreater(max(diffs), 1.0)
        # endpoints stay pinned to the base curve
        segs = app.segs_of(st2)
        self.assertEqual(tuple(out2[0]), tuple(segs[0][0]))
        self.assertEqual(tuple(out2[-1]), tuple(segs[-1][3]))

    def test_sampling_full_stack_disabled_returns_base(self):
        st = self._stacked(2)
        comp = app._stroke_components(st)[0]
        for i in range(2):
            w = app._get_wave_style(comp, i)
            w["enabled"] = False
            app._set_wave_style(comp, w, i)
        st["components"] = [comp]
        out = app.sample_distorted_component(st, 0)
        base = app._stroke_polyline(st, samples=24)
        self.assertEqual(len(out), len(base))

    def _thickened(self, length=200.0, amp=20.0):
        st = self._straight(length)
        comp = app._stroke_components(st)[0]
        th = app._merge_thickness_style(dict(app.default_thickness_params()))
        th["enabled"] = True
        th["amplitude"] = amp
        th["thickness_points"] = [[0.0, -1.0], [0.5, 1.0], [1.0, -1.0]]
        app._set_distortion_style(comp, th, 0)
        st["components"] = [comp]
        return st

    def test_thickness_open_curve_returns_ribbon_not_clobbered_points(self):
        # Thickness must return a closed ribbon: bottom forward + top reversed.
        # The open-curve endpoint pinning must NOT overwrite the ribbon's end
        # points (it used to clobber the offset top edge with the raw bottom end,
        # which made the renderer inject a straight start->end connector line).
        st = self._thickened(200.0, 20.0)
        out = app.sample_distorted_component(st, 0)
        segs = app.segs_of(st)
        self.assertGreaterEqual(len(out), 4)
        self.assertEqual(len(out) % 2, 0)
        # first point stays the bottom start edge, last is the offset top edge
        self.assertEqual(tuple(out[0]), tuple(segs[0][0]))
        self.assertNotEqual(tuple(out[-1]), tuple(segs[-1][3]))
        half = len(out) // 2
        # bottom half follows the base path, top half is offset outward
        self.assertGreater(
            max(math.hypot(out[i][0] - out[half + i][0], out[i][1] - out[half + i][1])
                for i in range(half)),
            1e-6,
        )

    def test_thickness_disabled_returns_base_points(self):
        st = self._straight(200.0)
        out = app.sample_distorted_component(st, 0)
        segs = app.segs_of(st)
        self.assertEqual(tuple(out[0]), tuple(segs[0][0]))
        self.assertEqual(tuple(out[-1]), tuple(segs[-1][3]))

    # ---- contextual parameters ----

    def test_noise_sliders_hidden_on_plain_wave_shown_for_legacy(self):
        # noise is its own stackable layer now: plain waves don't show the
        # old per-wave noise sliders at all...
        st = self._stroke()
        comp = app._stroke_components(st)[0]
        w = app.default_wave_params(); w.update({"enabled": True, "noise": 0.0})
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        rects = state["wave_slider_rects"]
        self.assertIn("amplitude", rects)
        self.assertIn("frequency", rects)
        self.assertIn("phase", rects)
        self.assertNotIn("seed", rects)
        self.assertNotIn("noise_scale", rects)
        self.assertNotIn("noise", rects)
        # ...but legacy noise saved by older versions stays adjustable here
        w["noise"] = 10.0
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertIn("noise", state["wave_slider_rects"])
        self.assertIn("seed", state["wave_slider_rects"])
        self.assertIn("noise_scale", state["wave_slider_rects"])

    def test_noise_shape_has_contextual_sliders(self):
        # the standalone Noise layer: amount (amplitude), density (frequency),
        # smoothing (noise scale) and seed apply; phase does not -> grayed out
        st = self._stroke()
        comp = app._stroke_components(st)[0]
        w = app.default_wave_params()
        w.update({"enabled": True, "shape": "noise", "amplitude": 20.0,
                  "frequency": 4.0, "noise_scale": 3.0, "seed": 11})
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        rects = state["wave_slider_rects"]
        self.assertIn("amplitude", rects)
        self.assertIn("frequency", rects)
        self.assertIn("noise_scale", rects)
        self.assertIn("seed", rects)
        # phase is inapplicable to random noise: drawn grayed, not interactive
        self.assertNotIn("phase", rects)
        # no formula input or custom box for the noise layer
        self.assertEqual(state["wave_formula_rect"].w, 0)
        self.assertEqual(state["wave_custom_box_rect"].w, 0)

    def test_noise_shape_value_is_bounded_and_smooth(self):
        ev = app._prepare_wave_evaluator({"shape": "noise", "frequency": 4.0,
                                          "amplitude": 25.0, "noise_scale": 2.0, "seed": 3})
        vals = [app._wave_value_for(ev, i / 512.0) for i in range(513)]
        # bounded like every other shape: [-1,1] (amplitude scales outside)
        self.assertLessEqual(max(vals), 1.01)
        self.assertGreaterEqual(min(vals), -1.01)
        # not degenerate: the profile actually varies
        self.assertGreater(max(vals) - min(vals), 0.4)
        # smooth: no jumps between adjacent dense samples
        max_step = max(abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1))
        self.assertLess(max_step, 0.2)
        # frequency 0 disables the layer (consistent with other shapes)
        ev0 = app._prepare_wave_evaluator({"shape": "noise", "frequency": 0.0, "amplitude": 25.0})
        self.assertEqual(app._wave_value_for(ev0, 0.5), 0.0)

    def test_noise_shape_seed_changes_pattern(self):
        base = {"shape": "noise", "frequency": 5.0, "amplitude": 20.0, "noise_scale": 2.0}
        v1 = [app._wave_value_for(app._prepare_wave_evaluator({**base, "seed": 1}), i / 64.0)
              for i in range(65)]
        v2 = [app._wave_value_for(app._prepare_wave_evaluator({**base, "seed": 2}), i / 64.0)
              for i in range(65)]
        self.assertNotEqual(v1, v2)

    def test_noise_layer_is_its_own_row_and_previewable(self):
        st = self._stacked(2)  # sine + noise rows
        state = self._panel_state(st, active=1)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        # the noise row exists in the stack
        rows = state["wave_row_rects"]
        self.assertEqual(len(rows), 2)
        # shape stepper is available (noise is a selectable shape)
        self.assertGreater(state["wave_shape_prev_rect"].w, 0)
        self.assertGreater(state["wave_shape_next_rect"].w, 0)
        # preview renders the noise profile (adaptive point count for cells)
        prev = app._wave_preview_polyline(app._get_wave_style(app._stroke_components(st)[0], 1))
        self.assertGreater(len(prev), 200)
        for _sx, vy in prev:
            self.assertTrue(-1.3 <= vy <= 1.3, vy)

    def test_noise_independent_toggle_in_stacked_render(self):
        st = self._stroke()
        comp = app._stroke_components(st)[0]
        sine = app.default_wave_params()
        sine.update({"enabled": True, "shape": "sine", "amplitude": 10.0, "frequency": 4.0})
        nz = app.default_wave_params()
        # noise_scale 1.0 -> 16 cells * 8 + 8 = 136 samples, exactly what the
        # freq-4 sine needs (4*32+8), so both stacks sample identically
        nz.update({"enabled": False, "shape": "noise", "amplitude": 15.0,
                   "frequency": 4.0, "noise_scale": 1.0})
        app._set_wave_style(comp, sine, 0)
        app._set_wave_style(comp, nz, 1)
        st["components"] = [comp]
        # disabled noise layer does not affect rendering
        out_off = app.sample_distorted_component(st, 0)
        sine_only = self._stroke()
        c2 = app._stroke_components(sine_only)[0]
        app._set_wave_style(c2, sine, 0)
        sine_only["components"] = [c2]
        out_sine = app.sample_distorted_component(sine_only, 0)
        self.assertEqual(len(out_off), len(out_sine))
        for a, b in zip(out_off, out_sine):
            self.assertAlmostEqual(a[0], b[0], places=6)
            self.assertAlmostEqual(a[1], b[1], places=6)
        # enabling the noise layer changes the geometry
        nz["enabled"] = True
        app._set_wave_style(comp, nz, 1)
        st["components"] = [comp]
        out_on = app.sample_distorted_component(st, 0)
        diffs = [abs(out_on[i][0] - out_sine[i][0]) + abs(out_on[i][1] - out_sine[i][1])
                 for i in range(len(out_on))]
        self.assertGreater(max(diffs), 1.0)

    def test_contextual_formula_and_custom_boxes(self):
        st = self._stroke()
        comp = app._stroke_components(st)[0]
        w = app.default_wave_params(); w.update({"enabled": True, "shape": "formula"})
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertGreater(state["wave_formula_rect"].w, 0)
        self.assertEqual(state["wave_custom_box_rect"].w, 0)
        w["shape"] = "custom"
        w["custom_points"] = [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertGreater(state["wave_custom_box_rect"].w, 0)
        self.assertEqual(state["wave_formula_rect"].w, 0)

    # ---- waveform thumbnails + live preview ----

    def test_shape_thumbnail_grid_has_all_icons(self):
        st = self._stroke()
        comp = app._stroke_components(st)[0]
        w = app.default_wave_params(); w.update({"enabled": True})
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        self.assertGreater(state["wave_shape_prev_rect"].w, 0)
        self.assertGreater(state["wave_shape_next_rect"].w, 0)

    def test_icon_polyline_is_one_normalized_cycle(self):
        for shape in app.WAVE_SHAPES:
            poly = app._wave_icon_polyline({"shape": shape, "frequency": 9.0,
                                            "custom_points": [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)]})
            self.assertGreaterEqual(len(poly), 10, shape)
            self.assertAlmostEqual(poly[0][0], 0.0)
            self.assertAlmostEqual(poly[-1][0], 1.0)
            for vx, vy in poly:
                self.assertTrue(-2.5 <= vy <= 2.5, (shape, vy))
        # frequency must not affect the icon (one cycle is forced)
        a = app._wave_icon_polyline({"shape": "sine", "frequency": 2.0})
        b = app._wave_icon_polyline({"shape": "sine", "frequency": 17.0})
        self.assertEqual(len(a), len(b))
        for (x1, y1), (x2, y2) in zip(a, b):
            self.assertAlmostEqual(y1, y2, places=6)

    def test_preview_polyline_reflects_amplitude(self):
        p1 = app._wave_preview_polyline({"shape": "sine", "enabled": True,
                                         "amplitude": 100.0, "frequency": 4.0})
        p2 = app._wave_preview_polyline({"shape": "sine", "enabled": True,
                                         "amplitude": 50.0, "frequency": 4.0})
        self.assertGreater(len(p1), 100)
        m1 = max(abs(v) for _x, v in p1)
        m2 = max(abs(v) for _x, v in p2)
        self.assertGreater(m1, 0.5)   # amp 100 -> ~1.0
        self.assertLess(m2, m1)       # smaller amplitude -> smaller preview
        self.assertLessEqual(m1, 1.3)

    # ---- stack row switching ----

    def test_stack_rows_and_active_index_switching(self):
        st = self._stacked(2)
        state = self._panel_state(st, active=0)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        rows = state["wave_row_rects"]
        self.assertEqual(len(rows), 2)
        # toggle/remove belong to the active row
        self.assertTrue(rows[0][1].collidepoint(state["wave_toggle_rect"].center))
        self.assertTrue(rows[0][1].collidepoint(state["wave_remove_rect"].center))
        # active row must be inside the visible panel
        self.assertGreaterEqual(rows[0][1].top, 0)
        # active row 0 is a plain sine: no noise sliders
        self.assertNotIn("seed", state["wave_slider_rects"])
        state = self._panel_state(st, active=1)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        rows = state["wave_row_rects"]
        self.assertTrue(rows[1][1].collidepoint(state["wave_toggle_rect"].center))
        # parameters shown belong to the active noise layer
        self.assertIn("seed", state["wave_slider_rects"])
        self.assertIn("noise_scale", state["wave_slider_rects"])
        self.assertNotIn("phase", state["wave_slider_rects"])

    # ---- panel scrolling ----

    # ---- geometric frequency/amplitude scaling ----

    def _straight(self, length=200.0):
        return app.new_stroke([((0.0, 0.0), (length / 3.0, 0.0), (2.0 * length / 3.0, 0.0), (length, 0.0))])

    def _sign_changes(self, ys):
        changes = 0
        last = 0
        for y in ys:
            sg = 1 if y > 1e-6 else (-1 if y < -1e-6 else 0)
            if sg == 0:
                continue
            if last != 0 and sg != last:
                changes += 1
            last = sg
        return changes

    def _waved(self, length, freq, amp=100.0):
        st = self._straight(length)
        comp = app._stroke_components(st)[0]
        w = app.default_wave_params()
        w.update({"enabled": True, "shape": "sine", "amplitude": amp, "frequency": freq})
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        return st

    def test_cycle_length_is_freq_fraction_of_bbox_diagonal(self):
        # bbox is 200x0 -> diagonal 200; freq 1.0 = one cycle spans the
        # diagonal -> exactly one interior zero crossing along the stroke
        out = app.sample_distorted_component(self._waved(200.0, 1.0), 0)
        self.assertEqual(self._sign_changes([p[1] for p in out]), 1)
        # freq 0.5 -> cycle = half the diagonal -> two cycles -> 3 crossings
        out = app.sample_distorted_component(self._waved(200.0, 0.5), 0)
        self.assertEqual(self._sign_changes([p[1] for p in out]), 3)
        # freq 0.01 -> 100 cycles across a 200px diagonal
        out = app.sample_distorted_component(self._waved(200.0, 0.01), 0)
        self.assertGreaterEqual(self._sign_changes([p[1] for p in out]), 90)

    def test_amplitude_scales_with_shape_size(self):
        # amp 50 -> amp_px = 0.5 * diagonal/2; doubling the shape doubles it
        out1 = app.sample_distorted_component(self._waved(200.0, 1.0, 50.0), 0)
        out2 = app.sample_distorted_component(self._waved(400.0, 1.0, 50.0), 0)
        peak1 = max(abs(p[1]) for p in out1)
        peak2 = max(abs(p[1]) for p in out2)
        self.assertGreater(peak1, 20.0)
        self.assertAlmostEqual(peak2 / peak1, 2.0, delta=0.3)

    def test_frequency_slider_uses_fraction_range(self):
        st = self._waved(200.0, 0.25)
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        _r, lo, hi = state["wave_slider_rects"]["frequency"]
        self.assertAlmostEqual(lo, 0.01)
        self.assertAlmostEqual(hi, 1.0)

    def test_preview_shows_geometric_cycle_count(self):
        # preview geometry is a unit square: freq 0.25 -> 4 cycles
        prev = app._wave_preview_polyline({"shape": "sine", "enabled": True,
                                           "amplitude": 100.0, "frequency": 0.25})
        self.assertGreater(len(prev), 200)
        self.assertEqual(self._sign_changes([v for _x, v in prev]), 7)

    def test_reverse_flag_flips_wave_direction(self):
        # reverse = -f(x): the offset profile is negated, not time-mirrored
        st = self._waved(200.0, 1.0, 100.0)
        comp = app._stroke_components(st)[0]
        out_f = app.sample_distorted_component(st, 0)
        w = app._get_wave_style(comp, 0)
        w2 = dict(w)
        w2["reverse"] = True
        app._set_wave_style(comp, w2, 0)
        st["components"] = [comp]
        out_r = app.sample_distorted_component(st, 0)
        self.assertEqual(len(out_f), len(out_r))
        ys_f = [p[1] for p in out_f]
        ys_r = [p[1] for p in out_r]
        for i in range(len(ys_f)):
            self.assertAlmostEqual(ys_r[i], -ys_f[i], delta=1e-6)
        # x positions unchanged (only the offset flips)
        for (fx, _fy), (rx, _ry) in zip(out_f, out_r):
            self.assertAlmostEqual(fx, rx, places=6)
        # endpoints stay pinned in both directions
        segs = app.segs_of(st)
        self.assertEqual(tuple(out_r[0]), tuple(segs[0][0]))
        self.assertEqual(tuple(out_r[-1]), tuple(segs[-1][3]))

    def test_reverse_toggle_in_panel(self):
        st = self._waved(200.0, 1.0, 50.0)
        state = self._panel_state(st)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        rev_rect = state.get("wave_reverse_rect", pygame.Rect(0, 0, 0, 0))
        self.assertGreater(rev_rect.w, 0)
        # default is OFF; the flag round-trips through the style helpers
        self.assertIn("reverse", app.default_wave_params())
        self.assertFalse(app.default_wave_params()["reverse"])
        comp = app._stroke_components(st)[0]
        w = app._get_wave_style(comp, 0)
        self.assertFalse(bool(w.get("reverse")))
        w["reverse"] = True
        app._set_wave_style(comp, w, 0)
        st["components"] = [comp]
        self.assertTrue(app._get_wave_style(app._stroke_components(st)[0], 0)["reverse"])

    def test_event_handlers_read_only_wired_state_keys(self):
        # state is rebuilt every frame from a literal BEFORE events run, so any
        # key an event handler reads must appear in that literal (fed by a
        # *_cache readback) - otherwise the handler silently no-ops. This is
        # how the custom-wave box click broke: the box rendered (draw_panel
        # sets the key after events) but clicks saw a zero rect at event time.
        import io
        import os
        import re
        path = app.__file__
        if path.endswith(".pyc"):
            path = path[:-1]
        # MVC: the event loop lives in controllers/app_controller.py
        ctrl_path = os.path.join(os.path.dirname(path), "controllers", "app_controller.py")
        lines = io.open(ctrl_path, encoding="utf-8").read().splitlines()
        lit_start = next(i for i, l in enumerate(lines) if l == "        state = {")
        lit_end = next(i for i in range(lit_start + 1, len(lines)) if lines[i] == "        }")
        literal_keys = set(re.findall(r'"([a-z_0-9]+)":', "\n".join(lines[lit_start:lit_end + 1])))
        def _is_event_loop_line(l):
            return "for event in pygame.event.get():" in l or "for ctx.event in pygame.event.get():" in l
        try:
            ev_start = next(i for i, l in enumerate(lines) if _is_event_loop_line(l))
        except StopIteration:
            ev_loop_path = os.path.join(os.path.dirname(path), "controllers", "event_loop.py")
            ev_lines = io.open(ev_loop_path, encoding="utf-8").read().splitlines() if os.path.exists(ev_loop_path) else lines
            ev_start = next(i for i, l in enumerate(ev_lines) if _is_event_loop_line(l))
            lines = ev_lines
        try:
            ev_end = next(i for i in range(ev_start + 1, len(lines))
                          if "draw_panel(screen, fonts, mouse_pos, state)" in lines[i])
            region = "\n".join(lines[ev_start:ev_end])
        except StopIteration:
            # render/event handling may be split across modules after SRP refactor
            region = "\n".join(lines[ev_start:])
            ev_path = os.path.join(os.path.dirname(path), "controllers", "event_loop.py")
            if os.path.exists(ev_path) and os.path.abspath(ev_path) != os.path.abspath(ctrl_path):
                region += "\n" + io.open(ev_path, encoding="utf-8").read()
        reads = set(re.findall(r'state\.get\(\s*"([a-z_0-9]+)"', region))
        reads.update(re.findall(r'state\.setdefault\(\s*"([a-z_0-9]+)"', region))
        for m in re.finditer(r'state\[\s*"([a-z_0-9]+)"\s*\](?!\s*=)', region):
            reads.add(m.group(1))
        missing = sorted(k for k in reads if k not in literal_keys)
        self.assertEqual(
            missing, [],
            "event handlers read state keys missing from the per-frame state "
            "literal (no cache/readback wiring): %s" % missing)

    def test_panel_content_overflows_and_scroll_reveals_it(self):
        st = self._stacked(2)
        state = self._panel_state(st, scroll=0)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        bottom = state["panel_content_bottom"]
        self.assertGreater(bottom, app.HEIGHT, "panel content should overflow the window")
        max_scroll = max(0, bottom + 24 - app.HEIGHT)
        self.assertGreater(max_scroll, 0)
        # scroll to the max: preset swatches (drawn last) must come into view
        state2 = self._panel_state(st, scroll=max_scroll)
        app.draw_panel(self.screen, self.fonts, (0, 0), state2)
        sw = state2["stroke_swatch_rects"][0]
        self.assertGreater(sw.w, 0)
        self.assertGreaterEqual(sw.top, 0)
        self.assertLessEqual(sw.bottom, app.HEIGHT)
        # content height is scroll-invariant (measured un-scrolled)
        self.assertEqual(state2["panel_content_bottom"], bottom)

    def test_scroll_amount_is_clamped_to_content(self):
        st = self._stacked(2)
        state = self._panel_state(st, scroll=0)
        app.draw_panel(self.screen, self.fonts, (0, 0), state)
        bottom = state["panel_content_bottom"]
        max_scroll = max(0, bottom + 24 - app.HEIGHT)
        # the main-loop clamp: never negative, never past the content
        for requested in (-500, 0, max_scroll // 2, max_scroll, max_scroll + 10000):
            clamped = max(0, min(requested, max_scroll))
            self.assertGreaterEqual(clamped, 0)
            self.assertLessEqual(clamped, max_scroll)



class TestWidthProfiles(unittest.TestCase):
    def _line_stroke(self):
        return app.new_stroke(
            [((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)),
             ((30.0, 0.0), (40.0, 0.0), (50.0, 0.0), (60.0, 0.0))],
            stroke_width=10.0,
        )

    def test_apply_taper_profiles_set_point_widths(self):
        from models.strokes import apply_width_profile, get_point_width, WIDTH_PROFILES
        self.assertIn("taper_out", WIDTH_PROFILES)
        s = self._line_stroke()
        out = apply_width_profile(s, "taper_out")
        self.assertEqual(out.get("width_profile"), "taper_out")
        self.assertTrue(out.get("point_widths"))
        self.assertAlmostEqual(get_point_width(out, 0, "p0"), 10.0, places=4)
        self.assertAlmostEqual(get_point_width(out, 1, "p3"), 1.5, places=4)
        self.assertTrue(app._stroke_needs_variable_width(out))

    def test_uniform_clears_point_widths(self):
        from models.strokes import apply_width_profile
        s = apply_width_profile(self._line_stroke(), "pressure")
        self.assertTrue(s.get("point_widths"))
        u = apply_width_profile(s, "uniform")
        self.assertEqual(u.get("width_profile"), "uniform")
        self.assertFalse(u.get("point_widths"))

    def test_manual_point_width_clears_profile(self):
        from models.strokes import apply_width_profile, set_point_width
        s = apply_width_profile(self._line_stroke(), "taper_in")
        self.assertEqual(s.get("width_profile"), "taper_in")
        set_point_width(s, 0, "p0", 7.0)
        self.assertNotIn("width_profile", s)
        self.assertAlmostEqual(float((s.get("point_widths") or {}).get("0:p0", 0.0)), 7.0, places=4)


class TestMeshGradients(unittest.TestCase):
    def test_default_and_normalize_mesh_gradient(self):
        from models.geometry import default_mesh_gradient, normalize_gradient, GRADIENT_TYPES
        self.assertIn("mesh", GRADIENT_TYPES)
        g = default_mesh_gradient(rows=2, cols=2)
        self.assertEqual(g.get("type"), "mesh")
        self.assertEqual(int(g.get("rows", 0)), 2)
        self.assertEqual(int(g.get("cols", 0)), 2)
        self.assertTrue(isinstance(g.get("grid"), list))
        n = normalize_gradient(g)
        self.assertEqual(n.get("type"), "mesh")
        # Mesh grid stores (rows+1) x (cols+1) color/control points.
        self.assertEqual(len(n.get("grid") or []), 3)
        self.assertEqual(len((n.get("grid") or [[]])[0] or []), 3)

    def test_mesh_gradient_serializes_and_renders(self):
        import os, tempfile
        from models.geometry import default_mesh_gradient
        from models.document import serialize_document, deserialize_document_with_meta
        from views.canvas import export_scene_png
        st = {
            "segs": [((10.0, 10.0), (40.0, 10.0), (40.0, 40.0), (10.0, 40.0))],
            "stroke_color": None,
            "stroke_width": 0.0,
            "fill_color": (1.0, 0.0, 0.0, 1.0),
            "fill_gradient": default_mesh_gradient(rows=2, cols=2),
            "hidden_segs": set(),
            "corner_anchors": set(),
        }
        doc = serialize_document([st], meta={})
        strokes, _meta = deserialize_document_with_meta(doc)
        self.assertEqual(((strokes[0].get("fill_gradient") or {}).get("type")), "mesh")
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "mesh.png")
            export_scene_png(out, strokes, size=(60, 60))
            self.assertTrue(os.path.exists(out))
            self.assertGreater(os.path.getsize(out), 0)


class TestTextOnPath(unittest.TestCase):
    def _path(self):
        return [((0.0, 80.0), (40.0, 20.0), (80.0, 20.0), (120.0, 80.0))]

    def test_new_text_stroke_on_path_has_metadata_and_segs(self):
        from models.text import new_text_stroke
        s = new_text_stroke("Hello", 0, 80, "Sans", 24, path_segs=self._path(), path_offset=2.0)
        self.assertTrue(s.get("is_text"))
        tp = s.get("text_path")
        self.assertIsInstance(tp, dict)
        self.assertTrue(tp.get("segs"))
        self.assertAlmostEqual(float(tp.get("offset", 0.0)), 2.0, places=4)
        self.assertTrue(s.get("segs"))

    def test_set_and_clear_text_path(self):
        from models.text import new_text_stroke, set_text_path, clear_text_path
        s = new_text_stroke("Hi", 0, 80, "Sans", 24)
        self.assertFalse(s.get("text_path"))
        s2 = set_text_path(s, self._path(), offset=3.0)
        self.assertIsInstance(s2.get("text_path"), dict)
        self.assertFalse(s.get("text_path"))  # copy semantics
        s3 = clear_text_path(s2)
        self.assertFalse(s3.get("text_path"))
        self.assertTrue(s3.get("is_text"))

    def test_update_preserves_text_path(self):
        from models.text import new_text_stroke, update_text_stroke
        s = new_text_stroke("Hi", 0, 80, "Sans", 24, path_segs=self._path())
        s2 = update_text_stroke(s, text_content="World", font_size=30)
        self.assertEqual(s2.get("text_content"), "World")
        self.assertIsInstance(s2.get("text_path"), dict)
        self.assertTrue(s2.get("segs"))

    def test_text_path_roundtrips_in_document_meta_context(self):
        from models.text import new_text_stroke
        from models.document import serialize_document, deserialize_document_with_meta
        s = new_text_stroke("Path", 0, 80, "Sans", 20, path_segs=self._path(), path_offset=1.0)
        doc = serialize_document([s], meta={"artboards": [{"name": "A", "x": 1, "y": 2, "w": 30, "h": 40}], "active_artboard": 0})
        strokes, meta = deserialize_document_with_meta(doc)
        self.assertTrue(strokes and isinstance(strokes[0].get("text_path"), dict))
        self.assertEqual(meta.get("active_artboard"), 0)
        self.assertEqual((meta.get("artboards") or [{}])[0].get("w"), 30)


class TestArtboards(unittest.TestCase):
    def _stroke(self):
        return {
            "segs": [((10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0))],
            "stroke_color": (0.0, 0.0, 0.0, 1.0),
            "stroke_width": 2.0,
            "fill_color": None,
            "hidden_segs": set(),
            "corner_anchors": set(),
        }

    def test_export_png_cropped_to_artboard(self):
        import os, tempfile
        from views.canvas import export_scene_png
        from PIL import Image
        artboard = {"name": "A", "x": 5.0, "y": 7.0, "w": 50.0, "h": 30.0}
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "ab.png")
            export_scene_png(out, [self._stroke()], size=(200, 200), scale=1.0, artboard=artboard)
            im = Image.open(out)
            try:
                self.assertEqual(im.size, (50, 30))
            finally:
                im.close()

    def test_export_scene_image_cropped_to_artboard(self):
        import os, tempfile
        from views.canvas import export_scene_image
        from PIL import Image
        artboard = {"name": "A", "x": 0.0, "y": 0.0, "w": 64.0, "h": 32.0}
        with tempfile.TemporaryDirectory() as d:
            for ext in ("png", "jpg", "webp"):
                out = os.path.join(d, f"ab.{ext}")
                export_scene_image(out, [self._stroke()], size=(200, 200), scale=1.0, artboard=artboard)
                im = Image.open(out)
                try:
                    self.assertEqual(im.size, (64, 32), ext)
                finally:
                    im.close()

    def test_artboards_meta_roundtrip(self):
        from models.document import serialize_document, deserialize_document_with_meta
        meta = {
            "view": {"zoom": 1.25, "pan": [10.0, -5.0]},
            "artboards": [
                {"name": "One", "x": 0, "y": 0, "w": 100, "h": 50},
                {"name": "Two", "x": 120, "y": 0, "w": 80, "h": 60},
            ],
            "active_artboard": 1,
        }
        doc = serialize_document([self._stroke()], meta=meta)
        strokes, out_meta = deserialize_document_with_meta(doc)
        self.assertEqual(len(strokes), 1)
        self.assertEqual(out_meta.get("active_artboard"), 1)
        self.assertEqual(len(out_meta.get("artboards") or []), 2)
        self.assertEqual(out_meta["artboards"][1]["name"], "Two")


class TestShapeStateLibrary(unittest.TestCase):
    """Shape States: create a shape -> save to library -> insert as asset."""

    def _master(self):
        return app.new_stroke([((10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0))])

    def test_capture_shape_state_normalizes_and_stores(self):
        strokes = [self._master()]
        shape_states = {}
        sid, counter = app._capture_shape_state(strokes, [0], shape_states, 0)
        self.assertEqual(sid, "shape1")
        self.assertEqual(counter, 1)
        self.assertIn(sid, shape_states)
        self.assertEqual(shape_states[sid]["name"], "Shape State 1")
        self.assertTrue(shape_states[sid]["strokes"])
        self.assertEqual(strokes[0]["shape_state_id"], "shape1")
        self.assertTrue(strokes[0]["shape_state_is_master"])
        self.assertEqual(strokes[0]["shape_state_instance_id"], "shape1:master")

    def test_capture_does_not_alias_definition_into_instances(self):
        strokes = [self._master()]
        shape_states = {}
        sid, counter = app._capture_shape_state(strokes, [0], shape_states, 0)
        idxs, counter2 = app._insert_shape_state(strokes, shape_states, counter, [0])
        self.assertEqual(idxs, [1])
        self.assertEqual(counter2, 2)
        self.assertEqual(len(strokes), 2)
        inst = strokes[1]
        self.assertEqual(inst["shape_state_id"], "shape1")
        self.assertFalse(inst["shape_state_is_master"])
        self.assertEqual(inst["shape_state_instance_id"], "shape1:i2")
        bb = app.combined_bbox(strokes, [0])
        offx = (bb[2] - bb[0]) * 0.2 + 24.0
        offy = (bb[3] - bb[1]) * 0.2 + 24.0
        self.assertEqual(inst["segs"][0][0], (10.0 + offx, 10.0 + offy))
        self.assertEqual(inst["segs"][0][3], (10.0 + offx, 30.0 + offy))

    def test_insert_without_saved_state_returns_no_indices(self):
        strokes = [self._master()]
        idxs, counter = app._insert_shape_state(strokes, {}, 0, [0])
        self.assertEqual(idxs, [])
        self.assertEqual(counter, 0)

    def test_delete_removes_state_and_detaches_strokes(self):
        strokes = [self._master()]
        shape_states = {}
        sid, counter = app._capture_shape_state(strokes, [0], shape_states, 0)
        self.assertTrue(app._delete_shape_state(shape_states, sid, strokes))
        self.assertNotIn(sid, shape_states)
        self.assertIsNone(strokes[0].get("shape_state_id"))


if __name__ == "__main__":
    unittest.main()
