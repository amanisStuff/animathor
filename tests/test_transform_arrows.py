"""Regression coverage for the transform-field arrow nudge controls."""

import os
import types
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

pygame.font.init()

from controllers.input.xform_field_keys import handle_xform_field_keys  # noqa: E402
from controllers.panel.transform_fields import transform_fields_typed  # noqa: E402
from models.interaction import xform_step  # noqa: E402
from views import panel_domain_selection as pds  # noqa: E402
from views.widgets import make_fonts  # noqa: E402


class TestXformStep(unittest.TestCase):
    def test_default_fine_and_coarse_steps(self):
        self.assertEqual(xform_step(), 1.0)
        self.assertEqual(xform_step(fine=True), 0.1)
        self.assertEqual(xform_step(coarse=True), 10.0)

    def test_fine_wins_when_both_modifiers_are_held(self):
        self.assertEqual(xform_step(fine=True, coarse=True), 0.1)


class TestArrowRendering(unittest.TestCase):
    def setUp(self):
        # Other tests may have called pygame.quit(), which de-inits fonts.
        pygame.font.init()

    def test_steppers_render_arrow_glyphs(self):
        self.assertEqual(pds.XFORM_ARROW_LEFT, chr(0x25C0))
        self.assertEqual(pds.XFORM_ARROW_RIGHT, chr(0x25B6))
        font = make_fonts()[1]
        for glyph in (pds.XFORM_ARROW_LEFT, pds.XFORM_ARROW_RIGHT):
            surface = font.render(glyph, True, (255, 255, 255))
            self.assertGreater(pygame.mask.from_surface(surface).count(), 0,
                               f"glyph {hex(ord(glyph))} must be visible")

    def test_view_uses_arrows_for_the_transform_steppers(self):
        import inspect
        source = inspect.getsource(pds.render_selection_a)
        self.assertIn("_button(minus_r, XFORM_ARROW_LEFT", source)
        self.assertIn("_button(plus_r, XFORM_ARROW_RIGHT", source)


class TestMouseArrowStep(unittest.TestCase):
    def _click(self, key, mods=0):
        tools = types.SimpleNamespace(tool_mode="selection")
        selection = types.SimpleNamespace(
            selection_submode="transform", selected_strokes={0},
            selected_point=None, selected_curve=None, selected_curves=set())
        document = types.SimpleNamespace(strokes=[None])
        drag = types.SimpleNamespace(
            transform_drag=None, drag_last=None, pending_transform_toggle=None)
        ui = types.SimpleNamespace(xform_field_focus="x", xform_field_buffer="1")
        rect = pygame.Rect(100, 100, 18, 24)
        state = {f"xform_x{key}_rect": rect}
        event = types.SimpleNamespace(pos=rect.center, mod=mods)
        apply_xform_field = mock.Mock()
        xform_current_value = mock.Mock(return_value=10.0)
        transform_fields_typed(
            tools, selection, document, drag, ui, state, event,
            mock.Mock(), None, None, None, None,
            apply_xform_field, xform_current_value, {}, {})
        return apply_xform_field

    def test_left_arrow_decrements_by_one(self):
        call = self._click("m")
        call.assert_called_once_with("x", -1.0, relative=True)

    def test_right_arrow_increments_finely_with_ctrl(self):
        call = self._click("p", pygame.KMOD_CTRL)
        call.assert_called_once_with("x", 0.1, relative=True)

    def test_right_arrow_increments_coarsely_with_shift(self):
        call = self._click("p", pygame.KMOD_SHIFT)
        call.assert_called_once_with("x", 10.0, relative=True)


class TestKeyboardArrowStep(unittest.TestCase):
    def _key(self, key, mods=0):
        ctx = types.SimpleNamespace(
            xform_field_focus="x", tool_mode="selection",
            selection_submode="transform", selected_strokes={0},
            xform_field_buffer="", state={}, step=None,
            _apply_xform_field=mock.Mock())
        event = types.SimpleNamespace(key=key, unicode="", mod=mods)
        result = handle_xform_field_keys(ctx, event)
        self.assertEqual(result, "continue")
        return ctx

    def test_left_and_right_are_aliases_for_down_and_up(self):
        right = self._key(pygame.K_RIGHT)
        right._apply_xform_field.assert_called_once_with("x", 1.0, relative=True)
        left = self._key(pygame.K_LEFT)
        left._apply_xform_field.assert_called_once_with("x", -1.0, relative=True)

    def test_up_and_down_still_work(self):
        up = self._key(pygame.K_UP)
        up._apply_xform_field.assert_called_once_with("x", 1.0, relative=True)
        down = self._key(pygame.K_DOWN)
        down._apply_xform_field.assert_called_once_with("x", -1.0, relative=True)

    def test_ctrl_gives_fine_step_and_shift_gives_coarse_step(self):
        fine = self._key(pygame.K_RIGHT, pygame.KMOD_CTRL)
        fine._apply_xform_field.assert_called_once_with("x", 0.1, relative=True)
        coarse = self._key(pygame.K_LEFT, pygame.KMOD_SHIFT)
        coarse._apply_xform_field.assert_called_once_with("x", -10.0, relative=True)
        both = self._key(pygame.K_RIGHT, pygame.KMOD_CTRL | pygame.KMOD_SHIFT)
        both._apply_xform_field.assert_called_once_with("x", 0.1, relative=True)


if __name__ == "__main__":
    unittest.main()
