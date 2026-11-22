"""Render a headless preview of the application chrome for visual checks.

Usage::

    python tools/render_ui_preview.py [output.png] [--mode draw|selection]

The script uses SDL's dummy video driver, so it works on CI / without a display.
It is intentionally small: it only draws the static UI chrome (menu bar, toolbars,
panel) over a blank canvas, which is enough to review visual consistency.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import pygame  # noqa: E402

import app  # noqa: E402
from views.widgets import make_fonts  # noqa: E402
from views.menu import draw_menu_bar  # noqa: E402
from views.panel import draw_panel, draw_panel_toggle  # noqa: E402
from views.toolbar import (  # noqa: E402
    draw_bottom_shape_toolbar,
    draw_left_toolbar,
)


def base_state(mode="draw"):
    """Build a minimal state dict accepted by the panel drawing code."""
    pw = app.PANEL_W - 40
    btn = lambda label="", h=34: app.Button((0, 0, pw, h), label)  # noqa: E731
    slider = app.Slider(app.PANEL_X + 20, 0, pw, 2, 5, 4)
    width_slider = app.Slider(app.PANEL_X + 20, 0, pw, 1, 20, 3)
    st = {
        "tool_mode": mode,
        "max_points": 4,
        "boost_points": False,
        "NORMAL_MAX_POINTS": 5,
        "BOOST_MAX_POINTS": 100,
        "slider": slider,
        "width_slider": width_slider,
        "buttons": {"boost": btn("Boost limit"), "actions": [btn("Undo", 36), btn("Clear", 36)]},
        "stroke_count": 0,
        "selected_strokes": set(),
        "selected_obj": None,
        "stroke_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.STROKE_SWATCHES],
        "fill_swatch_rects": [pygame.Rect(0, 0, 0, 0) for _ in app.FILL_SWATCHES],
        "color_target": "stroke",
        "picker_h": 10.0,
        "picker_s": 0.5,
        "picker_v": 0.8,
        "picker_drag_sv": False,
        "picker_drag_hue": False,
        "sv_rect": pygame.Rect(0, 0, 0, 0),
        "hue_rect": pygame.Rect(0, 0, 0, 0),
        "alpha_rect": pygame.Rect(0, 0, 0, 0),
        "tab_stroke_rect": pygame.Rect(0, 0, 0, 0),
        "tab_fill_rect": pygame.Rect(0, 0, 0, 0),
        "nofill_rect": pygame.Rect(0, 0, 0, 0),
        "selection_submode": "transform",
        "nodes_toggle_rect": pygame.Rect(0, 0, 0, 0),
        "panel_scroll": 0,
        "panel_collapsed": False,
        "draw_tool": "pen",
        "draw_shape": "freehand",
        "snap_enabled": True,
        "shape_menu_key": None,
        "shape_menu_rect": pygame.Rect(0, 0, 0, 0),
        "shape_menu_item_rects": {},
        "panel_toggle_rect": pygame.Rect(0, 0, 0, 0),
    }
    return st


def render(path, mode="draw", menu_open=None):
    pygame.init()
    screen = pygame.display.set_mode((app.WIDTH, app.HEIGHT))
    fonts = make_fonts()
    state = base_state(mode)

    canvas = app.make_cairo_surface(app.CANVAS_W, app.canvas_viewport_height())
    screen.fill(app.CANVAS_BACKDROP)
    screen.blit(app.surface_to_pygame(canvas), (app.CANVAS_X, app.TOP_BAR_H))

    btn_draw = app.Button((8, 40, 40, 40), "")
    btn_select = app.Button((8, 88, 40, 40), "")
    draw_left_toolbar(screen, (-100, -100), mode, btn_draw, btn_select,
                      app.Button((8, 100, 40, 40), ""), app.Button((8, 148, 40, 40), ""),
                      True, False)
    draw_panel(screen, fonts, (-100, -100), state)
    draw_panel_toggle(screen, (-100, -100), state)
    draw_bottom_shape_toolbar(screen, fonts, (-100, -100), state)

    # Drawn last, exactly like the real app, so an open dropdown overlays chrome.
    draw_menu_bar(screen, fonts[1], (-100, -100), menu_open)

    pygame.image.save(screen, path)
    pygame.quit()
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "ui-preview.png"
    mode = "selection" if "--mode" in sys.argv and sys.argv[sys.argv.index("--mode") + 1] == "selection" else "draw"
    print(render(out, mode))
