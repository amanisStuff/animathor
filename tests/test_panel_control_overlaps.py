import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.font.init()

import config as cfg  # noqa: E402
import models as m  # noqa: E402
import views.panel as panel_view  # noqa: E402
from models.appearance import set_appearance  # noqa: E402
from models.waves import (  # noqa: E402
    default_displacement_params,
    default_repeat_params,
    default_thickness_params,
    default_wave_params,
)
from views.widgets import Button, Slider, make_fonts  # noqa: E402


def _stroke():
    return m.new_stroke([((10, 10), (30, 10), (50, 40), (70, 40))])


def _base_state(obj=None, submode="transform", curve=None):
    boost = Button((0, 0, cfg.PANEL_W - 40, 34), "Boost limit")
    slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 2, 5, 4)
    width_slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 1, 20, 3)
    cut_slider = Slider(cfg.PANEL_X + 20, 0, cfg.PANEL_W - 40, 0, 20, 0)
    cut_slider.track.width = 0
    return {
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
        "picker_h": 10.0,
        "picker_s": 0.5,
        "picker_v": 0.8,
        "picker_drag_sv": False,
        "picker_drag_hue": False,
        "sv_rect": pygame.Rect(0, 0, 0, 0),
        "hue_rect": pygame.Rect(0, 0, 0, 0),
        "tab_stroke_rect": pygame.Rect(0, 0, 0, 0),
        "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
        "nofill_rect": pygame.Rect(0, 0, 0, 0),
        "selection_submode": submode,
        "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
        "draw_tool": "pen",
        "draw_shape": "freehand",
        "trace_algorithm": "fit",
        "snap_enabled": True,
        "reference_image": None,
        "cut_gap": 0,
        "panel_scroll": 0,
        "selection_bbox": None,
        "selected_curve": curve,
    }


def _styled_stroke(factory):
    stroke = _stroke()
    comps = m.strokes._stroke_components(stroke)
    comps[0]["styles"] = [factory()]
    stroke["components"] = comps
    return stroke


def _render(state):
    # Other suites call pygame.quit() in tearDown, so fonts/surfaces must be
    # recreated for each render instead of cached at import time.
    pygame.font.init()
    screen = pygame.Surface((cfg.WIDTH, cfg.HEIGHT))
    fonts = make_fonts()
    panel_view.draw_panel(screen, fonts, (0, 0), state)
    return state


def _slider_rects(state):
    entries = state.get("wave_slider_rects") or {}
    rects = {}
    for key, value in entries.items():
        rect = value[0] if isinstance(value, (tuple, list)) else value
        if isinstance(rect, pygame.Rect):
            rects[key] = rect
    return rects


class TestShadowStepperLayout(unittest.TestCase):
    def test_shadow_blur_stepper_does_not_overlap_color_tabs(self):
        state = _base_state(obj=set_appearance(_stroke(), shadow={"blur": 8}))
        # Appearance is folded by default; expand it so the stepper is drawn.
        state["panel_sections"] = {"selection_appearance": True}
        _render(state)

        blur_rects = [state["shadow_blur_minus_rect"], state["shadow_blur_plus_rect"]]
        tab_rects = [state["tab_stroke_rect"], state["tab_fill_rect"]]

        for blur in blur_rects:
            self.assertGreater(blur.w, 0)
            for tab in tab_rects:
                self.assertFalse(
                    blur.colliderect(tab),
                    f"shadow stepper {blur} overlaps color tab {tab}",
                )

        self.assertGreaterEqual(
            min(tab.top for tab in tab_rects),
            max(blur.bottom for blur in blur_rects),
        )


class TestCurveStyleSliderLayout(unittest.TestCase):
    def _curve_state(self, factory):
        obj = _styled_stroke(factory)
        return _render(_base_state(obj=obj, submode="curve", curve=(0, 0)))

    def test_repeat_sliders_start_below_the_drawing_box(self):
        state = self._curve_state(default_repeat_params)
        sliders = _slider_rects(state)
        box = state["wave_custom_box_rect"]

        self.assertEqual(set(sliders), {"amplitude", "frequency", "phase"})
        self.assertGreater(box.w, 0)
        self.assertGreaterEqual(min(rect.top for rect in sliders.values()), box.bottom)
        for key, rect in sliders.items():
            self.assertFalse(rect.colliderect(box), f"{key} slider overlaps repeat box")

    def test_thickness_sliders_start_below_the_drawing_box(self):
        state = self._curve_state(default_thickness_params)
        sliders = _slider_rects(state)
        box = state["wave_custom_box_rect"]

        self.assertEqual(set(sliders), {"amplitude"})
        self.assertGreater(box.w, 0)
        self.assertGreaterEqual(min(rect.top for rect in sliders.values()), box.bottom)
        self.assertFalse(sliders["amplitude"].colliderect(box))

    def test_displacement_sliders_start_below_the_affect_buttons(self):
        state = self._curve_state(default_displacement_params)
        sliders = _slider_rects(state)
        affects = [rect for rect in (state.get("displacement_affect_rects") or {}).values()]

        self.assertEqual(
            set(sliders),
            {"location", "handle_rotate", "handle_length", "noise_scale", "seed"},
        )
        self.assertTrue(affects)
        self.assertGreaterEqual(
            min(rect.top for rect in sliders.values()),
            max(rect.bottom for rect in affects),
        )
        for key, rect in sliders.items():
            for affect in affects:
                self.assertFalse(
                    rect.colliderect(affect), f"{key} slider overlaps affect button"
                )

    def test_wave_sliders_start_below_the_shape_selector(self):
        state = self._curve_state(default_wave_params)
        sliders = _slider_rects(state)
        shape_rects = [state["wave_shape_prev_rect"], state["wave_shape_next_rect"]]

        self.assertEqual(set(sliders), {"amplitude", "frequency", "phase"})
        self.assertGreaterEqual(
            min(rect.top for rect in sliders.values()),
            max(rect.bottom for rect in shape_rects),
        )
        for key, rect in sliders.items():
            for shape_rect in shape_rects:
                self.assertFalse(
                    rect.colliderect(shape_rect), f"{key} slider overlaps shape button"
                )


if __name__ == "__main__":
    unittest.main()
