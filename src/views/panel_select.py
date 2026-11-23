"""View: panel section (split for complexity)."""
import math
import pygame
import config as cfg
from config import *
import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))
import views.canvas as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'icons', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))
from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip  # noqa: E402
from views.widgets import (  # noqa: E402
    draw_button, draw_card, draw_color_swatch as draw_swatch, draw_hue_cursor,
    draw_picker_cursor, draw_slider_knob, draw_toggle, draw_track,
    to_screen_rgb,
)

# Cached HSV picker gradients.
_SV_CACHE = {}
_SV_RAMP_CACHE = {}
_HUE_BAR_CACHE = {}

def _draw_wave_graph(screen, rect, poly, color, bg=PLOT_BG, line_w=2, mid=True):
    """Draw a normalized waveform polyline inside rect (x in [0,1], y in [-1,1])."""
    pygame.draw.rect(screen, bg, rect, border_radius=RADIUS_SM)
    if mid:
        pygame.draw.line(screen, PLOT_GRID, (rect.x + 3, rect.centery), (rect.right - 3, rect.centery), BORDER_WIDTH)
    if not poly or len(poly) < 2:
        return
    pad = 3
    hw = max(1, rect.w - 2 * pad)
    hh = max(1, rect.h - 2 * pad)
    pts = []
    for vx, vy in poly:
        px = rect.x + pad + clamp(vx, 0.0, 1.0) * hw
        py = rect.centery - clamp(vy, -1.15, 1.15) * (hh / 2.0)
        pts.append((px, py))
    pygame.draw.lines(screen, color, False, pts, line_w)

def _value_ramp(w, h):
    """Vertical white->black ramp used to turn an S gradient into an S/V square."""
    key = (w, h)
    ramp = _SV_RAMP_CACHE.get(key)
    if ramp is None:
        col = pygame.Surface((1, h))
        for iy in range(h):
            g = int(round(255 * (1.0 - iy / max(1, h - 1))))
            col.set_at((0, iy), (g, g, g))
        ramp = pygame.transform.smoothscale(col, (w, h))
        _SV_RAMP_CACHE[key] = ramp
    return ramp

def _sv_surface(hue, w, h):
    """Saturation/value square for a hue (built from a 1px row + value ramp)."""
    key = (round(float(hue), 1), w, h)
    surf = _SV_CACHE.get(key)
    if surf is None:
        row = pygame.Surface((w, 1))
        for ix in range(w):
            c = hsv_to_rgb(hue, ix / max(1, w - 1), 1.0)
            row.set_at((ix, 0), to_screen_rgb(c))
        surf = pygame.transform.smoothscale(row, (w, h))
        surf.blit(_value_ramp(w, h), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if len(_SV_CACHE) > 24:
            _SV_CACHE.clear()
        _SV_CACHE[key] = surf
    return surf

def _hue_bar_surface(w, h):
    """Full-saturation hue gradient strip."""
    key = (w, h)
    surf = _HUE_BAR_CACHE.get(key)
    if surf is None:
        surf = pygame.Surface((w, h))
        for ix in range(w):
            c = hsv_to_rgb((ix / max(1, w - 1)) * 360.0, 1.0, 1.0)
            pygame.draw.line(surf, to_screen_rgb(c), (ix, 0), (ix, h - 1))
        _HUE_BAR_CACHE[key] = surf
    return surf

def _draw_panel_select_mode(screen, fonts, mouse_pos, state, x, y, _button, _queue_tip):
    """Panel select mode (delegates to split parts for SRP)."""
    import types
    c = types.SimpleNamespace(
        screen=screen, fonts=fonts, mouse_pos=mouse_pos, state=state, x=x, y=y,
        _button=_button, _queue_tip=_queue_tip, help_lines=[],
        sel_strokes=state.get("selected_strokes", set()),
        sel_count=len(state.get("selected_strokes", set())),
        submode=state.get("selection_submode", "transform"),
        sel_stroke=state.get("selected_obj"),
    )
    from views.panel_select_parts import _part_a, _part_b
    from views.panel_select_parts_c import _part_c, _part_d
    _part_a(c); _part_b(c); _part_c(c); _part_d(c)
    return c.y, c.help_lines
