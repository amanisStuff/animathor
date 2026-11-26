"""View: panel_select parts B (SRP)."""
"""View: panel section (split for complexity)."""
from panel_rects import publish_rect  # noqa: E402
import math
import pygame
import config as cfg
from config import *
# Legacy star-import plumbing removed; explicit imports below define this module's contract.
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


import sys as _sys
import ctypes as _ctypes
try:
    _ctypes.pythonapi.PyFrame_LocalsToFast.argtypes = [_ctypes.py_object, _ctypes.c_int]
    _ctypes.pythonapi.PyFrame_FastToLocals.argtypes = [_ctypes.py_object]
except Exception:
    pass
def _sync_in(c, _f=None):
    f = _f or _sys._getframe(1)
    f.f_locals.update(c.__dict__)
    try: _ctypes.pythonapi.PyFrame_LocalsToFast(_ctypes.py_object(f), 0)
    except Exception: pass
def _sync_out(c, _f=None):
    f = _f or _sys._getframe(1)
    try: _ctypes.pythonapi.PyFrame_FastToLocals(_ctypes.py_object(f))
    except Exception: pass
    d=dict(f.f_locals); d.pop('c',None); c.__dict__.update(d)


BOOL_KEYS = ("bool_union_rect", "bool_intersect_rect", "bool_subtract_rect", "bool_exclude_rect")
_xform_keys = ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
               "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
               "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
               "xform_rm_rect", "xform_rp_rect")
DIST_KEYS = ("distribute_h_rect", "distribute_v_rect")
PATH_KEYS = ("path_close_rect", "path_reverse_rect", "path_add_rect",
             "path_delete_rect", "path_smooth_rect", "path_corner_rect",
             "path_expand_rect")
APPEAR_KEYS = ("obj_opacity_rect", "shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")

def render_path_section(screen, fonts, mouse_pos, state, x, y, _button, _queue_tip, help_lines,
                        sel_strokes, sel_count, submode, sel_stroke):
    """Explicit-contract render for Path section (no ctx-bag/sync_in-sync_out)."""
    font, font_small, font_title = fonts
    if submode == "nodes" and sel_count == 1 and sel_stroke is not None:
        screen.blit(font_small.render("Path", True, TEXT_COLOR), (x, y)); y += 20
        pgap = MIN_ELEMENT_SPACING
        pwidth = (PANEL_W - 40 - pgap) // 2
        row_pitch = 24 + MIN_ELEMENT_SPACING
        for pi, (plabel, pkey) in enumerate([
                ("Close / Open", "path_close_rect"),
                ("Reverse", "path_reverse_rect"),
                ("Add Node", "path_add_rect"),
                ("Delete Node", "path_delete_rect"),
                ("Smooth", "path_smooth_rect"),
                ("Corner", "path_corner_rect")]):
            pr = pygame.Rect(x + (pi % 2) * (pwidth + pgap),
                             y + (pi // 2) * row_pitch, pwidth, 24)
            state[pkey] = pr
            _button(pr, plabel)
            _queue_tip(pr, None, plabel)
        y += 3 * row_pitch
        expand_r = pygame.Rect(x, y, PANEL_W - 40, 24)
        publish_rect(state, "path_expand_rect", expand_r)
        _button(expand_r, "Expand Stroke")
        _queue_tip(expand_r, None, "Expand stroke into a filled outline")
        y += 24 + MIN_ELEMENT_SPACING
    else:
        for _k in PATH_KEYS:
            state[_k] = pygame.Rect(0, 0, 0, 0)
    sel_curves_panel = set(state.get("selected_curves") or [])
    if not sel_curves_panel and state.get("selected_curve"):
        sel_curves_panel = {state.get("selected_curve")}
    return {
        "y": y, "help_lines": help_lines, "sel_stroke": sel_stroke, "submode": submode,
        "sel_count": sel_count, "sel_strokes": sel_strokes, "sel_curves_panel": sel_curves_panel,
    }


def _part_b2(c):
    """Compat ctx-bag wrapper; core logic lives in render_path_section."""
    out = render_path_section(
        c.screen, c.fonts, c.mouse_pos, c.state, c.x, c.y, c._button, c._queue_tip, c.help_lines,
        c.sel_strokes, c.sel_count, c.submode, c.sel_stroke,
    )
    if isinstance(out, dict):
        c.y = out.get("y", c.y)
        c.help_lines = out.get("help_lines", c.help_lines)
        c.sel_stroke = out.get("sel_stroke", c.sel_stroke)
        c.submode = out.get("submode", c.submode)
        c.sel_count = out.get("sel_count", c.sel_count)
        c.sel_strokes = out.get("sel_strokes", c.sel_strokes)
        c._sel_curves_panel = out.get("sel_curves_panel", getattr(c, "_sel_curves_panel", []))
    _part_b2b(c)


def render_multi_curve_section(screen, fonts, state, x, y, _button, _queue_tip, submode, sel_curves_panel):
    """Explicit-contract render for multi-curve selection section."""
    font, font_small, font_title = fonts
    if submode == "curve" and len(sel_curves_panel) > 1:
        screen.blit(font_small.render(f"Selected curves: {len(sel_curves_panel)}", True, MUTED_COLOR), (x, y)); y += 22
        screen.blit(font_small.render("Shift+click to add or remove curves.", True, MUTED_COLOR), (x, y)); y += 20
        join_rect = pygame.Rect(x, y, PANEL_W - 40, 30)
        publish_rect(state, "curve_join_rect", join_rect)
        publish_rect(state, "curve_hide_rect", pygame.Rect(0,0,0,0))
        publish_rect(state, "curve_redraw_rect", pygame.Rect(0,0,0,0))
        publish_rect(state, "curve_cut_rect", pygame.Rect(0,0,0,0))
        _button(join_rect, "Join curves")
        _queue_tip(join_rect, None, "Join selected curves (adjacent components)")
        y += 38
        _gap_slider = state.get("cut_gap_slider")
        if _gap_slider is not None:
            _gap_slider.track.width = 0
        for k in ("wave_toggle_rect","wave_add_rect","displacement_add_rect","wave_remove_rect","wave_bake_rect",
                  "wave_formula_rect","wave_custom_box_rect","wave_smooth_rect","wave_clear_rect","wave_done_rect",
                  "repeat_pick_curve_rect","wave_reverse_rect","wave_clamp_rect"):
            state[k] = pygame.Rect(0,0,0,0)
        publish_rect(state, "wave_slider_rects", {})
        publish_rect(state, "wave_shape_rects", {})
        publish_rect(state, "displacement_profile_rects", {})
        publish_rect(state, "wave_row_rects", [])
    return y


def _part_b2b(c):
    """Compat ctx-bag wrapper; core logic lives in render_multi_curve_section."""
    c.y = render_multi_curve_section(
        c.screen, c.fonts, c.state, c.x, c.y, c._button, c._queue_tip, c.submode,
        getattr(c, "_sel_curves_panel", set()),
    )
    from views.panel_select_parts_b2 import _part_b2b_main
    _part_b2b_main(c)

