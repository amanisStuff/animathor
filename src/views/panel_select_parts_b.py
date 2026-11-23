"""View: panel_select parts B (SRP)."""
"""View: panel section (split for complexity)."""
import math
import pygame
import config as cfg
from config import *
from views.panel_select_parts import _draw_wave_graph, _value_ramp, _sv_surface, _hue_bar_surface
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

def _part_b2(c):
    _sync_in(c)
    screen=c.screen; fonts=c.fonts; mouse_pos=c.mouse_pos; state=c.state; x=c.x; y=c.y
    _button=c._button; _queue_tip=c._queue_tip; help_lines=c.help_lines
    font, font_small, font_title = fonts
    sel_strokes=c.sel_strokes; sel_count=c.sel_count; submode=c.submode; sel_stroke=c.sel_stroke
    if submode == "nodes" and sel_count == 1 and sel_stroke is not None:
        screen.blit(font_small.render("Path", True, TEXT_COLOR), (x, y)); y += 20
        pgap = 6
        pwidth = (PANEL_W - 40 - pgap) // 2
        for pi, (plabel, pkey) in enumerate([
                ("Close / Open", "path_close_rect"),
                ("Reverse", "path_reverse_rect"),
                ("Add Node", "path_add_rect"),
                ("Delete Node", "path_delete_rect"),
                ("Smooth", "path_smooth_rect"),
                ("Corner", "path_corner_rect")]):
            pr = pygame.Rect(x + (pi % 2) * (pwidth + pgap),
                             y + (pi // 2) * 28, pwidth, 24)
            state[pkey] = pr
            _button(pr, plabel)
            _queue_tip(pr, None, plabel)
        y += 28 * 3
        expand_r = pygame.Rect(x, y, PANEL_W - 40, 24)
        state["path_expand_rect"] = expand_r
        _button(expand_r, "Expand Stroke")
        _queue_tip(expand_r, None, "Expand stroke into a filled outline")
        y += 28 + 8
    else:
        for _k in PATH_KEYS:
            state[_k] = pygame.Rect(0, 0, 0, 0)

    _sel_curves_panel = set(state.get("selected_curves") or [])
    if not _sel_curves_panel and state.get("selected_curve"):
        _sel_curves_panel = {state.get("selected_curve")}
    c.y=y; c.help_lines=help_lines; c.sel_stroke=sel_stroke; c.submode=submode
    c.sel_count=sel_count; c.sel_strokes=sel_strokes
    _sync_out(c)
    _part_b2b(c)
    _sync_in(c)
    _sync_out(c)


def _part_b2b(c):
    _sync_in(c)
    screen=c.screen; fonts=c.fonts; mouse_pos=c.mouse_pos; state=c.state; x=c.x; y=c.y
    _button=c._button; _queue_tip=c._queue_tip; help_lines=c.help_lines
    font, font_small, font_title = fonts
    sel_strokes=c.sel_strokes; sel_count=c.sel_count; submode=c.submode; sel_stroke=c.sel_stroke
    _sel_curves_panel=getattr(c,"_sel_curves_panel",set())
    if submode == "curve" and len(_sel_curves_panel) > 1:
        screen.blit(font_small.render(f"Selected curves: {len(_sel_curves_panel)}", True, MUTED_COLOR), (x, y)); y += 22
        screen.blit(font_small.render("Shift+click to add or remove curves.", True, MUTED_COLOR), (x, y)); y += 20
        join_rect = pygame.Rect(x, y, PANEL_W - 40, 30)
        state["curve_join_rect"] = join_rect
        state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
        state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
        state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
        _button(join_rect, "Join curves")
        _queue_tip(join_rect, None, "Join selected curves (adjacent components)")
        y += 38
        _gap_slider = state.get("cut_gap_slider")
        if _gap_slider is not None:
            _gap_slider.track.width = 0
        state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
        state["wave_add_rect"] = pygame.Rect(0,0,0,0)
        state["displacement_add_rect"] = pygame.Rect(0,0,0,0)
        state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
        state["wave_bake_rect"] = pygame.Rect(0,0,0,0)
        state["wave_slider_rects"] = {}
        state["wave_shape_rects"] = {}
        state["displacement_profile_rects"] = {}
        state["wave_row_rects"] = []
        state["wave_formula_rect"] = pygame.Rect(0,0,0,0)
        state["wave_custom_box_rect"] = pygame.Rect(0,0,0,0)
        state["wave_smooth_rect"] = pygame.Rect(0,0,0,0)
        state["wave_clear_rect"] = pygame.Rect(0,0,0,0)
        state["wave_done_rect"] = pygame.Rect(0,0,0,0)
        state["repeat_pick_curve_rect"] = pygame.Rect(0,0,0,0)
        state["wave_reverse_rect"] = pygame.Rect(0,0,0,0)
        state["wave_clamp_rect"] = pygame.Rect(0,0,0,0)
    _sync_out(c)
    from views.panel_select_parts_b2 import _part_b2b_main
    _part_b2b_main(c)
    _sync_in(c)
    _sync_out(c)

