"""View: panel_select parts B (SRP)."""
"""View: panel section (split for complexity)."""
from panel_rects import publish_rect  # noqa: E402
import math
import pygame
import config as cfg
from config import *
from controllers.coordinates import clamp
from views.panel_select_parts import _draw_wave_graph, _value_ramp, _sv_surface, _hue_bar_surface
from models.waves import WAVE_SHAPE_LABELS
from models.waves_extra import _wave_icon_polyline
from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip  # noqa: E402
from views.widgets import (  # noqa: E402
    draw_button, draw_card, draw_color_swatch as draw_swatch, draw_drag_field,
    draw_hue_cursor, draw_picker_cursor, draw_toggle,
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


def draw_style_slider(screen, font_small, state, x, y, label, key, val, lo, hi,
                      fmt=None, enabled_sl=True):
    """Draw one parameter slider at ``y`` and return the next layout y.

    Each style section owns its own ``y`` cursor. A shared closure over the
    caller's ``y`` used to draw sliders at a stale position, placing them on
    top of the style header/buttons and leaving later controls too high.
    """
    field = pygame.Rect(x, y, PANEL_W - 40, DRAG_FIELD_H)
    draw_drag_field(
        screen, field, val, lo, hi,
        fmt(val) if fmt else str(val), font_small,
        enabled=enabled_sl, label=label,
    )
    if enabled_sl:
        state.setdefault("wave_slider_rects", {})[key] = (field, lo, hi)
    return field.bottom + MIN_ELEMENT_SPACING


def _local_style_slider(screen, font_small, state, x, y_holder):
    """Build a slider callback that advances ``y_holder['y']``."""
    def slider(label, key, val, lo, hi, fmt=None, enabled_sl=True):
        y_holder["y"] = draw_style_slider(
            screen, font_small, state, x, y_holder["y"], label, key, val, lo, hi,
            fmt=fmt, enabled_sl=enabled_sl,
        )
    return slider


def render_displacement_section(screen, font_small, state, x, y, _button, _style_slider, active_style):
    """Explicit-contract render for displacement style section."""
    publish_rect(state, "displacement_profile_rects", {})
    publish_rect(state, "wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
    state["wave_custom_draw"] = False
    publish_rect(state, "wave_smooth_rect", pygame.Rect(0, 0, 0, 0))
    publish_rect(state, "wave_reverse_rect", pygame.Rect(0, 0, 0, 0))
    publish_rect(state, "wave_clamp_rect", pygame.Rect(0, 0, 0, 0))
    screen.blit(font_small.render("Point displacement (along path)", True, TEXT_COLOR), (x, y)); y += 20
    screen.blit(font_small.render("Apply to", True, TEXT_COLOR), (x, y)); y += 20
    affect_rects = {}
    affect_items = [("affect_x", "X"), ("affect_y", "Y"), ("affect_rotate", "Rotate"), ("affect_length", "Length")]
    cols = 2
    gap = MIN_ELEMENT_SPACING
    row_pitch = 24 + MIN_ELEMENT_SPACING
    bw = (PANEL_W - 40 - gap * (cols - 1)) // cols
    for i, (akey, alabel) in enumerate(affect_items):
        rowi, coli = divmod(i, cols)
        r = pygame.Rect(x + coli * (bw + gap), y + rowi * row_pitch, bw, 24)
        affect_rects[akey] = r
        on = bool(active_style.get(akey, True))
        _button(r, alabel, active=on)
    publish_rect(state, "displacement_affect_rects", affect_rects)
    y += ((len(affect_items) + cols - 1) // cols) * row_pitch + MIN_ELEMENT_SPACING
    screen.blit(font_small.render("Parameters", True, TEXT_COLOR), (x, y)); y += 20
    loc_v = float(active_style.get("location", 0.0) or 0.0)
    rot_v = float(active_style.get("handle_rotate", 0.0) or 0.0)
    len_v = float(active_style.get("handle_length", 0.0) or 0.0)
    nsc_v = float(active_style.get("noise_scale", 1.0) or 1.0)
    seed_v = int(active_style.get("seed", 0) or 0)
    _yh = {"y": y}
    _slider = _local_style_slider(screen, font_small, state, x, _yh)
    _slider("Location", "location", loc_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
    _slider("Handle rotate", "handle_rotate", rot_v, -180.0, 180.0, fmt=lambda v: str(int(round(v))))
    _slider("Handle length", "handle_length", len_v, -100.0, 100.0, fmt=lambda v: str(int(round(v))))
    _slider("Noise scale", "noise_scale", nsc_v, 0.1, 20.0, fmt=lambda v: f"{v:.1f}")
    _slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
    y = _yh["y"]
    screen.blit(font_small.render("Affects selected axes/properties on unbaked nodes (edges fixed).", True, MUTED_COLOR), (x, y)); y += 18
    y += MIN_ELEMENT_SPACING
    return y


def _b2b_disp(c):
    """Compat ctx-bag wrapper; core logic lives in render_displacement_section."""
    if getattr(c, 'style_type', None) == "displacement":
        c.y = render_displacement_section(
            c.screen, c.fonts[1], c.state, c.x, c.y, c._button, c._style_slider, c.active_style,
        )

def render_repeat_section(screen, font_small, state, x, y, _button, _style_slider, active_style):
    """Explicit-contract render for repeat style section."""
    publish_rect(state, "displacement_affect_rects", {})
    publish_rect(state, "wave_shape_prev_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "wave_shape_next_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "wave_shape_rects", {})
    publish_rect(state, "wave_formula_rect", pygame.Rect(0,0,0,0))
    state["wave_formula_focus"] = False
    publish_rect(state, "wave_smooth_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "wave_clear_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "wave_done_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "repeat_pick_curve_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "displacement_profile_rects", {})
    screen.blit(font_small.render("Repeat curve (drawn pattern)", True, TEXT_COLOR), (x, y)); y += 20
    BOX_W = 180; BOX_H = 80
    bx = x + 8; by = y + 8
    box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
    publish_rect(state, "wave_custom_box_rect", box_rect)
    cp = active_style.get("repeat_points", None)
    bg_col = PLOT_BG if (cp and len(cp) >= 2) else PLOT_BG_DISABLED
    pygame.draw.rect(screen, bg_col, box_rect, border_radius=RADIUS_SM)
    pygame.draw.rect(screen, BORDER_STRONG, box_rect, 2, border_radius=RADIUS_SM)
    if cp and len(cp) >= 2:
        prev_px, prev_py = None, None
        for cxp, cyp in cp:
            px = bx + 6 + float(cxp) * (BOX_W - 12)
            py = by + BOX_H//2 + float(cyp) * (BOX_H//2 - 4)
            if prev_px is not None:
                pygame.draw.line(screen, CUSTOM_CURVE_COLOR, (prev_px, prev_py), (int(px), int(py)), BORDER_WIDTH_ACTIVE)
            prev_px, prev_py = int(px), int(py)
    pygame.draw.line(screen, PLOT_GRID, (bx + 6, by + 4), (bx + BOX_W - 6, by + 4), BORDER_WIDTH)
    pygame.draw.line(screen, PLOT_GRID, (bx + 6, by + BOX_H//2), (bx + BOX_W - 6, by + BOX_H//2), 1)
    y += BOX_H + 18
    btns_y = y
    gap = MIN_ELEMENT_SPACING
    bw = (PANEL_W - 40 - gap * 2) // 3
    clr_r = pygame.Rect(x, btns_y, bw, 24)
    smooth_r = pygame.Rect(x + bw + gap, btns_y, bw, 24)
    done_r = pygame.Rect(x + (bw + gap) * 2, btns_y, PANEL_W - 40 - (bw + gap) * 2, 24)
    _button(clr_r, "Clear")
    _button(smooth_r, "Smooth")
    _button(done_r, "Done")
    publish_rect(state, "wave_clear_rect", clr_r)
    publish_rect(state, "wave_smooth_rect", smooth_r)
    publish_rect(state, "wave_done_rect", done_r)
    y += 24 + MIN_ELEMENT_SPACING
    pick_r = pygame.Rect(x, y, PANEL_W - 40, 24)
    picking = bool(state.get("repeat_pick_mode"))
    _button(pick_r, "Picking curve..." if picking else "Copy Curve As Pattern", active=picking)
    publish_rect(state, "repeat_pick_curve_rect", pick_r)
    y += 24 + MIN_ELEMENT_SPACING
    _yh = {"y": y}
    _slider = _local_style_slider(screen, font_small, state, x, _yh)
    _slider("Amplitude (%)", "amplitude", float(active_style.get("amplitude", 8.0)), 0.0, 100.0, fmt=lambda v: f"{v:.1f}")
    _slider("Frequency", "frequency", float(active_style.get("frequency", 0.25)), 0.01, 5.0, fmt=lambda v: f"{v:.2f}")
    _slider("Phase (deg)", "phase", float(active_style.get("phase", 0.0)), 0.0, 360.0, fmt=lambda v: f"{v:.0f}")
    y = _yh["y"]  # each drag field already reserves its own 8px gap
    rev_rect = pygame.Rect(x, y, (PANEL_W - 40 - MIN_ELEMENT_SPACING) // 2, 24)
    clamp_rect = pygame.Rect(rev_rect.right + MIN_ELEMENT_SPACING, y,
                             PANEL_W - 40 - rev_rect.w - MIN_ELEMENT_SPACING, 24)
    _button(rev_rect, "Reverse", active=bool(active_style.get("reverse")))
    publish_rect(state, "wave_reverse_rect", rev_rect)
    _button(clamp_rect, f"Clamp: {active_style.get('clamp','none')}")
    publish_rect(state, "wave_clamp_rect", clamp_rect)
    y += 24 + MIN_ELEMENT_SPACING
    return y


def _b2b_rep(c):
    """Compat ctx-bag wrapper; core logic lives in render_repeat_section."""
    if getattr(c, 'style_type', None) == "repeat":
        c.y = render_repeat_section(
            c.screen, c.fonts[1], c.state, c.x, c.y, c._button, c._style_slider, c.active_style,
        )

def render_thickness_section(screen, font_small, state, x, y, _button, _style_slider, active_style):
    """Explicit-contract render for thickness style section."""
    publish_rect(state, "displacement_affect_rects", {})
    publish_rect(state, "wave_shape_prev_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "wave_shape_next_rect", pygame.Rect(0,0,0,0))
    publish_rect(state, "wave_shape_rects", {})
    publish_rect(state, "wave_formula_rect", pygame.Rect(0,0,0,0))
    state["wave_formula_focus"] = False
    publish_rect(state, "displacement_profile_rects", {})
    screen.blit(font_small.render("Thickness profile (no repetition)", True, TEXT_COLOR), (x, y)); y += 20
    BOX_W = 180; BOX_H = 80
    bx = x + 8; by = y + 8
    box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
    publish_rect(state, "wave_custom_box_rect", box_rect)
    cp = active_style.get("thickness_points", None)
    bg_col = PLOT_BG if (cp and len(cp) >= 2) else PLOT_BG_DISABLED
    pygame.draw.rect(screen, bg_col, box_rect, border_radius=RADIUS_SM)
    pygame.draw.rect(screen, BORDER_STRONG, box_rect, 2, border_radius=RADIUS_SM)
    if cp and len(cp) >= 2:
        prev_px, prev_py = None, None
        for cxp, cyp in cp:
            px = bx + 6 + float(cxp) * (BOX_W - 12)
            py = by + BOX_H//2 + float(cyp) * (BOX_H//2 - 4)
            if prev_px is not None:
                pygame.draw.line(screen, CUSTOM_CURVE_COLOR, (prev_px, prev_py), (int(px), int(py)), BORDER_WIDTH_ACTIVE)
            prev_px, prev_py = int(px), int(py)
    pygame.draw.line(screen, PLOT_GRID, (bx + 6, by + 4), (bx + BOX_W - 6, by + 4), BORDER_WIDTH)
    pygame.draw.line(screen, PLOT_GRID, (bx + 6, by + BOX_H//2), (bx + BOX_W - 6, by + BOX_H//2), 1)
    y += BOX_H + 18
    btns_y = y
    gap = MIN_ELEMENT_SPACING
    bw = (PANEL_W - 40 - gap * 2) // 3
    clr_r = pygame.Rect(x, btns_y, bw, 24)
    smooth_r = pygame.Rect(x + bw + gap, btns_y, bw, 24)
    done_r = pygame.Rect(x + (bw + gap) * 2, btns_y, PANEL_W - 40 - (bw + gap) * 2, 24)
    _button(clr_r, "Clear")
    _button(smooth_r, "Smooth")
    _button(done_r, "Done")
    publish_rect(state, "wave_clear_rect", clr_r)
    publish_rect(state, "wave_smooth_rect", smooth_r)
    publish_rect(state, "wave_done_rect", done_r)
    y += 24 + MIN_ELEMENT_SPACING
    pick_r = pygame.Rect(x, y, PANEL_W - 40, 24)
    picking = bool(state.get("repeat_pick_mode"))
    _button(pick_r, "Picking curve..." if picking else "Copy Curve As Pattern", active=picking)
    publish_rect(state, "repeat_pick_curve_rect", pick_r)
    y += 24 + MIN_ELEMENT_SPACING
    _yh = {"y": y}
    _slider = _local_style_slider(screen, font_small, state, x, _yh)
    _slider("Amplitude (%)", "amplitude", float(active_style.get("amplitude", 8.0)), 0.0, 100.0, fmt=lambda v: f"{v:.1f}")
    y = _yh["y"]  # each drag field already reserves its own 8px gap
    rev_rect = pygame.Rect(x, y, (PANEL_W - 40 - MIN_ELEMENT_SPACING) // 2, 24)
    clamp_rect = pygame.Rect(rev_rect.right + MIN_ELEMENT_SPACING, y,
                             PANEL_W - 40 - rev_rect.w - MIN_ELEMENT_SPACING, 24)
    _button(rev_rect, "Reverse", active=bool(active_style.get("reverse")))
    publish_rect(state, "wave_reverse_rect", rev_rect)
    _button(clamp_rect, f"Clamp: {active_style.get('clamp','none')}")
    publish_rect(state, "wave_clamp_rect", clamp_rect)
    y += 24 + MIN_ELEMENT_SPACING
    return y


def _b2b_thick(c):
    """Compat ctx-bag wrapper; core logic lives in render_thickness_section."""
    if getattr(c, 'style_type', None) == "thickness":
        c.y = render_thickness_section(
            c.screen, c.fonts[1], c.state, c.x, c.y, c._button, c._style_slider, c.active_style,
        )

def render_wave_section(screen, fonts, state, x, y, _button, _queue_tip, _style_slider, active_style, shape='sine', mouse_pos=(0,0)):
    """Explicit-contract render for wave style section."""
    font, font_small, font_title = fonts
    wave = active_style
    publish_rect(state, "displacement_affect_rects", {})
    # Wave style UI (existing behavior)
    wave = active_style
    # ---- shape selector ----
    screen.blit(font_small.render("Shape", True, TEXT_COLOR), (x, y)); y += 20
    shape_items = list(WAVE_SHAPE_LABELS)
    shape_labels = {k: lbl for k, lbl in shape_items}
    cur_shape = shape if shape in shape_labels else shape_items[0][0]
    btn_w = 28
    vw = PANEL_W - 40 - btn_w * 2 - MIN_ELEMENT_SPACING * 2
    pr = pygame.Rect(x, y, btn_w, 28)
    vr = pygame.Rect(x + btn_w + MIN_ELEMENT_SPACING, y, vw, 28)
    nr = pygame.Rect(vr.right + MIN_ELEMENT_SPACING, y, btn_w, 28)
    publish_rect(state, "wave_shape_prev_rect", pr)
    publish_rect(state, "wave_shape_next_rect", nr)
    publish_rect(state, "wave_shape_rects", {})
    _button(pr, "<", font_=font_small)
    # value area with small waveform preview
    _button(vr, "", active=False)
    icon_wave = dict(wave)
    icon_wave["shape"] = cur_shape
    icon_rect = pygame.Rect(vr.x + 6, vr.y + 4, 44, vr.h - 8)
    _draw_wave_graph(screen, icon_rect, _wave_icon_polyline(icon_wave),
                     ACCENT, bg=PLOT_BG, line_w=1)
    lbl_surf = font_small.render(shape_labels.get(cur_shape, cur_shape), True, TEXT_COLOR)
    screen.blit(lbl_surf, (icon_rect.right + 8, vr.centery - lbl_surf.get_height() // 2))
    _button(nr, ">", font_=font_small)
    y += 28 + MIN_ELEMENT_SPACING

    # Formula input (contextual: only for the formula shape)
    publish_rect(state, "wave_formula_rect", pygame.Rect(0,0,0,0))
    if shape == "formula":
        screen.blit(font_small.render("Formula (x=p, t,s)", True, TEXT_COLOR), (x, y)); y += 18
        frect = pygame.Rect(x, y, PANEL_W - 40, 26)
        publish_rect(state, "wave_formula_rect", frect)
        focused = bool(state.get("wave_formula_focus"))
        bg = SURFACE if focused else (BUTTON_HOVER if frect.collidepoint(mouse_pos) else BUTTON_BG)
        pygame.draw.rect(screen, bg, frect, border_radius=RADIUS_MD)
        pygame.draw.rect(screen, ACCENT if focused else BUTTON_BORDER, frect, 2 if focused else 1, border_radius=RADIUS_MD)
        ftxt = str(wave.get("formula", "sin(x)") or "sin(x)")
        if focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            ftxt_disp = ftxt + "|"
        else:
            ftxt_disp = ftxt
        while ftxt_disp and font_small.size(ftxt_disp)[0] > frect.w - 12:
            ftxt_disp = ftxt_disp[1:]
        tt = font_small.render(ftxt_disp, True, TEXT_COLOR)
        screen.blit(tt, (frect.x + 6, frect.y + 5))
        y += 32
    else:
        state["wave_formula_focus"] = False

    # Custom wave drawing mode - dedicated preview box (contextual)
    BOX_W = 180
    BOX_H = 80
    state["wave_custom_draw"] = False
    if shape != "custom":
        state["wave_custom_finished"] = False
    publish_rect(state, "wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
    if shape == "custom":
        bx = x + 8
        by = y + 8
        box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
        publish_rect(state, "wave_custom_box_rect", box_rect)
        cp = wave.get("custom_points", None)
        bg_col = PLOT_BG if (cp and len(cp) >= 2) else PLOT_BG_DISABLED
        pygame.draw.rect(screen, bg_col, box_rect, border_radius=RADIUS_SM)
        pygame.draw.rect(screen, BORDER_STRONG, box_rect, 2, border_radius=RADIUS_SM)
        if cp and len(cp) >= 2:
            prev_px, prev_py = None, None
            for cxp, cyp in cp:
                px = bx + 6 + cxp * (BOX_W - 12)
                py = by + BOX_H//2 + cyp * (BOX_H//2 - 4)
                if prev_px is not None:
                    pygame.draw.line(screen, CUSTOM_CURVE_COLOR, (prev_px, prev_py), (int(px), int(py)), BORDER_WIDTH_ACTIVE)
                prev_px, prev_py = int(px), int(py)
            if len(cp) > 2:
                pygame.draw.line(screen, CUSTOM_CURVE_COLOR, (int(prev_px), int(prev_py)), (int(bx+6), int(by+BOX_H//2)), BORDER_WIDTH)
        pygame.draw.line(screen, PLOT_GRID, (bx + 6, by + 4), (bx + BOX_W - 6, by + 4), BORDER_WIDTH)
        pygame.draw.line(screen, PLOT_GRID, (bx + 6, by + BOX_H - 4), (bx + BOX_W - 6, by + BOX_H - 4), BORDER_WIDTH)
        has_wave_pts = bool(cp and len(cp) >= 2)
        smooth_rect = pygame.Rect(bx, by + BOX_H + MIN_ELEMENT_SPACING, 74, 20)
        publish_rect(state, "wave_smooth_rect", smooth_rect)
        _button(smooth_rect, "Smooth", enabled=has_wave_pts)
        if has_wave_pts:
            pt_count = f"{len(cp)} samples"
        else:
            pt_count = "hold & drag to draw"
        instr = font_small.render(f"Custom: {pt_count}", True, TEXT_DISABLED)
        screen.blit(instr, (smooth_rect.right + 8, smooth_rect.y + 3))
        finish_instr = font_small.render("Esc to finish", True, TEXT_DISABLED)
        screen.blit(finish_instr, (smooth_rect.right + 8, smooth_rect.y + 18))
        y = by + BOX_H + MIN_ELEMENT_SPACING + 20 + MIN_ELEMENT_SPACING
        state["wave_custom_draw"] = not bool(state.get("wave_custom_finished", False))

    screen.blit(font_small.render("Parameters", True, TEXT_COLOR), (x, y)); y += 20
    amp_v = float(wave.get("amplitude", 0.0))
    freq_v = float(wave.get("frequency", 0.0))
    phase_v = float(wave.get("phase", 0.0))
    noise_v = float(wave.get("noise", 0.0))
    seed_v = int(wave.get("seed", 0) or 0)
    nscale_v = float(wave.get("noise_scale", 2.0))
    noise_on = abs(noise_v) > 1e-6
    _yh = {"y": y}
    _slider = _local_style_slider(screen, font_small, state, x, _yh)
    _slider("Amplitude", "amplitude", amp_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
    _slider("Frequency", "frequency", freq_v, 0.01, 1.0, fmt=lambda v: f"{v:.2f}")
    if shape == "noise":
        _slider("Phase", "phase", phase_v, 0.0, 360.0, fmt=lambda v: str(int(round(v))), enabled_sl=False)
        _slider("Noise scale", "noise_scale", nscale_v, 0.2, 10.0, fmt=lambda v: f"{v:.1f}")
        _slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
    else:
        _slider("Phase", "phase", phase_v, 0.0, 360.0, fmt=lambda v: str(int(round(v))))
        if noise_on:
            _slider("Noise", "noise", noise_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
            _slider("Noise scale", "noise_scale", nscale_v, 0.2, 10.0, fmt=lambda v: f"{v:.1f}")
            _slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
    y = _yh["y"]  # each drag field already reserves its own 8px gap
    # Reverse toggle: invert the wave (-f(x))
    rev = bool(wave.get("reverse"))
    rev_rect = pygame.Rect(x, y, PANEL_W - 40, 22)
    publish_rect(state, "wave_reverse_rect", rev_rect)
    _button(rev_rect, f"Reverse wave -f(x): {'ON' if rev else 'OFF'}", active=rev)
    y += 22 + MIN_ELEMENT_SPACING
    # Clamp: apply the curve on only one side or the other
    clamp_mode = str(wave.get("clamp", "none") or "none").lower()
    if clamp_mode not in ("none", "positive", "negative"):
        clamp_mode = "none"
    clamp_labels = {"none": "Off", "positive": "One side (+)", "negative": "One side (-)"}
    clamp_rect = pygame.Rect(x, y, PANEL_W - 40, 22)
    publish_rect(state, "wave_clamp_rect", clamp_rect)
    _button(clamp_rect, f"Clamp curve: {clamp_labels[clamp_mode]}",
            active=clamp_mode != "none")
    y += 22 + MIN_ELEMENT_SPACING
    y += MIN_ELEMENT_SPACING

    return y


def _b2b_wave(c):
    """Compat ctx-bag wrapper; core logic lives in render_wave_section."""
    c.y = render_wave_section(
        c.screen, c.fonts, c.state, c.x, c.y, c._button, getattr(c, '_queue_tip', None),
        c._style_slider, c.active_style, getattr(c, 'shape', 'sine'), getattr(c, 'mouse_pos', (0, 0)),
    )
