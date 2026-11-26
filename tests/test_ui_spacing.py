"""Regression coverage for the 8px UI spacing contract in docs/STYLE_GUIDE.md."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.init()
pygame.font.init()

import config as cfg  # noqa: E402
import models as m  # noqa: E402
import views.menu as menu_view  # noqa: E402
import views.panel as panel_view  # noqa: E402
import views.toolbar as toolbar_view  # noqa: E402
from models.appearance import set_appearance  # noqa: E402
from models.waves import (  # noqa: E402
    default_displacement_params,
    default_repeat_params,
    default_thickness_params,
    default_wave_params,
)
from panel_rects import (  # noqa: E402
    panel_spacing_violations,
    spacing_violations,
    visible_rects_from_state,
)
from views.widgets import Button, Slider, make_fonts  # noqa: E402


def _stroke(fill=None, text=False):
    stroke = m.new_stroke([((10, 10), (30, 10), (50, 40), (70, 40))], fill_color=fill)
    if text:
        if hasattr(m, "new_text_stroke"):
            stroke = m.new_text_stroke("Hello", 10, 10, size=24)
        stroke["is_text"] = True
        stroke["text_content"] = "Hello"
        stroke["font_size"] = 24
    return stroke


def _base_state(tool_mode="draw", selected=None, obj=None, color_target="stroke",
                submode="transform", draw_tool="pen", draw_shape="freehand"):
    boost = Button((0, 0, cfg.PANEL_W - 40, 34), "Boost limit")
    slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 2, 5, 4)
    width_slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 1, 20, 3)
    cut_slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 0, 20, 0)
    cut_slider.track.width = 0
    return {
        "tool_mode": tool_mode, "max_points": 4, "boost_points": False,
        "NORMAL_MAX_POINTS": 5, "BOOST_MAX_POINTS": 100,
        "slider": slider, "width_slider": width_slider, "cut_gap_slider": cut_slider,
        "buttons": {"boost": boost, "actions": []},
        "stroke_count": 1 if obj else 0,
        "selected_strokes": ({selected} if selected is not None else set()),
        "selected_obj": obj,
        "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in panel_view.STROKE_SWATCHES],
        "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in panel_view.FILL_SWATCHES],
        "color_target": color_target, "picker_h": 10.0, "picker_s": 0.5, "picker_v": 0.8,
        "picker_drag_sv": False, "picker_drag_hue": False,
        "sv_rect": pygame.Rect(0, 0, 0, 0), "hue_rect": pygame.Rect(0, 0, 0, 0),
        "tab_stroke_rect": pygame.Rect(0, 0, 0, 0), "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
        "nofill_rect": pygame.Rect(0, 0, 0, 0),
        "selection_submode": submode, "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
        "draw_tool": draw_tool, "draw_shape": draw_shape,
        "trace_algorithm": "fit", "snap_enabled": True,
        "reference_image": None, "cut_gap": 0,
        "panel_scroll": 0, "selection_bbox": None,
    }


def _styled_stroke(style_type):
    factories = {
        "repeat": default_repeat_params,
        "thickness": default_thickness_params,
        "displacement": default_displacement_params,
        "wave": default_wave_params,
    }
    stroke = _stroke()
    components = m.strokes._stroke_components(stroke)
    components[0]["styles"] = [factories[style_type]()]
    stroke["components"] = components
    return stroke


def _gradient_stroke(nstops=12):
    stroke = _stroke(fill=(0.2, 0.3, 0.4, 1.0))
    stroke["fill_gradient"] = {
        "type": "linear",
        "angle": 0.0,
        "stops": [
            {"pos": i / (nstops - 1), "color": [i / nstops, 0.2, 0.8, 1.0]}
            for i in range(nstops)
        ],
    }
    return stroke


class TestSpacingValidator(unittest.TestCase):
    def test_minimum_gap_is_the_shared_config_token(self):
        self.assertEqual(cfg.MIN_ELEMENT_SPACING, 8)

    def test_validator_accepts_eight_pixels_and_flags_closer_gaps(self):
        spaced = {
            "a": pygame.Rect(0, 0, 20, 20),
            "b": pygame.Rect(28, 0, 20, 20),
        }
        self.assertEqual(spacing_violations(spaced), [])

        close = dict(spaced, b=pygame.Rect(27, 0, 20, 20))
        violations = spacing_violations(close)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].gap, 7)
        self.assertEqual(violations[0].axis, "horizontal")
        self.assertEqual(violations[0].key_a, "a")
        self.assertEqual(violations[0].key_b, "b")

    def test_validator_flags_touching_and_overlapping_rects(self):
        rects = {
            "a": pygame.Rect(0, 0, 20, 20),
            "touch": pygame.Rect(20, 0, 20, 20),
            "overlap": pygame.Rect(10, 10, 20, 20),
        }
        violations = {item.key_b: item for item in spacing_violations(rects)}
        self.assertEqual(violations["touch"].gap, 0)
        self.assertEqual(violations["touch"].axis, "touching")
        self.assertEqual(violations["overlap"].gap, 0)
        self.assertEqual(violations["overlap"].axis, "overlap")

    def test_contained_children_are_not_separate_elements(self):
        rects = {
            "row": pygame.Rect(0, 0, 100, 30),
            "toggle": pygame.Rect(60, 4, 20, 20),
            "other": pygame.Rect(104, 0, 20, 20),
        }
        violations = spacing_violations(rects)
        self.assertEqual([item.key_a for item in violations], ["row"])
        self.assertEqual([item.key_b for item in violations], ["other"])

    def test_visible_rects_flattens_collections_and_nested_hit_boxes(self):
        state = {
            "shown_rect": pygame.Rect(0, 0, 10, 10),
            "hidden_rect": pygame.Rect(0, 0, 0, 0),
            "swatches_rects": {"first": pygame.Rect(20, 0, 10, 10)},
            "sliders_rects": {"amplitude": (pygame.Rect(40, 0, 10, 10), 0.0, 1.0)},
            "rows_rects": [(0, pygame.Rect(60, 0, 10, 10))],
            "unrelated": pygame.Rect(80, 0, 10, 10),
        }
        rects = visible_rects_from_state(state)
        self.assertIn("shown_rect", rects)
        self.assertNotIn("hidden_rect", rects)
        self.assertIn("swatches_rects[first]", rects)
        self.assertIn("sliders_rects[amplitude][0]", rects)
        self.assertIn("rows_rects[0][1]", rects)
        self.assertNotIn("unrelated", rects)


class TestRenderedSpacing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.screen = pygame.Surface((cfg.WIDTH, cfg.HEIGHT))
        # Other suites call pygame.quit(), which also shuts down the font
        # module. Re-initialise here so make_fonts() works in a full run.
        pygame.font.init()
        cls.fonts = make_fonts()

    def _scenarios(self):
        scenarios = {
            "draw/pen/freehand": lambda: _base_state(),
            "draw/pen/bezier": lambda: _base_state(draw_shape="pen"),
            "draw/bucket": lambda: _base_state(draw_tool="bucket"),
            "draw/eraser": lambda: _base_state(draw_tool="eraser"),
            "draw/cutter": lambda: _base_state(draw_tool="cutter"),
            "selection/none": lambda: _base_state("selection"),
            "selection/transform": lambda: _base_state("selection", 0, _stroke()),
            "selection/transform/bbox": lambda: dict(
                _base_state("selection", 0, _stroke()), selection_bbox=(10, 10, 70, 40)),
            "selection/transform/fill": lambda: _base_state(
                "selection", 0, _stroke(fill=(0.2, 0.3, 0.4)), color_target="fill"),
            "selection/transform/pattern": lambda: dict(
                _base_state("selection", 0, _stroke(fill=(0.2, 0.3, 0.4)), color_target="fill"),
                stroke=_stroke(fill=(0.2, 0.3, 0.4))),
            "selection/transform/two": lambda: dict(
                _base_state("selection", 0, _stroke()), selected_strokes={0, 1}, stroke_count=2),
            "selection/transform/three": lambda: dict(
                _base_state("selection", 0, _stroke()), selected_strokes={0, 1, 2}, stroke_count=3),
            "selection/transform/text": lambda: _base_state("selection", 0, _stroke(text=True)),
            "selection/nodes": lambda: _base_state("selection", 0, _stroke(), submode="nodes"),
            "selection/curve": lambda: _base_state("selection", 0, _stroke(), submode="curve"),
            "selection/shadow": lambda: dict(
                _base_state("selection", 0, set_appearance(_stroke(), shadow={"blur": 8})),
                selection_bbox=(10, 10, 70, 40)),
        }
        for style_type in ("repeat", "thickness", "displacement", "wave"):
            scenarios[f"selection/curve/{style_type}"] = lambda st=style_type: dict(
                _base_state("selection", 0, _styled_stroke(st), submode="curve"),
                selected_curve=(0, 0))
        return scenarios

    def assert_no_spacing_violations(self, state, label):
        violations = panel_spacing_violations(state)
        details = "; ".join(
            f"{item.gap}px {item.key_a} <-> {item.key_b} ({item.axis})"
            for item in violations
        )
        self.assertEqual(violations, [], f"{label}: {details}")

    def test_rendered_panel_states_keep_eight_pixel_spacing(self):
        for name, factory in self._scenarios().items():
            with self.subTest(state=name):
                state = factory()
                panel_view.draw_panel(self.screen, self.fonts, (0, 0), state)
                self.assert_no_spacing_violations(state, name)

    def test_gradient_stop_swatches_wrap_instead_of_shrinking_gaps(self):
        stroke = _gradient_stroke(nstops=12)
        state = _base_state("selection", 0, stroke, color_target="fill")
        panel_view.draw_panel(self.screen, self.fonts, (0, 0), state)

        stop_rects = state["fill_stop_rects"]
        self.assertEqual(len(stop_rects), 12)
        self.assertGreater(len({rect.y for rect in stop_rects.values()}), 1)
        self.assertEqual(spacing_violations(stop_rects), [])
        self.assert_no_spacing_violations(state, "gradient-stop wrap")

    def test_pattern_controls_keep_eight_pixel_spacing(self):
        stroke = _stroke(fill=(0.2, 0.3, 0.4, 1.0))
        stroke["fill_pattern"] = {"type": "stripes", "size": 14}
        state = _base_state("selection", 0, stroke, color_target="fill")
        panel_view.draw_panel(self.screen, self.fonts, (0, 0), state)

        controls = {
            "type": state["pattern_type_rect"],
            "minus": state["pattern_size_minus_rect"],
            "plus": state["pattern_size_plus_rect"],
        }
        self.assertEqual(spacing_violations(controls), [])
        self.assert_no_spacing_violations(state, "pattern controls")

    def test_marker_dropdown_keeps_gap_from_its_anchor(self):
        state = _base_state("selection", 0, _stroke())
        panel_view.draw_panel(self.screen, self.fonts, (0, 0), state)
        state["marker_dropdown"] = "start"
        panel_view.draw_marker_dropdown(self.screen, self.fonts, (0, 0), state)
        self.assert_no_spacing_violations(state, "marker dropdown")

    def test_toolbar_menu_and_export_dialog_keep_eight_pixel_spacing(self):
        toolbar_state = {"tool_mode": "draw", "draw_tool": "pen", "draw_shape": "freehand"}
        toolbar_view.draw_bottom_shape_toolbar(self.screen, self.fonts, (0, 0), toolbar_state)
        self.assertEqual(spacing_violations(toolbar_state["draw_shape_rects"]), [])

        menu_state = {
            "shape_menu_key": "freehand",
            "shape_menu_anchor": pygame.Rect(100, 300, 60, 40),
            "snap_enabled": True,
        }
        toolbar_view.draw_shape_context_menu(self.screen, self.fonts, (0, 0), menu_state)
        self.assertEqual(spacing_violations(menu_state["shape_menu_item_rects"]), [])

        menu_bar_state = {}
        label_rects, _ = menu_view.draw_menu_bar(
            self.screen, self.fonts[0], (0, 0), None, menu_bar_state)
        labels = dict(label_rects)
        labels["workspace_rect"] = menu_bar_state["workspace_rect"]
        self.assertEqual(spacing_violations(labels), [])

        dialog_state = {}
        menu_view.draw_export_dialog(self.screen, self.fonts[0], self.fonts[1], (0, 0), dialog_state)
        self.assertEqual(spacing_violations(dialog_state["export_dialog_rects"]), [])


if __name__ == "__main__":
    unittest.main()
