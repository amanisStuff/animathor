"""Regression tests for the bundled icon set and icon rendering.

Every icon name that reaches draw_icon()/draw_button() must resolve to a real
asset with visible pixels.  A missing asset used to leave several toolbar and
panel buttons completely blank; ``_draw_fallback_icon`` now also guarantees a
visible glyph for unknown names.
"""

import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from views import icons as icon_view  # noqa: E402

ICON_DIR = os.path.join(SRC, "assets", "icons")
BUILD_SCRIPT = os.path.join(ROOT, "tools", "build_icons.py")

# Names actually handed to draw_icon()/draw_button() by the views (including
# the menu bar and both toolbars).  Keep this list in sync when adding icons.
CALL_SITE_ICON_NAMES = {
    # left toolbar / shape palette / context menu
    "undo", "redo", "pen", "select", "shape_free", "shape_line", "shape_rect",
    "shape_square", "shape_ellipse", "shape_circle", "shape_triangle",
    "shape_polygon", "shape_star", "eraser", "cutter", "bucket", "text",
    # selection toolbar and properties panel
    "flip_h", "flip_v", "align_left", "align_hcenter", "align_right",
    "align_top", "align_vmiddle", "align_bottom", "eyedropper", "elev_front",
    "elev_forward", "elev_backward", "elev_back", "union", "intersect",
    "subtract", "exclude", "boost", "snap", "ref_load", "ref_visible",
    "ref_hidden", "ref_clear", "curve_redraw", "wave_add",
    "displacement_add", "repeat_add", "thickness_add", "wave_apply",
    # menu bar
    "open", "import", "save", "export", "copy",
}


def generator_icon_names():
    """Read the logical icon names declared in tools/build_icons.py."""
    with open(BUILD_SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not any(t in ("ICONS", "CUSTOM_SVG") for t in targets):
            continue
        if isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names.add(key.value)
    return names


class IconAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def test_generator_covers_every_call_site_icon(self):
        missing = CALL_SITE_ICON_NAMES - generator_icon_names()
        self.assertEqual(set(), missing,
                         f"icons used by views but not generated: {sorted(missing)}")

    def test_every_generated_icon_has_visible_assets(self):
        for name in sorted(generator_icon_names()):
            for size in (20, 24):
                with self.subTest(name=name, size=size):
                    surf = icon_view.load_icon(name, size)
                    self.assertIsNotNone(surf, f"missing asset {name}_{size}.png")
                    self.assertGreater(pygame.mask.from_surface(surf, 1).count(), 0,
                                       f"empty asset {name}_{size}.png")

    def test_every_bundled_png_has_visible_pixels(self):
        for filename in sorted(os.listdir(ICON_DIR)):
            if not filename.endswith(".png"):
                continue
            with self.subTest(filename=filename):
                surf = pygame.image.load(os.path.join(ICON_DIR, filename)).convert_alpha()
                self.assertGreater(pygame.mask.from_surface(surf, 1).count(), 0,
                                   f"empty asset {filename}")

    def test_draw_icon_renders_visible_pixels(self):
        screen = pygame.Surface((48, 48), pygame.SRCALPHA)
        for name in sorted(generator_icon_names()):
            for size in (20, 24):
                with self.subTest(name=name, size=size):
                    screen.fill((0, 0, 0, 0))
                    icon_view.draw_icon(screen, name, pygame.Rect(0, 0, 48, 48),
                                        color=(255, 255, 255), size=size)
                    self.assertGreater(pygame.mask.from_surface(screen, 1).count(), 0,
                                       f"{name}_{size}.png did not render")

    def test_unknown_icon_gets_a_visible_fallback(self):
        screen = pygame.Surface((48, 48), pygame.SRCALPHA)
        screen.fill((0, 0, 0, 0))
        icon_view.draw_icon(screen, "icon_that_does_not_exist",
                            pygame.Rect(0, 0, 48, 48), color=(255, 255, 255))
        self.assertGreater(pygame.mask.from_surface(screen, 1).count(), 0)

    def test_call_site_icons_have_tooltips(self):
        for name in sorted(CALL_SITE_ICON_NAMES):
            with self.subTest(name=name):
                self.assertIn(name, icon_view.BUTTON_TIPS)


if __name__ == "__main__":
    unittest.main()
