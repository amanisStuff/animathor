"""Tests for the shared UI design system.

These guard the "one visual language" guarantee: semantic tokens exist,
chrome code uses them (no ad-hoc radii or RGB literals), and the shared
primitives actually render with those tokens.
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import pygame  # noqa: E402

import config as cfg  # noqa: E402
from views.widgets import draw_button, make_fonts  # noqa: E402


CHROME_FILES = [
    os.path.join(_ROOT, "src", "views", "panel.py"),
    os.path.join(_ROOT, "src", "views", "toolbar.py"),
    os.path.join(_ROOT, "src", "views", "widgets.py"),
    os.path.join(_ROOT, "src", "views", "icons.py"),
    os.path.join(_ROOT, "src", "views", "menu.py"),
    os.path.join(_ROOT, "src", "controllers", "app_controller.py"),
    os.path.join(_ROOT, "tools", "render_ui_preview.py"),
]


class TestThemeTokens(unittest.TestCase):
    def test_all_exported_tokens_exist(self):
        missing = [name for name in cfg.__all__ if not hasattr(cfg, name)]
        self.assertEqual(missing, [], f"missing theme/layout tokens: {missing}")

    def test_colour_tokens_are_rgb(self):
        colour_tokens = [
            "SURFACE", "SURFACE_SUBTLE", "SURFACE_ALT", "SURFACE_SUNKEN",
            "SURFACE_DISABLED", "SHADOW_COLOR", "BORDER_SUBTLE", "BORDER_STRONG",
            "BORDER_DISABLED", "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_DISABLED",
            "TEXT_ON_ACCENT", "TEXT_DANGER", "TEXT_WARNING", "HOVER_BG",
            "ACTIVE_BG", "PRIMARY", "PRIMARY_HOVER", "PRIMARY_SOFT", "DANGER",
            "DISABLED", "PLOT_BG", "PLOT_BG_DISABLED", "PLOT_GRID",
            "PLOT_LINE_DISABLED", "TOOLTIP_BG", "TOOLTIP_BORDER", "TOOLTIP_TEXT",
            "CANVAS_BACKDROP", "SELECTION_BORDER", "CUT_COLOR",
            "NO_SWATCH_COLOR", "CUSTOM_CURVE_COLOR",
        ]
        for name in colour_tokens:
            value = getattr(cfg, name)
            self.assertIsInstance(value, tuple, name)
            self.assertEqual(len(value), 3, name)
            self.assertTrue(all(isinstance(c, int) and 0 <= c <= 255 for c in value), name)

    def test_radius_and_spacing_scales_are_ordered(self):
        radii = [getattr(cfg, f"RADIUS_{s}") for s in ("XS", "SM", "MD", "LG", "XL")]
        spaces = [getattr(cfg, f"SPACE_{s}") for s in ("XS", "SM", "MD", "LG", "XL")]
        self.assertEqual(radii, sorted(set(radii)))
        self.assertEqual(spaces, sorted(set(spaces)))
        self.assertTrue(all(r > 0 for r in radii))
        self.assertEqual(cfg.BORDER_WIDTH_ACTIVE, cfg.BORDER_WIDTH + 1)

    def test_legacy_names_alias_semantic_tokens(self):
        self.assertEqual(cfg.BUTTON_BG, cfg.SURFACE)
        self.assertEqual(cfg.BUTTON_HOVER, cfg.HOVER_BG)
        self.assertEqual(cfg.TOOL_ACTIVE, cfg.ACTIVE_BG)
        self.assertEqual(cfg.ACCENT, cfg.PRIMARY)
        self.assertEqual(cfg.TEXT_COLOR, cfg.TEXT_PRIMARY)
        self.assertEqual(cfg.MUTED_COLOR, cfg.TEXT_SECONDARY)


class TestChromeUsesTokens(unittest.TestCase):
    def test_no_literal_border_radii(self):
        import re
        offenders = []
        for path in CHROME_FILES:
            with open(path, encoding="utf-8") as handle:
                for i, line in enumerate(handle, 1):
                    if re.search(r"border_radius=\d", line):
                        offenders.append(f"{os.path.basename(path)}:{i}")
        self.assertEqual(offenders, [], f"hard-coded border radii: {offenders}")

    def test_no_literal_chrome_colours(self):
        import re
        pattern = re.compile(r"\(\s*\d{2,3}\s*,\s*\d{2,3}\s*,\s*\d{2,3}\s*\)")
        offenders = []
        for path in CHROME_FILES:
            with open(path, encoding="utf-8") as handle:
                for i, line in enumerate(handle, 1):
                    if pattern.search(line):
                        offenders.append(f"{os.path.basename(path)}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], f"hard-coded chrome colours: {offenders}")

    def test_fonts_come_from_tokens(self):
        pygame.font.init()
        fonts = make_fonts()
        self.assertEqual(len(fonts), 3)
        self.assertEqual(fonts[0].get_height() > 0, True)
        self.assertEqual(pygame.font.SysFont(None, cfg.FONT_SIZE_SMALL).get_height(),
                         fonts[1].get_height())


class TestCanvasEditorTokens(unittest.TestCase):
    EDITOR_FILE = os.path.join(_ROOT, "src", "views", "canvas.py")

    def test_editor_colours_are_cairo_ready(self):
        for name in ("EDITOR_SELECTION", "EDITOR_ACCENT", "EDITOR_ROTATION",
                     "EDITOR_HANDLE_FILL", "EDITOR_GUIDE", "EDITOR_TEMPLATE"):
            value = getattr(cfg, name)
            self.assertIsInstance(value, tuple, name)
            self.assertEqual(len(value), 3, name)
            self.assertTrue(all(isinstance(c, float) and 0.0 <= c <= 1.0 for c in value), name)

    def test_editor_rgb_sources_are_bytes(self):
        for name in ("EDITOR_SELECTION_RGB", "EDITOR_ACCENT_RGB",
                     "EDITOR_ROTATION_RGB", "EDITOR_HANDLE_FILL_RGB",
                     "EDITOR_GUIDE_RGB", "EDITOR_TEMPLATE_RGB"):
            value = getattr(cfg, name)
            self.assertTrue(all(isinstance(c, int) and 0 <= c <= 255 for c in value), name)

    def test_cairo_rgb_converts_and_preserves_alpha(self):
        self.assertEqual(cfg.cairo_rgb((255, 0, 128)), (1.0, 0.0, 0.501961))
        self.assertEqual(cfg.cairo_rgb((0, 255, 0), 0.5), (0.0, 1.0, 0.0, 0.5))

    def test_handle_scale_is_consistent(self):
        self.assertGreater(cfg.EDITOR_PIVOT_RADIUS, cfg.EDITOR_HANDLE_RADIUS)
        self.assertGreater(cfg.EDITOR_HANDLE_RADIUS, cfg.EDITOR_HANDLE_HALF)
        self.assertGreater(cfg.EDITOR_SNAP_RADIUS, cfg.EDITOR_SNAP_INNER)
        self.assertGreater(cfg.CUT_HANDLE_RADIUS, 0)
        widths = [cfg.EDITOR_LINE_WIDTH_SUBTLE, cfg.EDITOR_LINE_WIDTH,
                  cfg.EDITOR_LINE_WIDTH_BOLD]
        self.assertEqual(widths, sorted(set(widths)))

    def test_no_literal_editor_colours_in_canvas(self):
        import re
        pattern = re.compile(
            r"set_source_rgb[a]?\(\s*(?:0|1)(?:\.\d+)?\s*,\s*(?:0|1)(?:\.\d+)?\s*,\s*(?:0|1)(?:\.\d+)?"
        )
        offenders = []
        with open(self.EDITOR_FILE, encoding="utf-8") as handle:
            for i, line in enumerate(handle, 1):
                if pattern.search(line):
                    offenders.append(f"canvas.py:{i}: {line.strip()}")
        self.assertEqual(offenders, [], f"hard-coded editor colours: {offenders}")


class TestSharedPrimitives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _render_button(self, **kwargs):
        screen = pygame.Surface((100, 50), pygame.SRCALPHA)
        screen.fill((0, 0, 0, 255))
        rect = pygame.Rect(10, 10, 80, 30)
        mouse = kwargs.pop("mouse", None)
        draw_button(screen, rect, "", None, mouse_pos=mouse, **kwargs)
        return screen.get_at((50, 25))[:3]

    def test_active_button_uses_active_bg(self):
        self.assertEqual(self._render_button(active=True), cfg.ACTIVE_BG)

    def test_hover_button_uses_hover_bg(self):
        self.assertEqual(self._render_button(mouse=(20, 20)), cfg.HOVER_BG)

    def test_disabled_button_uses_disabled_bg(self):
        self.assertEqual(self._render_button(enabled=False), cfg.SURFACE_DISABLED)

    def test_resting_button_uses_surface(self):
        self.assertEqual(self._render_button(), cfg.SURFACE)

    def test_headless_ui_preview_renders(self):
        """Full chrome renders headlessly with token colours on the panel."""
        sys.path.insert(0, os.path.join(_ROOT, "tools"))
        from render_ui_preview import render
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "preview.png")
            render(path, "draw")
            self.assertTrue(os.path.isfile(path))
            self.assertGreater(os.path.getsize(path), 1000)
            image = pygame.image.load(path)
            # Panel background is the sunken surface token.
            self.assertEqual(image.get_at((cfg.PANEL_X + 8, cfg.TOP_BAR_H + 8))[:3],
                             cfg.PANEL_BG)
            # Left toolbar background uses the toolbar token.
            self.assertEqual(image.get_at((2, cfg.TOP_BAR_H + 8))[:3], cfg.TOOLBAR_BG)


class TestDataDefaultsAndControls(unittest.TestCase):
    """Shared data defaults and small control geometry live in config too."""

    def test_shared_colour_defaults_are_float_rgba(self):
        for name in ("DEFAULT_STROKE_RGBA", "DEFAULT_FILL_RGBA"):
            value = getattr(cfg, name)
            self.assertIsInstance(value, tuple, name)
            self.assertEqual(len(value), 4, name)
            self.assertTrue(
                all(isinstance(c, float) and 0.0 <= c <= 1.0 for c in value), name
            )

    def test_control_geometry_tokens_are_positive(self):
        for name in ("PICKER_HANDLE_RADIUS", "SLIDER_KNOB_RADIUS",
                     "CUT_HANDLE_RADIUS"):
            value = getattr(cfg, name)
            self.assertIsInstance(value, int, name)
            self.assertGreater(value, 0, name)

    def test_canvas_uses_shared_colour_defaults(self):
        canvas_path = os.path.join(_ROOT, "src", "views", "canvas.py")
        with open(canvas_path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("DEFAULT_STROKE_RGBA", source)
        self.assertIn("DEFAULT_FILL_RGBA", source)
        self.assertNotIn("color_rgba(fill, (0.0, 0.0, 0.0, 1.0))", source)

    def test_control_tokens_used_by_shared_primitives_and_controller(self):
        widgets_path = os.path.join(_ROOT, "src", "views", "widgets.py")
        controller_path = os.path.join(_ROOT, "src", "controllers", "app_controller.py")
        with open(widgets_path, encoding="utf-8") as handle:
            widgets = handle.read()
        with open(controller_path, encoding="utf-8") as handle:
            controller = handle.read()
        self.assertIn("PICKER_HANDLE_RADIUS", widgets)
        self.assertIn("SLIDER_KNOB_RADIUS", widgets)
        self.assertIn("CUT_HANDLE_RADIUS", controller)

    def test_editor_line_widths_used_in_canvas(self):
        canvas_path = os.path.join(_ROOT, "src", "views", "canvas.py")
        with open(canvas_path, encoding="utf-8") as handle:
            source = handle.read()
        for name in ("EDITOR_LINE_WIDTH", "EDITOR_LINE_WIDTH_BOLD",
                     "EDITOR_LINE_WIDTH_SUBTLE"):
            self.assertIn(name, source)


class TestSharedControlPrimitives(unittest.TestCase):
    """Repeated controls (swatches, knobs, cursors) have one implementation."""

    PANEL = os.path.join(_ROOT, "src", "views", "panel.py")
    TOOLBAR = os.path.join(_ROOT, "src", "views", "toolbar.py")
    WIDGETS = os.path.join(_ROOT, "src", "views", "widgets.py")

    def _read(self, path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_slider_uses_shared_knob_token(self):
        widgets = self._read(self.WIDGETS)
        self.assertIn("SLIDER_KNOB_RADIUS", widgets)
        self.assertNotIn("self.handle_r", widgets)

    def test_both_pickers_use_shared_cursor_helpers(self):
        panel = self._read(self.PANEL)
        self.assertEqual(panel.count("draw_picker_cursor("), 2)
        self.assertEqual(panel.count("draw_hue_cursor("), 2)

    def test_swatches_use_shared_primitive(self):
        panel = self._read(self.PANEL)
        toolbar = self._read(self.TOOLBAR)
        self.assertIn("draw_color_swatch", panel)
        self.assertIn("draw_color_swatch", toolbar)
        # No local swatch implementation or inline 0..1 -> 0..255 conversion.
        self.assertNotIn("def draw_swatch", panel)
        self.assertNotIn("int(c * 255)", panel)
        self.assertNotIn("int(c * 255)", toolbar)

    def test_slider_knob_single_implementation(self):
        panel = self._read(self.PANEL)
        self.assertIn("draw_slider_knob", panel)
        self.assertNotIn("SLIDER_KNOB_RADIUS)", panel)


class TestMenuBar(unittest.TestCase):
    """The top bar exposes the full command set through one data-driven tree."""

    CONTROLLER = os.path.join(_ROOT, "src", "controllers", "app_controller.py")

    def setUp(self):
        pygame.font.init()
        self.fonts = make_fonts()
        # An offscreen surface is enough: the menu reads cfg.WIDTH/HEIGHT.
        self.screen = pygame.Surface((cfg.WIDTH, cfg.HEIGHT))

    def test_conventional_menus_cover_all_actions(self):
        from views import menu as menu_view
        self.assertEqual([m[0] for m in menu_view.MENUS],
                         ["file", "edit", "view", "tools", "help"])
        keys = [i[0] for m in menu_view.MENUS for i in m[2] if i]
        self.assertGreaterEqual(len(keys), 25)
        self.assertEqual(len(keys), len(set(keys)), "duplicate menu item keys")

    def test_every_menu_item_has_a_controller_action(self):
        from views import menu as menu_view
        with open(self.CONTROLLER, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("def run_menu_action(key):", source)
        for key in (i[0] for m in menu_view.MENUS for i in m[2] if i):
            self.assertIn(f'"{key}"', source, f"no action for menu item {key}")

    def test_keyboard_and_menu_share_one_action_path(self):
        with open(self.CONTROLLER, encoding="utf-8") as handle:
            source = handle.read()
        self.assertGreaterEqual(source.count("run_menu_action("), 25)
        self.assertNotIn('menu_open == "file"', source)
        self.assertNotIn("menu_bar_rect =", source)

    def test_bar_and_dropdown_render_with_tokens(self):
        from views.menu import draw_menu_bar
        labels, items = draw_menu_bar(self.screen, self.fonts[1], (-100, -100), "edit")
        self.assertEqual(set(labels), {"file", "edit", "view", "tools", "help"})
        self.assertIn("undo", items)
        self.assertIn("paste", items)
        self.assertNotIn("save", items)  # only the open menu's items are hit-tested
        self.assertEqual(self.screen.get_at((5, 5))[:3], cfg.SURFACE_SUBTLE)

    def test_workspace_toggle_draws_and_registers_rect(self):
        from views.menu import draw_menu_bar
        state = {}
        labels, items = draw_menu_bar(self.screen, self.fonts[1], (-100, -100), "edit", state=state)
        self.assertEqual(set(labels), {"file", "edit", "view", "tools", "help"})
        self.assertIn("workspace_rect", state)
        self.assertGreater(state["workspace_rect"].w, 0)
        self.assertGreater(state["workspace_rect"].h, 0)

    def test_shortcuts_overlay_renders(self):
        from views.menu import draw_shortcuts_overlay
        rect = draw_shortcuts_overlay(self.screen, self.fonts[0], self.fonts[1])
        self.assertEqual((rect.centerx, rect.centery),
                         (cfg.WIDTH // 2, cfg.HEIGHT // 2))
        self.assertEqual(self.screen.get_at(rect.center)[:3], cfg.SURFACE)


if __name__ == "__main__":
    unittest.main()
