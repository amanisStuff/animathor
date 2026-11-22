"""Regression tests for the vector-editor capability gaps.

Covers boolean completeness, native-document fidelity, path editing, stroke
styling, distribution and export format dispatch.
"""

import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from models import boolean  # noqa: E402
from models import document  # noqa: E402
from models import strokes as strokes_model  # noqa: E402


def rect_stroke(x, y, w, h):
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    segs = [(corners[i], corners[i], corners[(i + 1) % 4], corners[(i + 1) % 4])
            for i in range(4)]
    return strokes_model.new_stroke(segs, fill_color=(0.5, 0.5, 0.5, 1.0),
                                    stroke_width=0.0)


class TestBooleanCompleteness(unittest.TestCase):
    def test_public_operations(self):
        self.assertEqual(boolean.OPERATIONS,
                         ("union", "intersection", "difference", "exclude"))
        self.assertEqual(boolean.SUBTRACT, boolean.DIFFERENCE)

    def test_exclude_is_xor(self):
        a = rect_stroke(0, 0, 10, 10)
        b = rect_stroke(5, 5, 10, 10)
        loops, _ = boolean.boolean_loops([a, b], op=boolean.EXCLUDE)
        # Two disjoint lobes: A-only and B-only (the overlap cancels out).
        self.assertEqual(len(loops), 2)

    def test_exclude_of_identical_shapes_is_empty(self):
        a = rect_stroke(0, 0, 10, 10)
        b = rect_stroke(0, 0, 10, 10)
        loops, _ = boolean.boolean_loops([a, b], op=boolean.EXCLUDE)
        self.assertEqual(loops, [])

    def test_subtract_and_difference_agree(self):
        a = rect_stroke(0, 0, 10, 10)
        b = rect_stroke(5, 5, 10, 10)
        self.assertEqual(boolean.boolean_loops([a, b], op=boolean.SUBTRACT),
                         boolean.boolean_loops([a, b], op=boolean.DIFFERENCE))

    def test_boolean_result_returns_components(self):
        a = rect_stroke(0, 0, 10, 10)
        b = rect_stroke(5, 5, 10, 10)
        result = boolean.boolean_result([a, b], op=boolean.EXCLUDE)
        self.assertIsNotNone(result)
        segs, comps, corners = result
        self.assertGreaterEqual(len(segs), 3)
        self.assertTrue(comps)
        self.assertIsInstance(corners, set)


class TestDocumentFidelity(unittest.TestCase):
    def test_set_fields_and_meta_roundtrip(self):
        st = strokes_model.new_stroke(
            [((0, 0), (1, 1), (2, 2), (3, 3))],
            corner_anchors={(0, "p0"), (3, "p3")},
        )
        st["hidden_segs"] = {5}
        meta = {"view": {"zoom": 2.5, "pan": [10.0, -4.0]}}
        with tempfile.TemporaryDirectory() as tmp:
            for ext in (".json", ".athors"):
                path = os.path.join(tmp, "doc" + ext)
                document.save_document(path, [st], meta)
                loaded, loaded_meta = document.load_document_with_meta(path)
                self.assertEqual(loaded[0]["corner_anchors"], st["corner_anchors"])
                self.assertEqual(loaded[0]["hidden_segs"], {5})
                self.assertEqual(loaded_meta, meta)

    def test_legacy_string_sets_are_recovered(self):
        payload = {
            "strokes": [{
                "segs": [[[0, 0], [1, 1], [2, 2], [3, 3]]],
                "corner_anchors": "{(0, 'p0')}",
            }],
            "meta": {},
        }
        import json
        strokes, _ = document.deserialize_document_with_meta(json.dumps(payload))
        self.assertIn((0, "p0"), strokes[0]["corner_anchors"])


class TestPathEditing(unittest.TestCase):
    def test_close_open_roundtrip(self):
        # An open three-sided polyline (rect_stroke is already closed).
        pts = [(0, 0), (10, 0), (10, 10)]
        st = strokes_model.new_stroke([(pts[i], pts[i], pts[i + 1], pts[i + 1])
                                       for i in range(len(pts) - 1)])
        self.assertFalse(strokes_model._is_closed_segs(strokes_model.segs_of(st)))
        closed = strokes_model.set_path_closed(st, True)
        self.assertTrue(strokes_model._is_closed_segs(strokes_model.segs_of(closed)))
        self.assertIn((0, "p0"), closed["corner_anchors"])
        opened = strokes_model.set_path_closed(closed, False)
        self.assertFalse(strokes_model._is_closed_segs(strokes_model.segs_of(opened)))
        self.assertEqual(len(strokes_model.segs_of(opened)), 2)

    def test_add_and_delete_anchor(self):
        st = strokes_model.new_stroke([((0, 0), (0, 10), (10, 10), (10, 0))])
        added = strokes_model.add_anchor_at(st, 0, 0.5)
        self.assertEqual(len(strokes_model.segs_of(added)), 2)
        deleted = strokes_model.delete_anchor(added, 0, "p0")
        self.assertEqual(len(strokes_model.segs_of(deleted)), 1)

    def test_smooth_corner_conversion(self):
        st = strokes_model.new_stroke([((0, 0), (0, 10), (10, 10), (10, 0))])
        corner = strokes_model.set_anchor_smooth(st, 0, "p0", smooth=False)
        self.assertTrue(strokes_model.is_corner_anchor(corner, 0, "p0"))
        smooth = strokes_model.set_anchor_smooth(corner, 0, "p0", smooth=True)
        self.assertFalse(strokes_model.is_corner_anchor(smooth, 0, "p0"))

    def test_reverse_preserves_geometry(self):
        st = rect_stroke(0, 0, 10, 10)
        rev = strokes_model.reverse_stroke(st)
        self.assertEqual(strokes_model.stroke_start(rev), strokes_model.stroke_end(st))
        self.assertEqual(strokes_model.stroke_end(rev), strokes_model.stroke_start(st))


class TestStrokeStyling(unittest.TestCase):
    def test_defaults_preserve_round_solid_appearance(self):
        st = strokes_model.new_stroke([])
        self.assertEqual(st["line_cap"], "round")
        self.assertEqual(st["line_join"], "round")
        self.assertEqual(st["miter_limit"], 10.0)
        self.assertIsNone(st["dash"])

    def test_dash_normalization(self):
        from views.canvas import normalize_dash
        self.assertIsNone(normalize_dash(None))
        self.assertIsNone(normalize_dash("solid"))
        self.assertEqual(normalize_dash("dashed"), (12.0, 8.0))
        self.assertEqual(normalize_dash([3, 2, 1]), [3.0, 2.0, 1.0])
        self.assertIsNone(normalize_dash([0, 0]))

    def test_apply_stroke_style_sets_all_fields(self):
        from views.canvas import apply_stroke_style

        class Recorder:
            def __init__(self):
                self.calls = []

            def __getattr__(self, name):
                def record(*args):
                    self.calls.append((name, args))
                return record

        ctx = Recorder()
        apply_stroke_style(ctx, {"line_cap": "butt", "line_join": "bevel",
                                 "miter_limit": 4.0, "dash": "dashed"}, 6.0)
        names = [c[0] for c in ctx.calls]
        self.assertIn("set_line_cap", names)
        self.assertIn("set_line_join", names)
        self.assertIn("set_miter_limit", names)
        dash_call = next(c for c in ctx.calls if c[0] == "set_dash")
        self.assertEqual(len(dash_call[1][0]), 2)


class TestDistribution(unittest.TestCase):
    def test_horizontal_spacing_is_even(self):
        from models.geometry import distribute_offsets
        boxes = [(0, 0, 10, 10), (20, 0, 30, 10), (90, 0, 100, 10)]
        offsets = distribute_offsets(boxes, "h")
        moved = [(b[0] + dx, b[2] + dx) for b, (dx, _dy) in zip(boxes, offsets)]
        gaps = [moved[i + 1][0] - moved[i][1] for i in range(len(moved) - 1)]
        self.assertAlmostEqual(gaps[0], gaps[1], places=6)
        self.assertEqual(offsets[0], (0.0, 0.0))
        self.assertEqual(offsets[-1], (0.0, 0.0))

    def test_vertical_spacing_is_even(self):
        from models.geometry import distribute_offsets
        boxes = [(0, 0, 10, 10), (0, 15, 10, 25), (0, 80, 10, 90)]
        offsets = distribute_offsets(boxes, "v")
        moved = [(b[1] + dy, b[3] + dy) for b, (_dx, dy) in zip(boxes, offsets)]
        gaps = [moved[i + 1][0] - moved[i][1] for i in range(len(moved) - 1)]
        self.assertAlmostEqual(gaps[0], gaps[1], places=6)

    def test_fewer_than_three_is_noop(self):
        from models.geometry import distribute_offsets
        self.assertEqual(distribute_offsets([(0, 0, 1, 1), (5, 0, 6, 1)], "h"),
                         [(0.0, 0.0), (0.0, 0.0)])


class TestExportFormats(unittest.TestCase):
    def test_supported_extensions_dispatch(self):
        from views.canvas import export_format_for, EXPORT_FORMATS
        self.assertEqual(export_format_for("a.png"), "PNG")
        self.assertEqual(export_format_for("a.SVG"), "SVG")
        self.assertEqual(export_format_for("a.pdf"), "PDF")
        self.assertEqual(export_format_for("a.eps"), "EPS")
        self.assertEqual(export_format_for("a.jpg"), "JPEG")
        self.assertEqual(export_format_for("a.jpeg"), "JPEG")
        self.assertEqual(export_format_for("a.webp"), "WEBP")
        self.assertIsNone(export_format_for("a.txt"))
        self.assertEqual(len(EXPORT_FORMATS), 7)

    def test_unknown_extension_rejected(self):
        from views.canvas import export_scene_image
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                export_scene_image(os.path.join(tmp, "bad.gif"), [])

    def test_normalize_export_scale(self):
        from views.canvas import normalize_export_scale
        self.assertEqual(normalize_export_scale(None), 1.0)
        self.assertEqual(normalize_export_scale(0), 1.0)
        self.assertEqual(normalize_export_scale(-2), 1.0)
        self.assertEqual(normalize_export_scale(2.5), 2.5)
        self.assertEqual(normalize_export_scale(99), 10.0)

    def _scene(self):
        return [rect_stroke(2, 2, 40, 30)]

    def test_png_2x_dimensions(self):
        from views.canvas import export_scene_image
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.png")
            export_scene_image(path, self._scene(), size=(100, 80), scale=2.0)
            with Image.open(path) as img:
                self.assertEqual(img.size, (200, 160))

    def test_jpeg_and_webp_magic(self):
        from views.canvas import export_scene_image
        with tempfile.TemporaryDirectory() as tmp:
            jpg = os.path.join(tmp, "out.jpg")
            webp = os.path.join(tmp, "out.webp")
            export_scene_image(jpg, self._scene(), size=(80, 60))
            export_scene_image(webp, self._scene(), size=(80, 60))
            with open(jpg, "rb") as handle:
                self.assertEqual(handle.read(2), b"\xff\xd8")
            with open(webp, "rb") as handle:
                head = handle.read(12)
            self.assertEqual(head[:4], b"RIFF")
            self.assertEqual(head[8:12], b"WEBP")

    def test_pdf_and_eps_headers(self):
        from views.canvas import export_scene_image
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "out.pdf")
            eps = os.path.join(tmp, "out.eps")
            export_scene_image(pdf, self._scene(), size=(80, 60))
            export_scene_image(eps, self._scene(), size=(80, 60))
            with open(pdf, "rb") as handle:
                self.assertEqual(handle.read(5), b"%PDF-")
            with open(eps, "rb") as handle:
                self.assertEqual(handle.read(2), b"%!")

    def test_svg_header(self):
        from views.canvas import export_scene_image
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.svg")
            export_scene_image(path, self._scene(), size=(80, 60))
            with open(path, "r", encoding="utf-8") as handle:
                self.assertIn("<svg", handle.read(500))


class TestShapePrimitives(unittest.TestCase):
    def test_polygon_segment_count(self):
        from models.geometry import _regular_polygon_beziers
        for n in (3, 5, 6, 12):
            self.assertEqual(len(_regular_polygon_beziers(0, 0, 50, 50, n)), n)

    def test_star_has_two_segments_per_point(self):
        from models.geometry import _star_beziers
        self.assertEqual(len(_star_beziers(0, 0, 50, 50, 5)), 10)
        self.assertEqual(len(_star_beziers(0, 0, 50, 50, 8)), 16)

    def test_shape_from_doodle_polygon_star(self):
        from models.geometry import shape_from_doodle
        pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
        poly, _ = shape_from_doodle(pts, "polygon", sides=6)
        star, _ = shape_from_doodle(pts, "star", star_points=5)
        self.assertEqual(len(poly), 6)
        self.assertEqual(len(star), 10)

    def test_shapes_registered_in_config(self):
        import config
        keys = [k for k, _ in config.DRAW_SHAPES]
        self.assertIn("polygon", keys)
        self.assertIn("star", keys)


class TestExpandStroke(unittest.TestCase):
    def test_open_line_expands_to_weighted_outline(self):
        from models.geometry import expand_stroke_outline
        st = {"segs": [((0, 0), (33, 0), (66, 0), (100, 0))],
              "stroke_width": 10.0, "fill_color": None,
              "stroke_color": (0.1, 0.2, 0.3, 1.0)}
        out = expand_stroke_outline(st)
        self.assertIsNotNone(out)
        self.assertEqual(out["stroke_width"], 0.0)
        self.assertGreater(len(out["segs"]), 2)
        ys = [s[0][1] for s in out["segs"]] + [s[3][1] for s in out["segs"]]
        self.assertAlmostEqual(min(ys), -5.0, places=1)
        self.assertAlmostEqual(max(ys), 5.0, places=1)
        # Stroke color carried over as fill.
        self.assertEqual(tuple(round(v, 2) for v in out["fill_color"][:3]),
                         (0.1, 0.2, 0.3))

    def test_zero_width_returns_none(self):
        from models.geometry import expand_stroke_outline
        st = {"segs": [((0, 0), (1, 0), (2, 0), (3, 0))], "stroke_width": 0.0}
        self.assertIsNone(expand_stroke_outline(st))

    def test_closed_path_makes_ring(self):
        from models.geometry import expand_stroke_outline
        segs = rect_stroke(0, 0, 40, 40)["segs"]
        st = {"segs": segs, "stroke_width": 8.0,
              "fill_color": None, "stroke_color": (0, 0, 0, 1)}
        out = expand_stroke_outline(st)
        self.assertIsNotNone(out)
        # Closed shape => outer + inner contours, so plenty of segments.
        self.assertGreater(len(out["segs"]), 16)


class TestSvgImport(unittest.TestCase):
    def test_parse_colors(self):
        from models.svg import parse_color
        self.assertEqual(parse_color("#ff0000"), (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(parse_color("#0f0"), (0.0, 1.0, 0.0, 1.0))
        self.assertEqual(parse_color("rgb(0,0,255)"), (0.0, 0.0, 1.0, 1.0))
        self.assertIsNone(parse_color("none"))
        self.assertEqual(parse_color("blue")[:3], (0.0, 0.0, 1.0))

    def test_parse_transforms(self):
        from models.svg import parse_transform
        self.assertEqual(parse_transform("translate(10,20)"), (1, 0, 0, 1, 10, 20))
        self.assertEqual(parse_transform("scale(2)"), (2, 0, 0, 2, 0, 0))
        self.assertEqual(parse_transform("matrix(1,0,0,1,5,6)"), (1, 0, 0, 1, 5, 6))

    def test_path_commands(self):
        from models.svg import parse_path_data
        subs = parse_path_data("M0,0 L10,0 L10,10 Z")
        self.assertEqual(len(subs), 1)
        self.assertTrue(subs[0]["closed"])
        self.assertEqual(len(subs[0]["segs"]), 2)

    def test_relative_commands(self):
        from models.svg import parse_path_data
        subs = parse_path_data("m10,10 l10,0 l0,10 z")
        segs = subs[0]["segs"]
        self.assertEqual(tuple(segs[0][0]), (10.0, 10.0))
        self.assertEqual(tuple(segs[-1][3]), (20.0, 20.0))

    def test_multiple_subpaths(self):
        from models.svg import parse_path_data
        self.assertEqual(len(parse_path_data("M0,0 L5,5 M10,10 L15,15")), 2)

    def test_cubic_and_arc(self):
        from models.svg import parse_path_data
        c = parse_path_data("M0,0 C1,1 2,2 3,3")[0]["segs"]
        self.assertEqual(len(c), 1)
        self.assertEqual(tuple(c[0][3]), (3.0, 3.0))
        self.assertGreater(len(parse_path_data("M0,0 A10,10 0 0 1 20,0")[0]["segs"]), 0)

    def test_basic_shapes(self):
        from models.svg import _shape_subpaths
        self.assertEqual(len(_shape_subpaths("rect", {"x": "0", "y": "0", "width": "10", "height": "20"})[0]["segs"]), 4)
        self.assertEqual(len(_shape_subpaths("circle", {"cx": "5", "cy": "5", "r": "5"})[0]["segs"]), 8)
        self.assertEqual(len(_shape_subpaths("polygon", {"points": "0,0 10,0 5,10"})[0]["segs"]), 3)
        self.assertEqual(len(_shape_subpaths("line", {"x1": "0", "y1": "0", "x2": "10", "y2": "10"})[0]["segs"]), 1)

    def test_import_svg_text(self):
        from models.svg import import_svg_text
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<rect x="10" y="10" width="30" height="20" fill="#ff0000"/>'
            '<circle cx="50" cy="50" r="10" fill="none" stroke="blue" stroke-width="2"/>'
            "</svg>"
        )
        strokes = import_svg_text(svg)
        self.assertEqual(len(strokes), 2)
        self.assertEqual(strokes[0]["fill_color"], (1.0, 0.0, 0.0, 1.0))
        self.assertIsNone(strokes[0]["stroke_color"])
        self.assertIsNone(strokes[1]["fill_color"])
        self.assertEqual(strokes[1]["stroke_color"], (0.0, 0.0, 1.0, 1.0))
        self.assertEqual(strokes[1]["stroke_width"], 2.0)

    def test_import_file(self):
        from models.svg import import_svg
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "art.svg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0,0 L10,0 L10,10 Z"/></svg>')
            strokes = import_svg(path)
            self.assertEqual(len(strokes), 1)
            self.assertEqual(len(strokes[0]["segs"]), 2)

    def test_viewbox_scaling(self):
        from models.svg import import_svg_text, _viewbox_transform
        m = _viewbox_transform(_ET_root('<svg width="200" height="200" viewBox="0 0 100 100"/>'))
        self.assertAlmostEqual(m[0], 2.0)
        strokes = import_svg_text(
            '<svg width="200" height="200" viewBox="0 0 100 100">'
            '<path d="M0,0 L10,0" stroke="black" fill="none"/></svg>')
        self.assertEqual(len(strokes), 1)
        self.assertAlmostEqual(strokes[0]["segs"][0][3][0], 20.0)


class TestAppearance(unittest.TestCase):
    def test_normalize_opacity(self):
        from models.appearance import normalize_opacity
        self.assertEqual(normalize_opacity(0.5), 0.5)
        self.assertEqual(normalize_opacity(-1), 0.0)
        self.assertEqual(normalize_opacity(5), 1.0)
        self.assertEqual(normalize_opacity("bad", 0.7), 0.7)
        self.assertEqual(normalize_opacity(float("nan"), 0.25), 0.25)

    def test_normalize_blend_mode(self):
        from models.appearance import normalize_blend_mode
        self.assertEqual(normalize_blend_mode("MULTIPLY"), "multiply")
        self.assertEqual(normalize_blend_mode("color_burn"), "color-burn")
        self.assertEqual(normalize_blend_mode("nonsense"), "normal")
        self.assertEqual(normalize_blend_mode(None), "normal")

    def test_normalize_shadow(self):
        from models.appearance import normalize_shadow
        self.assertIsNone(normalize_shadow(None))
        self.assertIsNone(normalize_shadow("yes"))
        s = normalize_shadow({"dx": 4, "dy": 8, "blur": 200, "opacity": 9})
        self.assertEqual(s["dx"], 4.0)
        self.assertEqual(s["dy"], 8.0)
        self.assertEqual(s["blur"], 64.0)
        self.assertEqual(s["opacity"], 1.0)
        self.assertEqual(len(s["color"]), 4)

    def test_get_appearance_defaults(self):
        from models.appearance import get_appearance, DEFAULT_APPEARANCE
        self.assertEqual(get_appearance({}), DEFAULT_APPEARANCE)
        self.assertEqual(get_appearance(None)["opacity"], 1.0)
        self.assertFalse(__import__("models").stroke_has_appearance({}))

    def test_stroke_has_appearance(self):
        from models import stroke_has_appearance
        self.assertFalse(stroke_has_appearance({"opacity": 1.0}))
        self.assertTrue(stroke_has_appearance({"opacity": 0.5}))
        self.assertTrue(stroke_has_appearance({"blend_mode": "multiply"}))
        self.assertTrue(stroke_has_appearance({"shadow": {"dx": 2, "dy": 2}}))

    def test_set_appearance_is_copy_and_normalizes(self):
        from models import set_appearance
        original = {"segs": [], "opacity": 1.0}
        out = set_appearance(original, opacity=2.0, blend_mode="SCREEN")
        self.assertIsNot(out, original)
        self.assertEqual(out["opacity"], 1.0)
        self.assertEqual(out["blend_mode"], "screen")
        self.assertEqual(original["opacity"], 1.0)  # unchanged

    def test_apply_opacity(self):
        from models.appearance import apply_opacity
        self.assertIsNone(apply_opacity(None, 0.5))
        self.assertEqual(apply_opacity((1.0, 0.0, 0.0, 1.0), 0.5),
                         (1.0, 0.0, 0.0, 0.5))
        self.assertEqual(apply_opacity((1.0, 0.0, 0.0, 0.8), 0.5)[3], 0.4)

    def test_document_roundtrip(self):
        from models import document, set_appearance
        st = rect_stroke(0, 0, 10, 10)
        st = set_appearance(st, opacity=0.4, blend_mode="multiply",
                            shadow={"dx": 3, "dy": 3, "blur": 5, "opacity": 0.3})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.json")
            document.save_document(path, [st], {})
            loaded = document.load_document(path)
        self.assertEqual(len(loaded), 1)
        from models import get_appearance
        app = get_appearance(loaded[0])
        self.assertAlmostEqual(app["opacity"], 0.4)
        self.assertEqual(app["blend_mode"], "multiply")
        self.assertIsNotNone(app["shadow"])

    def test_new_stroke_has_defaults(self):
        st = strokes_model.new_stroke([(0, 0, 0, 0, 1, 1, 2, 2)])
        self.assertEqual(st["opacity"], 1.0)
        self.assertEqual(st["blend_mode"], "normal")
        self.assertIsNone(st["shadow"])


class TestOrganization(unittest.TestCase):
    def test_hide_lock_defaults(self):
        st = strokes_model.new_stroke([(0, 0, 0, 0, 1, 1, 2, 2)])
        from models import is_hidden, is_locked, is_selectable
        self.assertFalse(is_hidden(st))
        self.assertFalse(is_locked(st))
        self.assertTrue(is_selectable(st))

    def test_toggle_helpers_are_copies(self):
        from models import toggle_hidden, toggle_locked, is_hidden, is_locked
        st = strokes_model.new_stroke([(0, 0, 0, 0, 1, 1, 2, 2)])
        hidden = toggle_hidden(st)
        self.assertIsNot(hidden, st)
        self.assertTrue(is_hidden(hidden))
        self.assertFalse(is_hidden(st))
        locked = toggle_locked(st)
        self.assertTrue(is_locked(locked))
        self.assertFalse(is_locked(st))

    def test_selectable_filter(self):
        from models import set_hidden, set_locked, filter_selectable, is_selectable
        strokes = [strokes_model.new_stroke([(0, 0, 0, 0, 1, 1, 2, 2)]) for _ in range(3)]
        strokes[1] = set_hidden(strokes[1], True)
        strokes[2] = set_locked(strokes[2], True)
        self.assertFalse(is_selectable(strokes[1]))
        self.assertFalse(is_selectable(strokes[2]))
        self.assertEqual(filter_selectable(strokes, [0, 1, 2]), [0])

    def test_hit_test_skips_hidden_locked(self):
        from models import set_hidden, set_locked
        from models.interaction import hit_test_stroke
        # Two overlapping rects; topmost is hidden, so lower one should be hit.
        bottom = rect_stroke(0, 0, 20, 20)
        top = set_hidden(rect_stroke(0, 0, 20, 20), True)
        self.assertEqual(hit_test_stroke((10, 10), [bottom, top]), 0)
        locked_top = set_locked(rect_stroke(0, 0, 20, 20), True)
        self.assertEqual(hit_test_stroke((10, 10), [bottom, locked_top]), 0)

    def test_document_roundtrip(self):
        from models import document, set_hidden, set_locked, is_hidden, is_locked
        st = rect_stroke(0, 0, 10, 10)
        st = set_hidden(set_locked(st, True), True)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "org.json")
            document.save_document(path, [st], {})
            loaded = document.load_document(path)
        self.assertEqual(len(loaded), 1)
        self.assertTrue(is_hidden(loaded[0]))
        self.assertTrue(is_locked(loaded[0]))


class TestGroups(unittest.TestCase):
    def test_group_helpers_roundtrip(self):
        from models import (new_group_id, assign_group, clear_group,
                            group_id_of, is_grouped, group_members)
        gid = new_group_id()
        a = assign_group(rect_stroke(0, 0, 10, 10), gid)
        b = assign_group(rect_stroke(20, 0, 30, 10), gid)
        self.assertTrue(is_grouped(a))
        self.assertEqual(group_id_of(a), gid)
        self.assertEqual(group_members([a, b], gid), [0, 1])
        c = clear_group(a)
        self.assertFalse(is_grouped(c))
        self.assertNotIn("group_id", c)

    def test_group_ids_are_unique(self):
        from models import new_group_id
        self.assertNotEqual(new_group_id(), new_group_id())

    def test_expand_group_selection(self):
        from models import assign_group, expand_group_selection
        a = assign_group(rect_stroke(0, 0, 10, 10), "g1")
        b = assign_group(rect_stroke(20, 0, 30, 10), "g1")
        c = rect_stroke(40, 0, 50, 10)
        self.assertEqual(expand_group_selection([a, b, c], {1}), {0, 1})
        self.assertEqual(expand_group_selection([a, b, c], {2}), {2})
        self.assertEqual(expand_group_selection([a, b, c], {0, 2}), {0, 1, 2})

    def test_group_selection_requires_two(self):
        from models import group_selection, is_grouped
        a = rect_stroke(0, 0, 10, 10)
        out, gid = group_selection([a], {0})
        self.assertIsNone(gid)
        self.assertFalse(is_grouped(out[0]))
        out, gid = group_selection([a, rect_stroke(20, 0, 30, 10)], {0, 1})
        self.assertIsNotNone(gid)
        self.assertTrue(all(is_grouped(s) for s in out))

    def test_ungroup_selection(self):
        from models import (assign_group, ungroup_selection, is_grouped)
        a = assign_group(rect_stroke(0, 0, 10, 10), "g1")
        b = assign_group(rect_stroke(20, 0, 30, 10), "g1")
        out = ungroup_selection([a, b], {0})
        self.assertFalse(is_grouped(out[0]))
        self.assertTrue(is_grouped(out[1]))

    def test_document_roundtrip_preserves_groups(self):
        from models import document, assign_group, group_id_of
        st = assign_group(rect_stroke(0, 0, 10, 10), "grp-99")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "grp.json")
            document.save_document(path, [st], {})
            loaded = document.load_document(path)
        self.assertEqual(group_id_of(loaded[0]), "grp-99")


class TestGuides(unittest.TestCase):
    def test_grid_positions(self):
        from models.guides import grid_positions
        self.assertEqual(grid_positions(0, 40, 20), [0, 20, 40])
        self.assertEqual(grid_positions(-25, 25, 20), [-20, 0, 20])
        self.assertEqual(grid_positions(0, 40, 0), [])
        self.assertEqual(grid_positions(10, 5, 20), [])

    def test_ruler_ticks_widen_on_zoom_out(self):
        from models.guides import ruler_ticks
        coarse = ruler_ticks(0, 1000, 10, min_pixels=64, zoom=0.25)
        fine = ruler_ticks(0, 1000, 10, min_pixels=64, zoom=4.0)
        self.assertGreater(coarse, fine)
        self.assertGreaterEqual(coarse * 0.25, 64)

    def test_snap_value_threshold(self):
        from models.guides import snap_value
        self.assertEqual(snap_value(13, 20), 20)
        self.assertEqual(snap_value(13, 20, threshold=3), 13)  # 7px away: too far
        self.assertEqual(snap_value(18, 20, threshold=3), 20)
        self.assertEqual(snap_value(13, 0), 13)

    def test_snap_point_to_grid(self):
        from models.guides import snap_point_to_grid
        self.assertEqual(snap_point_to_grid((13, 27), 20), (20.0, 20.0))

    def test_snap_to_guides_dominant_axis(self):
        from models.guides import snap_to_guides
        guides = [{"axis": "x", "pos": 100.0}, {"axis": "y", "pos": 50.0}]
        self.assertEqual(snap_to_guides((102, 80), guides, 10)[0], (100.0, 80))
        self.assertEqual(snap_to_guides((80, 47), guides, 10)[0], (80, 50.0))
        self.assertEqual(snap_to_guides((80, 80), guides, 10), ((80, 80), None))

    def test_snap_point_prefers_guides_over_grid(self):
        from models.guides import snap_point
        guides = [{"axis": "x", "pos": 103.0}]
        pt, kind = snap_point((104, 7), grid_size=20, guides=guides,
                              threshold=10, use_grid=True)
        self.assertEqual(kind, "guide_x")
        self.assertEqual(pt[0], 103.0)
        pt, kind = snap_point((7, 7), grid_size=20, use_grid=True)
        self.assertEqual(kind, "grid")
        self.assertEqual(pt, (0.0, 0.0))

    def test_guide_add_move_remove(self):
        from models.guides import add_guide, move_guide, remove_guide, hit_guide
        g = add_guide([], "x", 42)
        self.assertEqual(g, [{"axis": "x", "pos": 42.0}])
        g = add_guide(g, "y", 7.5)
        self.assertEqual(len(g), 2)
        g = move_guide(g, 0, 99)
        self.assertEqual(g[0]["pos"], 99.0)
        self.assertEqual(hit_guide((99.5, 0), g, 2), 0)
        self.assertIsNone(hit_guide((0, 0), g, 1))
        g = remove_guide(g, 0)
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["axis"], "y")

    def test_grid_does_not_change_default_render(self):
        import app as _app
        import config as cfg
        self.assertFalse(getattr(cfg, "SHOW_GRID", True))
        surf = _app.make_cairo_surface(120, 120)
        _app.draw_scene(surf, [])
        plain = bytes(_app.surface_to_pygame(surf).get_buffer())
        # Explicitly enable the grid: pixels must then differ.
        old = cfg.SHOW_GRID
        try:
            cfg.SHOW_GRID = True
            surf2 = _app.make_cairo_surface(120, 120)
            _app.draw_scene(surf2, [])
            gridded = bytes(_app.surface_to_pygame(surf2).get_buffer())
        finally:
            cfg.SHOW_GRID = old
        self.assertNotEqual(plain, gridded)


class TestPatternFills(unittest.TestCase):
    def test_new_pattern_normalizes(self):
        from models import new_pattern, is_fill_pattern
        p = new_pattern("dots", fg=(0.1, 0.2, 0.3), bg=None, size=8, angle=45)
        self.assertTrue(is_fill_pattern(p))
        self.assertEqual(p["type"], "dots")
        self.assertEqual(len(p["fg"]), 4)
        self.assertIsNone(p["bg"])
        self.assertEqual(p["size"], 8.0)
        self.assertEqual(p["angle"], 45.0)

    def test_bad_type_falls_back(self):
        from models import new_pattern
        self.assertEqual(new_pattern("nope")["type"], "stripes")

    def test_cycle_pattern_type(self):
        from models import new_pattern, cycle_pattern_type, PATTERN_TYPES
        p = cycle_pattern_type(new_pattern("stripes"))
        self.assertEqual(p["type"], PATTERN_TYPES[1])
        p2 = cycle_pattern_type(new_pattern(PATTERN_TYPES[-1]))
        self.assertEqual(p2["type"], PATTERN_TYPES[0])

    def test_set_pattern_fill_clears_solid_and_gradient(self):
        from models import new_pattern, set_pattern_fill, get_fill_pattern
        st = {"fill_color": (1, 0, 0, 1), "fill_gradient": {"type": "linear", "stops": []}}
        st = set_pattern_fill(st, new_pattern("checks"))
        self.assertIsNone(st["fill_color"])
        self.assertIsNone(st["fill_gradient"])
        self.assertEqual(get_fill_pattern(st)["type"], "checks")

    def test_clear_pattern_fill(self):
        from models import new_pattern, set_pattern_fill, clear_pattern_fill, pattern_has_fill
        st = set_pattern_fill({}, new_pattern("grid"))
        self.assertTrue(pattern_has_fill(st))
        clear_pattern_fill(st)
        self.assertFalse(pattern_has_fill(st))

    def test_pattern_render_changes_pixels(self):
        from models import new_pattern, set_pattern_fill
        import app as _app
        st = {"segs": [[(10, 10), (60, 10), (60, 60), (10, 60)]],
              "stroke_width": 0.0, "fill_color": (0.9, 0.2, 0.2, 1.0)}
        surf1 = _app.make_cairo_surface(80, 80)
        _app.draw_scene(surf1, [st])
        plain = bytes(_app.surface_to_pygame(surf1).get_buffer())
        pat_st = set_pattern_fill(dict(st, fill_color=None), new_pattern("stripes"))
        surf2 = _app.make_cairo_surface(80, 80)
        _app.draw_scene(surf2, [pat_st])
        patterned = bytes(_app.surface_to_pygame(surf2).get_buffer())
        self.assertNotEqual(plain, patterned)

    def test_pattern_document_roundtrip(self):
        from models import document, new_pattern, set_pattern_fill, get_fill_pattern
        st = set_pattern_fill({"segs": [[(0, 0), (10, 0), (10, 10), (0, 10)]],
                               "stroke_width": 0.0}, new_pattern("zigzag", size=9))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pat.json")
            document.save_document(path, [st], {})
            loaded = document.load_document(path)
        p = get_fill_pattern(loaded[0])
        self.assertIsNotNone(p)
        self.assertEqual(p["type"], "zigzag")
        self.assertEqual(p["size"], 9.0)


class TestMarkers(unittest.TestCase):
    def test_default_markers_none(self):
        from models import get_markers
        self.assertEqual(get_markers({}), {"start": "none", "end": "none"})

    def test_legacy_arrow_end_maps_to_arrow(self):
        from models import get_markers
        self.assertEqual(get_markers({"arrow_end": True})["end"], "arrow")

    def test_set_and_clear_marker(self):
        from models import set_marker, get_markers
        st = {}
        set_marker(st, "end", "triangle")
        self.assertEqual(get_markers(st)["end"], "triangle")
        self.assertTrue(st["arrow_end"])
        set_marker(st, "end", "none")
        self.assertEqual(get_markers(st)["end"], "none")
        self.assertFalse(st["arrow_end"])

    def test_cycle_marker_wraps(self):
        from models import cycle_marker, get_markers, MARKER_TYPES
        st = {}
        cycle_marker(st, "start")
        self.assertEqual(get_markers(st)["start"], MARKER_TYPES[1])
        for _ in range(len(MARKER_TYPES)):
            cycle_marker(st, "start")
        self.assertEqual(get_markers(st)["start"], MARKER_TYPES[1])

    def test_closed_path_has_no_anchors(self):
        from models import marker_anchors
        closed = {"segs": [[(0, 0), (5, 0), (5, 5), (0, 5)], [(0, 5), (0, 5), (0, 0), (0, 0)]]}
        self.assertEqual(marker_anchors(closed), [])

    def test_open_path_anchors_point_outward(self):
        from models import marker_anchors
        st = {"segs": [[(0, 0), (10, 0), (20, 0), (30, 0)]]}
        anchors = dict((a[0], a) for a in marker_anchors(st))
        self.assertIn("start", anchors)
        self.assertIn("end", anchors)
        _e, end_pt, ex, ey = anchors["end"]
        self.assertEqual(end_pt, (30.0, 0.0))
        self.assertAlmostEqual(ex, 1.0)
        self.assertAlmostEqual(ey, 0.0)
        _e, start_pt, sx, sy = anchors["start"]
        self.assertEqual(start_pt, (0.0, 0.0))
        self.assertAlmostEqual(sx, -1.0)  # points away from the path

    def test_marker_render_changes_pixels(self):
        from models import set_marker
        import app as _app
        st = {"segs": [[(10, 40), (40, 40), (70, 40), (110, 40)]],
              "stroke_color": (0.1, 0.1, 0.2, 1.0), "stroke_width": 4.0,
              "line_cap": "round", "line_join": "round"}
        surf1 = _app.make_cairo_surface(130, 80)
        _app.draw_scene(surf1, [st])
        plain = bytes(_app.surface_to_pygame(surf1).get_buffer())
        marked = set_marker(dict(st), "end", "triangle")
        surf2 = _app.make_cairo_surface(130, 80)
        _app.draw_scene(surf2, [marked])
        with_marker = bytes(_app.surface_to_pygame(surf2).get_buffer())
        self.assertNotEqual(plain, with_marker)

    def test_marker_document_roundtrip(self):
        from models import document, set_marker, get_markers
        st = set_marker({"segs": [[(0, 0), (10, 0), (20, 0), (30, 0)]],
                         "stroke_width": 3.0}, "start", "circle")
        st = set_marker(st, "end", "diamond")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mk.json")
            document.save_document(path, [st], {})
            loaded = document.load_document(path)
        m = get_markers(loaded[0])
        self.assertEqual(m["start"], "circle")
        self.assertEqual(m["end"], "diamond")


class TestTextOutlines(unittest.TestCase):
    def test_font_families_and_metrics(self):
        from models.text import FONT_FAMILIES, text_metrics, font_path
        self.assertIn("Sans", FONT_FAMILIES)
        w, h = text_metrics("Hello", "Sans", 36)
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)
        # On this machine a real TTF is found; the path must exist when present.
        p = font_path("Sans")
        if p is not None:
            self.assertTrue(os.path.isfile(p))

    def test_text_to_segs_is_cubic_and_positioned(self):
        from models.text import text_to_segs
        segs = text_to_segs("Hi", 10, 50, "Sans", 36)
        self.assertGreater(len(segs), 0)
        for seg in segs:
            self.assertEqual(len(seg), 4)
            for p in seg:
                self.assertEqual(len(p), 2)
        xs = [p[0] for s in segs for p in (s[0], s[3])]
        ys = [p[1] for s in segs for p in (s[0], s[3])]
        self.assertGreater(max(xs), min(xs))
        self.assertGreater(max(ys), min(ys))

    def test_fallback_font_produces_outlines(self):
        from models.text import text_to_segs
        segs = text_to_segs("A", 0, 0, "__no_such_font__", 20)
        self.assertGreater(len(segs), 0)

    def test_multiline_text(self):
        from models.text import text_to_segs
        one = text_to_segs("A", 0, 0, "Sans", 20)
        two = text_to_segs("A\nB", 0, 0, "Sans", 20)
        self.assertGreater(len(two), len(one))

    def test_new_text_stroke_metadata(self):
        from models import new_text_stroke, is_text_stroke
        st = new_text_stroke("Hello", 20, 80, "Sans", 36)
        self.assertTrue(is_text_stroke(st))
        self.assertEqual(st["text_content"], "Hello")
        self.assertEqual(st["font_family"], "Sans")
        self.assertEqual(st["font_size"], 36.0)
        self.assertEqual(st["text_x"], 20.0)
        self.assertEqual(st["text_y"], 80.0)
        self.assertEqual(st["stroke_width"], 0.0)
        self.assertGreater(len(st["segs"]), 0)

    def test_update_text_stroke_is_copy(self):
        from models import new_text_stroke, update_text_stroke
        st = new_text_stroke("Hello", 0, 0, "Sans", 36)
        out = update_text_stroke(st, text_content="World", font_size=48)
        self.assertIsNot(out, st)
        self.assertEqual(out["text_content"], "World")
        self.assertEqual(out["font_size"], 48.0)
        self.assertEqual(st["text_content"], "Hello")  # unchanged
        self.assertNotEqual(len(out["segs"]), 0)

    def test_update_bad_font_falls_back(self):
        from models import new_text_stroke, update_text_stroke
        st = new_text_stroke("Hi", 0, 0, "Sans", 36)
        out = update_text_stroke(st, font_family="Nope")
        self.assertEqual(out["font_family"], "Sans")

    def test_document_roundtrip(self):
        from models import document, new_text_stroke
        st = new_text_stroke("Roundtrip", 5, 6, "Sans", 24)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "text.json")
            document.save_document(path, [st], {})
            loaded = document.load_document(path)
        self.assertEqual(len(loaded), 1)
        self.assertTrue(loaded[0].get("is_text"))
        self.assertEqual(loaded[0].get("text_content"), "Roundtrip")
        self.assertEqual(loaded[0].get("font_size"), 24.0)

    def test_hit_test_text_outlines(self):
        from models import new_text_stroke
        from models.interaction import hit_test_stroke
        # Click inside a thick glyph region of a large letter.
        st = new_text_stroke("H", 0, 100, "Sans", 120)
        hit = None
        for xx in range(0, 120, 4):
            for yy in range(0, 100, 4):
                r = hit_test_stroke((xx, yy), [st], threshold=2.0)
                if r is not None:
                    hit = r
                    break
            if hit is not None:
                break
        self.assertEqual(hit, 0)

    def test_render_changes_pixels(self):
        from models import new_text_stroke
        import app as _app
        surf1 = _app.make_cairo_surface(200, 200)
        surf2 = _app.make_cairo_surface(200, 200)
        _app.draw_scene(surf1, [])
        st = new_text_stroke("A", 20, 160, "Sans", 100)
        _app.draw_scene(surf2, [st])
        img1 = bytes(_app.surface_to_pygame(surf1).get_buffer())
        img2 = bytes(_app.surface_to_pygame(surf2).get_buffer())
        self.assertNotEqual(img1, img2)


def _ET_root(text):
    import xml.etree.ElementTree as ET
    return ET.fromstring(text)


if __name__ == "__main__":
    unittest.main()
