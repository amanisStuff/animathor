"""Regression coverage for Blender/Krita-style draggable numeric fields.

A click starts a scrub from the field's current value; horizontal motion changes
the value relative to that starting point rather than jumping to the click
position. Ctrl/Meta is fine control and Shift is coarse control.
"""
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
pygame.font.init()

import config as cfg  # noqa: E402
from controllers.mouse_motion.guide_cut_motion import mm_part1  # noqa: E402
from controllers.mouse_motion.wave_motion import (  # noqa: E402
    color_picker_drag_move,
    wave_slider_drag_move,
)
from controllers.panel.wave_hits import _b3_wave_sliders  # noqa: E402
from models.geometry import clamp, color_alpha, set_color_alpha  # noqa: E402
from models.interaction import scrub_value  # noqa: E402
from models.waves import _get_distortion_style, default_wave_params  # noqa: E402
from views.panel_domain_style_effects import draw_style_slider  # noqa: E402
from views.widgets import (  # noqa: E402
    DragField,
    Slider,
    drag_modifiers,
    draw_drag_field,
    make_fonts,
)


def _event(kind, pos, mod=0):
    return types.SimpleNamespace(type=kind, button=1, pos=pos, mod=mod)


class TestScrubValue(unittest.TestCase):
    def test_click_without_motion_keeps_the_start_value(self):
        self.assertEqual(scrub_value(6.0, 0.0, 10.0, 200, 150, 150), 6.0)

    def test_drag_is_relative_to_the_click_position(self):
        self.assertAlmostEqual(scrub_value(2.0, 0.0, 10.0, 200, 100, 120), 3.0)
        self.assertAlmostEqual(scrub_value(8.0, 0.0, 10.0, 200, 100, 60), 6.0)

    def test_value_is_clamped_to_the_field_range(self):
        self.assertEqual(scrub_value(9.0, 0.0, 10.0, 100, 50, 500), 10.0)
        self.assertEqual(scrub_value(1.0, 0.0, 10.0, 100, 50, -500), 0.0)

    def test_empty_range_returns_the_lower_bound(self):
        self.assertEqual(scrub_value(7.0, 5.0, 5.0, 100, 10, 50), 5.0)

    def test_ctrl_and_meta_give_fine_control(self):
        self.assertAlmostEqual(
            scrub_value(5.0, 0.0, 100.0, 200, 100, 120, fine=True), 6.0)
        self.assertTrue(drag_modifiers(_event(0, (0, 0), pygame.KMOD_META))[0])

    def test_shift_gives_coarse_control(self):
        self.assertAlmostEqual(
            scrub_value(5.0, 0.0, 100.0, 200, 100, 120, coarse=True), 55.0)

    def test_step_quantises_integral_fields(self):
        self.assertEqual(
            scrub_value(4.0, 2.0, 10.0, 100, 50, 70, step=1.0), 6.0)


class TestDragModifiers(unittest.TestCase):
    def test_event_modifiers(self):
        self.assertEqual(drag_modifiers(_event(0, (0, 0), pygame.KMOD_CTRL)),
                         (True, False))
        self.assertEqual(drag_modifiers(_event(0, (0, 0), pygame.KMOD_SHIFT)),
                         (False, True))
        self.assertEqual(drag_modifiers(_event(0, (0, 0), 0)), (False, False))

    def test_falls_back_to_keyboard_state(self):
        with mock.patch.object(pygame.key, "get_mods",
                               return_value=pygame.KMOD_SHIFT):
            self.assertEqual(
                drag_modifiers(types.SimpleNamespace()), (False, True))


class TestDragFieldWidget(unittest.TestCase):
    def test_click_starts_a_drag_without_changing_the_value(self):
        field = DragField((100, 100, 200, cfg.DRAG_FIELD_H), 4, 0, 10)
        self.assertTrue(field.handle_event(
            _event(pygame.MOUSEBUTTONDOWN, (180, 110))))
        self.assertTrue(field.dragging)
        self.assertEqual(field.value, 4)
        self.assertEqual(field._start_x, 180)

    def test_drag_then_release_scrubs_the_value(self):
        field = DragField((100, 100, 200, cfg.DRAG_FIELD_H), 4, 0, 10)
        field.handle_event(_event(pygame.MOUSEBUTTONDOWN, (100, 110)))
        self.assertTrue(field.handle_event(
            _event(pygame.MOUSEMOTION, (150, 110))))
        self.assertAlmostEqual(field.value, 6.5)
        self.assertTrue(field.handle_event(
            _event(pygame.MOUSEBUTTONUP, (150, 110))))
        self.assertFalse(field.dragging)

    def test_event_modifiers_apply_while_dragging(self):
        fine = DragField((100, 100, 200, cfg.DRAG_FIELD_H), 5, 0, 100)
        fine.handle_event(_event(pygame.MOUSEBUTTONDOWN, (100, 110)))
        fine.handle_event(_event(pygame.MOUSEMOTION, (120, 110),
                                 pygame.KMOD_CTRL))
        self.assertAlmostEqual(fine.value, 6.0)

        coarse = DragField((100, 100, 200, cfg.DRAG_FIELD_H), 5, 0, 100)
        coarse.handle_event(_event(pygame.MOUSEBUTTONDOWN, (100, 110)))
        coarse.handle_event(_event(pygame.MOUSEMOTION, (120, 110),
                                   pygame.KMOD_SHIFT))
        self.assertAlmostEqual(coarse.value, 55.0)

    def test_disabled_or_hidden_fields_ignore_clicks(self):
        disabled = DragField((100, 100, 200, cfg.DRAG_FIELD_H), 4, 0, 10,
                             enabled=False)
        self.assertFalse(disabled.handle_event(
            _event(pygame.MOUSEBUTTONDOWN, (150, 110))))
        hidden = DragField((100, 100, 0, cfg.DRAG_FIELD_H), 4, 0, 10)
        self.assertFalse(hidden.handle_event(
            _event(pygame.MOUSEBUTTONDOWN, (100, 110))))

    def test_legacy_slider_is_a_drag_field_with_a_track_alias(self):
        slider = Slider(100, 100, 200, 2, 10, 4)
        self.assertIsInstance(slider, DragField)
        self.assertIs(slider.track, slider.rect)
        self.assertEqual(slider.display_text(), "4")
        slider.handle_event(_event(pygame.MOUSEBUTTONDOWN, (100, 110)))
        slider.handle_event(_event(pygame.MOUSEMOTION, (140, 110)))
        self.assertEqual(slider.value, 6)


class TestWaveFieldDrag(unittest.TestCase):
    def _ctx(self):
        rect = pygame.Rect(100, 100, 200, cfg.DRAG_FIELD_H)
        stroke = {"components": [default_wave_params()]}
        return types.SimpleNamespace(
            state={
                "wave_slider_rects": {"frequency": (rect, 0.0, 10.0)},
                "wave_active_index": 0,
            },
            tool_mode="selection",
            selected_strokes={0},
            selected_curve=(0, 0),
            selection_submode="curve",
            color_target="stroke",
            wave_formula_focus=False,
            strokes=[stroke],
            clamp=clamp,
            wave_custom_drag=None,
            wave_slider_drag=None,
            _stroke_components=lambda s: s["components"],
            _get_distortion_style=_get_distortion_style,
            _set_distortion_style=lambda comp, style, wi: comp.update(
                {"styles": [style]}),
        )

    def _frequency(self, ctx):
        return _get_distortion_style(ctx.strokes[0]["components"][0], 0)[
            "frequency"]

    def test_click_keeps_the_current_frequency(self):
        ctx = self._ctx()
        before = self._frequency(ctx)

        _b3_wave_sliders(ctx, _event(pygame.MOUSEBUTTONDOWN, (250, 110)), False)

        self.assertAlmostEqual(self._frequency(ctx), before)
        self.assertEqual(ctx.wave_slider_drag["start_x"], 250)
        self.assertAlmostEqual(ctx.wave_slider_drag["start_value"], before)

    def test_drag_scrubs_frequency_relative_to_the_click(self):
        ctx = self._ctx()
        _b3_wave_sliders(ctx, _event(pygame.MOUSEBUTTONDOWN, (200, 110)), False)
        before = self._frequency(ctx)

        with mock.patch.object(pygame.mouse, "get_pressed",
                               return_value=(1, 0, 0)):
            wave_slider_drag_move(ctx, _event(pygame.MOUSEMOTION, (220, 110)))

        self.assertAlmostEqual(self._frequency(ctx), before + 1.0)


class TestOpacityFieldDrag(unittest.TestCase):
    def test_reference_opacity_scrubs_from_the_click_snapshot(self):
        rect = pygame.Rect(100, 100, 200, cfg.DRAG_FIELD_H)
        ctx = types.SimpleNamespace(
            state={
                "ref_opacity_rect": rect,
                "ref_opacity_drag_start": (150, 0.6),
            },
            guide_drag=None,
            cutting=False,
            pan_drag=None,
            pivot_drag=None,
            ref_opacity_drag=True,
            reference_image={"opacity": 0.6},
            obj_opacity_drag=False,
            selected_strokes=set(),
            strokes=[],
            set_appearance=None,
            bucket_picker_drag=None,
            ref_drag=None,
            clamp=clamp,
        )

        mm_part1(ctx, _event(pygame.MOUSEMOTION, (100, 110)))

        self.assertAlmostEqual(ctx.reference_image["opacity"], 0.35)

    def test_alpha_scrubs_from_the_click_snapshot(self):
        rect = pygame.Rect(100, 100, 200, cfg.DRAG_FIELD_H)
        ctx = types.SimpleNamespace(
            state={
                "alpha_rect": rect,
                "alpha_drag_start": (150, 0.8),
                "color_target": "fill",
            },
            selected_strokes={0},
            selected_curve=None,
            selection_submode="transform",
            strokes=[{"fill_color": (0.1, 0.2, 0.3, 1.0)}],
            color_target="fill",
            picker_drag_sv=False,
            picker_drag_hue=False,
            picker_drag_alpha=True,
            picker_h=0.0,
            picker_s=0.0,
            picker_v=0.0,
            clamp=clamp,
            color_alpha=color_alpha,
            set_color_alpha=set_color_alpha,
            get_fill_gradient=lambda _stroke: None,
        )

        color_picker_drag_move(ctx, _event(pygame.MOUSEMOTION, (100, 110)))

        self.assertAlmostEqual(ctx.strokes[0]["fill_color"][3], 0.55)


class TestDragFieldLayout(unittest.TestCase):
    def setUp(self):
        # Other suites may call pygame.quit(); fonts must be live for rendering.
        pygame.font.init()

    def test_consecutive_style_fields_reserve_the_eight_pixel_gap(self):
        screen = pygame.Surface((cfg.PANEL_W, cfg.HEIGHT))
        font = make_fonts()[1]
        state = {}
        y = 100
        y = draw_style_slider(screen, font, state, 20, y, "Amplitude",
                              "amplitude", 8.0, 0.0, 20.0)
        y = draw_style_slider(screen, font, state, 20, y, "Frequency",
                              "frequency", 0.25, 0.0, 10.0)
        first = state["wave_slider_rects"]["amplitude"][0]
        second = state["wave_slider_rects"]["frequency"][0]

        self.assertEqual(first.h, cfg.DRAG_FIELD_H)
        self.assertEqual(second.h, cfg.DRAG_FIELD_H)
        self.assertGreaterEqual(second.top - first.bottom,
                                cfg.MIN_ELEMENT_SPACING)
        self.assertEqual(y, second.bottom + cfg.MIN_ELEMENT_SPACING)

    def test_drag_field_draws_inside_its_published_rect(self):
        screen = pygame.Surface((400, 300))
        rect = pygame.Rect(100, 100, 200, cfg.DRAG_FIELD_H)
        draw_drag_field(screen, rect, 5, 0, 10, "5", make_fonts()[1],
                        label="Opacity", mouse_pos=(150, 110))
        self.assertNotEqual(screen.get_at((rect.x + 2, rect.centery)),
                            (0, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()
