"""Regression coverage for collapsible right-panel sections."""

import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.font.init()

import config as cfg  # noqa: E402
import models as m  # noqa: E402
import views.panel as panel_view  # noqa: E402
from controllers.panel.dispatch import handle_panel_click  # noqa: E402
from controllers.panel.sections import handle_section_click  # noqa: E402
from models.appearance import set_appearance  # noqa: E402
from panel_rects import panel_spacing_violations  # noqa: E402
from views.panel_sections import (  # noqa: E402
    DEFAULT_OPEN,
    clear_rects,
    is_open,
    set_open,
    toggle,
)
from views.widgets import Button, Slider, make_fonts  # noqa: E402


def _stroke():
    return m.new_stroke([((10, 10), (30, 10), (50, 40), (70, 40))])


def _base_state(obj=None, submode="transform", bbox=None):
    """Build a fresh render-ready state (mirrors tests/test_ui_spacing.py)."""
    boost = Button((0, 0, cfg.PANEL_W - 40, 34), "Boost limit")
    slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 2, 5, 4)
    width_slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 1, 20, 3)
    cut_slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 0, 20, 0)
    cut_slider.track.width = 0
    state = {
        "tool_mode": "selection",
        "max_points": 4,
        "boost_points": False,
        "NORMAL_MAX_POINTS": 5,
        "BOOST_MAX_POINTS": 100,
        "slider": slider,
        "width_slider": width_slider,
        "cut_gap_slider": cut_slider,
        "buttons": {"boost": boost, "actions": []},
        "stroke_count": 1 if obj is not None else 0,
        "selected_strokes": {0} if obj is not None else set(),
        "selected_obj": obj,
        "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in panel_view.STROKE_SWATCHES],
        "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in panel_view.FILL_SWATCHES],
        "color_target": "stroke",
        "picker_h": 10.0, "picker_s": 0.5, "picker_v": 0.8,
        "picker_drag_sv": False, "picker_drag_hue": False,
        "sv_rect": pygame.Rect(0, 0, 0, 0),
        "hue_rect": pygame.Rect(0, 0, 0, 0),
        "tab_stroke_rect": pygame.Rect(0, 0, 0, 0),
        "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
        "nofill_rect": pygame.Rect(0, 0, 0, 0),
        "selection_submode": submode,
        "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
        "draw_tool": "pen", "draw_shape": "freehand",
        "trace_algorithm": "fit", "snap_enabled": True,
        "reference_image": None, "cut_gap": 0,
        "panel_scroll": 0, "selection_bbox": bbox,
    }
    return state


class _RenderMixin:
    @classmethod
    def setUpClass(cls):
        cls.screen = pygame.Surface((cfg.WIDTH, cfg.HEIGHT))
        pygame.font.init()
        cls.fonts = make_fonts()

    def render(self, state):
        panel_view.draw_panel(self.screen, self.fonts, (0, 0), state)
        return state


class TestSectionState(unittest.TestCase):
    def test_defaults_match_the_panel_contract(self):
        # Priority states stay immediately usable.
        self.assertTrue(DEFAULT_OPEN["selection_transform"])
        self.assertTrue(DEFAULT_OPEN["curve_styles"])
        self.assertTrue(DEFAULT_OPEN["selection_color"])
        # Secondary groups start folded.
        self.assertFalse(DEFAULT_OPEN["selection_arrange"])
        self.assertFalse(DEFAULT_OPEN["selection_appearance"])
        self.assertFalse(DEFAULT_OPEN["curve_color"])
        self.assertFalse(DEFAULT_OPEN["draw_reference"])
        self.assertFalse(DEFAULT_OPEN["help"])

    def test_missing_key_uses_default_and_initialises_maps(self):
        state = {}
        self.assertEqual(is_open(state, "selection_transform"),
                         DEFAULT_OPEN["selection_transform"])
        self.assertEqual(state["panel_sections"], {})
        self.assertEqual(state["panel_section_rects"], {})

    def test_toggle_and_set_open_persist(self):
        state = {}
        self.assertTrue(is_open(state, "selection_transform"))
        self.assertFalse(toggle(state, "selection_transform"))
        self.assertFalse(is_open(state, "selection_transform"))
        self.assertTrue(toggle(state, "selection_transform"))
        self.assertTrue(is_open(state, "selection_transform"))
        self.assertFalse(set_open(state, "selection_transform", False))
        self.assertEqual(state["panel_sections"]["selection_transform"], False)

    def test_clear_rects_zeroes_rects_collections(self):
        state = {
            "one_rect": pygame.Rect(1, 2, 3, 4),
            "many_rects": {"a": pygame.Rect(5, 6, 7, 8),
                           "b": pygame.Rect(9, 10, 11, 12)},
            "list_rects": [pygame.Rect(13, 14, 15, 16)],
            "keep_rect": pygame.Rect(17, 18, 19, 20),
        }
        clear_rects(state, ("one_rect", "many_rects", "list_rects"))
        self.assertEqual(state["one_rect"], pygame.Rect(0, 0, 0, 0))
        self.assertEqual(state["many_rects"]["a"], pygame.Rect(0, 0, 0, 0))
        self.assertEqual(state["many_rects"]["b"], pygame.Rect(0, 0, 0, 0))
        self.assertEqual(state["list_rects"][0], pygame.Rect(0, 0, 0, 0))
        self.assertEqual(state["keep_rect"], pygame.Rect(17, 18, 19, 20))


class TestHeaderClicks(_RenderMixin, unittest.TestCase):
    def _transform_state(self, sections=None):
        state = _base_state(obj=_stroke(), bbox=(10, 10, 70, 40))
        if sections is not None:
            state["panel_sections"] = dict(sections)
        return self.render(state)

    def test_clicking_a_header_toggles_only_that_section(self):
        state = self._transform_state({"selection_transform": True,
                                       "selection_arrange": False})
        rect = state["panel_section_rects"]["selection_transform"]
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": rect.center, "button": 1})
        ctx = types.SimpleNamespace(state=state)

        self.assertEqual(handle_panel_click(ctx, event), "continue")
        self.assertFalse(is_open(state, "selection_transform"))
        self.assertFalse(is_open(state, "selection_arrange"))

        # The other headers are untouched.
        event2 = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"pos": state["panel_section_rects"]["selection_arrange"].center,
             "button": 1})
        handle_panel_click(ctx, event2)
        self.assertTrue(is_open(state, "selection_arrange"))

    def test_click_outside_all_headers_is_not_consumed(self):
        state = self._transform_state()
        ctx = types.SimpleNamespace(state=state)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 1})
        self.assertIsNone(handle_section_click(ctx, event))

    def test_non_left_click_does_not_toggle(self):
        state = self._transform_state({"selection_transform": True})
        rect = state["panel_section_rects"]["selection_transform"]
        ctx = types.SimpleNamespace(state=state)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": rect.center, "button": 3})
        self.assertIsNone(handle_section_click(ctx, event))
        self.assertTrue(is_open(state, "selection_transform"))


class TestCollapsedRendering(_RenderMixin, unittest.TestCase):
    def test_collapsed_body_hit_rects_are_cleared(self):
        state = _base_state(obj=set_appearance(_stroke(), shadow={"blur": 8}),
                            bbox=(10, 10, 70, 40))
        state["panel_sections"] = {"selection_appearance": False,
                                   "selection_transform": False,
                                   "selection_color": False}
        self.render(state)
        for key in ("shadow_blur_minus_rect", "shadow_blur_plus_rect",
                    "obj_opacity_rect", "xform_x_rect", "xform_xp_rect",
                    "tab_stroke_rect", "sv_rect"):
            self.assertEqual(state.get(key), pygame.Rect(0, 0, 0, 0), key)

    def test_expanding_body_restores_hit_rects(self):
        state = _base_state(obj=set_appearance(_stroke(), shadow={"blur": 8}),
                            bbox=(10, 10, 70, 40))
        state["panel_sections"] = {"selection_appearance": True,
                                   "selection_transform": True,
                                   "selection_color": True}
        self.render(state)
        for key in ("shadow_blur_minus_rect", "shadow_blur_plus_rect",
                    "xform_x_rect", "tab_stroke_rect", "sv_rect"):
            self.assertGreater(state[key].w, 0, key)

    def test_collapsing_sections_reduces_content_height(self):
        def content_bottom(sections):
            state = _base_state(obj=_stroke(), bbox=(10, 10, 70, 40))
            state["panel_sections"] = dict(sections)
            self.render(state)
            return state["panel_content_bottom"]

        all_open = {key: True for key in DEFAULT_OPEN}
        all_closed = {key: False for key in DEFAULT_OPEN}
        self.assertGreater(content_bottom(all_open), content_bottom(all_closed))

    def test_focused_transform_field_renders_without_error(self):
        # Double-click entry sets xform_field_focus; the highlighted branch must
        # use a real config colour (BUTTON_ACTIVE_BG was never defined).
        state = _base_state(obj=_stroke(), bbox=(10, 10, 70, 40))
        state["xform_field_focus"] = "x"
        state["xform_field_buffer"] = "12.5"
        self.render(state)
        self.assertGreater(state["xform_x_rect"].w, 0)

    def test_stale_header_rects_are_dropped_between_renders(self):
        state = _base_state(obj=_stroke(), bbox=(10, 10, 70, 40))
        self.render(state)
        self.assertIn("selection_transform", state["panel_section_rects"])

        # Switch submode in the same persistent state: the transform header is
        # no longer drawn, so its hit rect must not survive the next frame.
        state["selection_submode"] = "curve"
        state["selection_bbox"] = None
        self.render(state)
        self.assertNotIn("selection_transform", state["panel_section_rects"])

    def test_spacing_holds_in_collapsed_and_expanded_states(self):
        # Exercise both extreme configurations for the two priority sections
        # and a representative secondary section.
        for key in ("selection_transform", "curve_styles", "selection_appearance"):
            for value in (True, False):
                with self.subTest(section=key, expanded=value):
                    obj = _stroke()
                    state = _base_state(obj=obj, bbox=(10, 10, 70, 40))
                    state["panel_sections"] = {key: value}
                    self.render(state)
                    violations = panel_spacing_violations(state)
                    self.assertEqual(
                        violations, [],
                        "; ".join(
                            f"{v.gap}px {v.key_a} <-> {v.key_b} ({v.axis})"
                            for v in violations
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
