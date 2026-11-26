"""Regression coverage for double-click numeric field text entry.

A single click scrubs as before; a second click on the same field opens an
inline editor. Typing replaces the current value, Enter commits (clamped and
stepped), Escape cancels, and clicking elsewhere commits before the click is
handled normally.
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
from controllers import numeric_field_edit as edit  # noqa: E402
from controllers.input.drag_field_keys import handle_drag_field_keys  # noqa: E402
from controllers.key_down import handle_keydown  # noqa: E402
from models.appearance import get_appearance  # noqa: E402
from models.waves import _get_distortion_style, default_wave_params  # noqa: E402
from views.widgets import draw_numeric_field_edit, make_fonts  # noqa: E402


def _mouse(pos, when=None):
    event = types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1, pos=pos)
    return event


def _key(key, unicode=""):
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key, unicode=unicode)


def _typed(text):
    return [_key(ord(ch), ch) for ch in text]


class _Ctx(types.SimpleNamespace):
    """Mutable ctx bag with typed-state-style attribute writes."""

    def set_edit(self, value):
        self.drag_field_edit = value
        self.state["drag_field_edit"] = value


class _FieldHarness(unittest.TestCase):
    rect = pygame.Rect(100, 100, 200, cfg.DRAG_FIELD_H)

    def setUp(self):
        self.field = types.SimpleNamespace(
            rect=self.rect.copy(), value=4, min_v=2, max_v=10,
            enabled=True, dragging=False,
        )
        self.state = {
            "wave_slider_rects": {}, "obj_opacity_rect": pygame.Rect(0, 0, 0, 0),
            "ref_opacity_rect": pygame.Rect(0, 0, 0, 0),
            "alpha_rect": pygame.Rect(0, 0, 0, 0), "cut_gap": 0,
        }
        self.ctx = _Ctx(
            state=self.state, slider=self.field,
            cut_gap_slider=types.SimpleNamespace(
                rect=pygame.Rect(0, 0, 0, 0), value=0, min_v=0, max_v=20),
            width_slider=types.SimpleNamespace(
                rect=pygame.Rect(0, 0, 0, 0), value=3, min_v=1, max_v=20,
                enabled=False),
            max_points_per_curve=4, cut_gap=0, tool_mode="draw",
            selected_strokes=set(), selected_curve=None, selected_point=None,
            selection_submode="transform", strokes=[], reference_image=None,
            drag_field_edit=None, drag_field_last_click=None,
            wave_slider_drag=None, wave_custom_drag=None,
            picker_drag_alpha=False, obj_opacity_drag=False,
            ref_opacity_drag=False, bucket_picker_drag=None,
            NORMAL_MAX_POINTS=5, BOOST_MAX_POINTS=100,
        )

    def _double_click(self, pos=(150, 110), times=(100, 200)):
        with mock.patch.object(pygame.time, "get_ticks", side_effect=times):
            first = edit.handle_mousedown(self.ctx, _mouse(pos))
            second = edit.handle_mousedown(self.ctx, _mouse(pos))
        return first, second


class TestDoubleClickDetection(_FieldHarness):
    def test_first_click_is_not_consumed_and_records_the_field(self):
        with mock.patch.object(pygame.time, "get_ticks", return_value=100):
            result = edit.handle_mousedown(self.ctx, _mouse((150, 110)))

        self.assertIsNone(result)
        self.assertIsNone(self.ctx.drag_field_edit)
        self.assertEqual(self.ctx.drag_field_last_click["id"], "points")
        self.assertEqual(self.ctx.drag_field_last_click["pos"], (150, 110))

    def test_second_click_opens_the_editor_and_cancels_any_scrub(self):
        self.field.dragging = True
        self.ctx.wave_slider_drag = {"key": "amplitude"}

        first, second = self._double_click()

        self.assertIsNone(first)
        self.assertEqual(second, "continue")
        self.assertEqual(self.ctx.drag_field_edit["id"], "points")
        self.assertEqual(self.ctx.drag_field_edit["buffer"], "4")
        self.assertTrue(self.ctx.drag_field_edit["replace_on_type"])
        self.assertIs(self.state["drag_field_edit"], self.ctx.drag_field_edit)
        self.assertFalse(self.field.dragging)
        self.assertIsNone(self.ctx.wave_slider_drag)

    def test_timeout_does_not_open_the_editor(self):
        self._double_click(times=(100, 100 + edit.DOUBLE_CLICK_MS + 1))
        self.assertIsNone(self.ctx.drag_field_edit)

    def test_motion_beyond_threshold_does_not_open_the_editor(self):
        with mock.patch.object(pygame.time, "get_ticks", side_effect=(100, 200)):
            edit.handle_mousedown(self.ctx, _mouse((150, 110)))
            result = edit.handle_mousedown(
                self.ctx, _mouse((150 + edit.DOUBLE_CLICK_DIST + 1, 110)))
        self.assertIsNone(result)
        self.assertIsNone(self.ctx.drag_field_edit)

    def test_click_outside_a_field_clears_the_last_click(self):
        with mock.patch.object(pygame.time, "get_ticks", return_value=100):
            edit.handle_mousedown(self.ctx, _mouse((10, 10)))
        self.assertIsNone(self.ctx.drag_field_last_click)

    def test_click_inside_the_editor_swallows_the_click(self):
        self._double_click()
        with mock.patch.object(pygame.time, "get_ticks", return_value=300):
            result = edit.handle_mousedown(self.ctx, _mouse((150, 110)))
        self.assertEqual(result, "continue")
        self.assertIsNotNone(self.ctx.drag_field_edit)

    def test_click_outside_commits_and_passes_to_normal_handling(self):
        self._double_click()
        for ev in _typed("9"):
            handle_drag_field_keys(self.ctx, ev)
        result = edit.handle_mousedown(self.ctx, _mouse((700, 400)))

        self.assertIsNone(result)
        self.assertIsNone(self.ctx.drag_field_edit)
        self.assertEqual(self.ctx.max_points_per_curve, 9)
        self.assertEqual(self.field.value, 9)


class TestNumericEntry(_FieldHarness):
    def _open_and_type(self, text):
        self._double_click()
        for ev in _typed(text):
            self.assertEqual(handle_drag_field_keys(self.ctx, ev), "continue")

    def test_typing_replaces_the_seed_value_and_backspace_edits_it(self):
        self._double_click()
        self.assertEqual(self.ctx.drag_field_edit["buffer"], "4")
        handle_drag_field_keys(self.ctx, _key(ord("5"), "5"))
        self.assertEqual(self.ctx.drag_field_edit["buffer"], "5")
        self.assertFalse(self.ctx.drag_field_edit["replace_on_type"])
        handle_drag_field_keys(self.ctx, _key(ord("0"), "0"))
        self.assertEqual(self.ctx.drag_field_edit["buffer"], "50")
        handle_drag_field_keys(self.ctx, _key(pygame.K_BACKSPACE))
        self.assertEqual(self.ctx.drag_field_edit["buffer"], "5")

    def test_enter_commits_clamped_and_stepped_value(self):
        self._open_and_type("99")
        handle_drag_field_keys(self.ctx, _key(pygame.K_RETURN))

        self.assertIsNone(self.ctx.drag_field_edit)
        self.assertEqual(self.ctx.max_points_per_curve, 10)
        self.assertEqual(self.field.value, 10)

    def test_escape_leaves_value_untouched(self):
        self._open_and_type("9")
        handle_drag_field_keys(self.ctx, _key(pygame.K_ESCAPE))

        self.assertIsNone(self.ctx.drag_field_edit)
        self.assertEqual(self.ctx.max_points_per_curve, 4)
        self.assertEqual(self.field.value, 4)

    def test_empty_or_incomplete_buffer_does_not_apply(self):
        self._double_click()
        for event in _typed("-"):
            handle_drag_field_keys(self.ctx, event)
        handle_drag_field_keys(self.ctx, _key(pygame.K_RETURN))
        self.assertEqual(self.ctx.max_points_per_curve, 4)

    def test_all_keys_are_consumed_while_editing(self):
        self._double_click()
        self.assertEqual(handle_drag_field_keys(self.ctx, _key(pygame.K_F1)), "continue")
        self.assertEqual(handle_keydown(self.ctx, _key(pygame.K_F1)), "continue")

    def test_cut_gap_commit_updates_the_slider_and_state(self):
        gap = types.SimpleNamespace(
            rect=pygame.Rect(200, 200, 200, cfg.DRAG_FIELD_H),
            value=0, min_v=0, max_v=20, enabled=True, dragging=False,
        )
        self.ctx.cut_gap_slider = gap
        self.ctx.slider.rect = pygame.Rect(0, 0, 0, 0)
        self.ctx.width_slider.enabled = False
        spec = next(s for s in edit.specifications(self.ctx)
                    if s["kind"] == "cut_gap")
        edit.begin(self.ctx, spec)
        for ev in _typed("7"):
            handle_drag_field_keys(self.ctx, ev)
        handle_drag_field_keys(self.ctx, _key(pygame.K_RETURN))
        self.assertEqual(self.state["cut_gap"], 7)
        self.assertEqual(gap.value, 7)

    def test_stroke_width_commit_updates_the_selected_stroke(self):
        stroke = {"stroke_width": 3.0}
        self.ctx.strokes = [stroke]
        self.ctx.selected_strokes = {0}
        self.ctx.tool_mode = "selection"
        width = types.SimpleNamespace(
            rect=pygame.Rect(200, 200, 200, cfg.DRAG_FIELD_H),
            value=3, min_v=1, max_v=20, enabled=True, dragging=False,
        )
        self.ctx.width_slider = width
        self.ctx.slider.rect = pygame.Rect(0, 0, 0, 0)
        spec = next(s for s in edit.specifications(self.ctx)
                    if s["kind"] == "stroke_width")
        edit.begin(self.ctx, spec)
        for ev in _typed("12"):
            handle_drag_field_keys(self.ctx, ev)
        handle_drag_field_keys(self.ctx, _key(pygame.K_RETURN))
        self.assertAlmostEqual(self.ctx.strokes[0]["stroke_width"], 12.0)

    def test_opacity_fields_interpret_typed_numbers_as_percent(self):
        stroke = {"stroke_width": 3.0}
        self.ctx.strokes = [stroke]
        self.ctx.selected_strokes = {0}
        self.state["obj_opacity_rect"] = pygame.Rect(
            400, 400, 200, cfg.DRAG_FIELD_H)
        self.ctx.slider.rect = pygame.Rect(0, 0, 0, 0)
        spec = next(s for s in edit.specifications(self.ctx)
                    if s["kind"] == "obj_opacity")
        self.assertEqual(spec["scale"], 100.0)
        self.assertEqual(edit.buffer_text(spec), "100")
        edit.begin(self.ctx, spec)
        for ev in _typed("35"):
            handle_drag_field_keys(self.ctx, ev)
        handle_drag_field_keys(self.ctx, _key(pygame.K_RETURN))

        self.assertAlmostEqual(get_appearance(self.ctx.strokes[0])["opacity"], 0.35)

    def test_wave_field_commit_updates_the_active_style(self):
        stroke = {"components": [default_wave_params()]}
        self.ctx.strokes = [stroke]
        self.ctx.selected_strokes = {0}
        self.ctx.selected_curve = (0, 0)
        self.ctx.state["wave_slider_rects"]["frequency"] = (
            pygame.Rect(500, 500, 200, cfg.DRAG_FIELD_H), 0.01, 1.0)
        self.ctx.slider.rect = pygame.Rect(0, 0, 0, 0)
        self.ctx._stroke_components = lambda s: s["components"]
        self.ctx._get_distortion_style = _get_distortion_style
        self.ctx._set_distortion_style = lambda comp, style, wi: comp.update(
            {"styles": [style]})
        spec = next(s for s in edit.specifications(self.ctx)
                    if s["id"] == "wave:frequency")
        edit.begin(self.ctx, spec)
        for ev in _typed("0.5"):
            handle_drag_field_keys(self.ctx, ev)
        handle_drag_field_keys(self.ctx, _key(pygame.K_RETURN))

        wave = _get_distortion_style(self.ctx.strokes[0]["components"][0], 0)
        self.assertAlmostEqual(wave["frequency"], 0.5)

    def test_reference_opacity_commit(self):
        self.ctx.reference_image = {"opacity": 0.5}
        self.state["ref_opacity_rect"] = pygame.Rect(
            600, 600, 200, cfg.DRAG_FIELD_H)
        self.ctx.slider.rect = pygame.Rect(0, 0, 0, 0)
        spec = next(s for s in edit.specifications(self.ctx)
                    if s["kind"] == "ref_opacity")
        edit.begin(self.ctx, spec)
        for ev in _typed("20"):
            handle_drag_field_keys(self.ctx, ev)
        handle_drag_field_keys(self.ctx, _key(pygame.K_RETURN))
        self.assertAlmostEqual(self.ctx.reference_image["opacity"], 0.2)


class TestEditorRendering(unittest.TestCase):
    def setUp(self):
        pygame.font.init()

    def test_overlay_is_clipped_to_the_field_rect(self):
        screen = pygame.Surface((400, 300))
        screen.fill((0, 0, 0))
        rect = pygame.Rect(100, 100, 200, cfg.DRAG_FIELD_H)
        with mock.patch.object(pygame.time, "get_ticks", return_value=0):
            draw_numeric_field_edit(
                screen, rect, 0.5, 0.0, 1.0, "12345678901234567890", "%",
                make_fonts()[1], label="Opacity")
        self.assertNotEqual(screen.get_at((rect.x + 2, rect.centery)),
                            (0, 0, 0, 255))
        self.assertEqual(screen.get_at((rect.x - 2, rect.centery)),
                         (0, 0, 0, 255))

    def test_display_text_includes_scale_and_suffix(self):
        spec = {
            "value": 0.42, "scale": 100.0, "suffix": "%", "decimals": 0,
        }
        self.assertEqual(edit.buffer_text(spec), "42")
        self.assertEqual(edit.display_text(spec), "42%")


if __name__ == "__main__":
    unittest.main()
