"""View: panel_select split parts C/D (SRP)."""
"""View: panel section (split for complexity)."""
import math
import pygame
import config as cfg
from config import *
from views.panel_select_parts import _draw_wave_graph, _value_ramp, _sv_surface, _hue_bar_surface
from controllers.coordinates import clamp
from models.geometry import color_alpha, color_rgb, color_rgba
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
    try:
        _ctypes.pythonapi.PyFrame_LocalsToFast(_ctypes.py_object(f), 0)
    except Exception:
        pass

def _sync_out(c, _f=None):
    f = _f or _sys._getframe(1)
    try:
        _ctypes.pythonapi.PyFrame_FastToLocals(_ctypes.py_object(f))
    except Exception:
        pass
    d = dict(f.f_locals)
    d.pop('c', None)
    c.__dict__.update(d)


BOOL_KEYS = ("bool_union_rect", "bool_intersect_rect", "bool_subtract_rect", "bool_exclude_rect")
_xform_keys = ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
               "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
               "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
               "xform_rm_rect", "xform_rp_rect")
DIST_KEYS = ("distribute_h_rect", "distribute_v_rect")
PATH_KEYS = ("path_close_rect", "path_reverse_rect", "path_add_rect",
             "path_delete_rect", "path_smooth_rect", "path_corner_rect", "path_expand_rect")
APPEAR_KEYS = ("obj_opacity_rect", "shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")


def render_color_tail_section(
    screen, fonts, mouse_pos, state, x, y, _button, _queue_tip, help_lines,
    sel_strokes, sel_count, submode, sel_stroke,
    stroke_color_enabled=True, fill_enabled=True,
    component_stroke_enabled=False, shape_style_enabled=True,
    color_target='stroke', has_fill_now=False,
    comp_style_target=None, stroke=None,
    fill_pat=None, fill_grad=None, cur_color=None, display_color=None,
    ph=0.0, ps=0.0, pv=0.0,
):
    """Explicit-contract render for color picker tail (nofill, fill type, SV/hue/alpha, swatches, stats)."""
    font, font_small, _font_title = fonts

    # No fill button
    if color_target == "fill":
        nofill = pygame.Rect(x + 150, y + 4, 70, 26)
        state["nofill_rect"] = nofill
        nf_active = not has_fill_now
        _button(nofill, "No fill", active=nf_active)
    else:
        state["nofill_rect"] = pygame.Rect(0, 0, 0, 0)
    y += 40
    # Fill type + gradient stop controls
    for _k in ("fill_type_prev_rect", "fill_type_next_rect"):
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    state.setdefault("fill_stop_rects", {})
    state.setdefault("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0))
    state.setdefault("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0))
    state.setdefault("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
    if color_target == "fill":
        fill_mode = "none"
        if fill_pat is not None:
            fill_mode = "pattern"
        elif fill_grad is not None:
            fill_mode = str(fill_grad.get("type", "linear"))
        elif stroke is not None and stroke.get("fill_color") is not None:
            fill_mode = "solid"
        fill_labels = {
            "none": "None", "solid": "Solid", "linear": "Linear", "radial": "Radial",
            "conic": "Conic", "spiral": "Spiral", "diamond": "Diamond", "square": "Square",
            "mesh": "Mesh", "pattern": "Pattern",
        }
        screen.blit(font_small.render("Fill type", True, MUTED_COLOR), (x, y + 4))
        btn_w = 28
        vx = x + 62
        vw = PANEL_W - 40 - 62 - btn_w * 2 - 8
        pr = pygame.Rect(vx, y, btn_w, 24)
        vr = pygame.Rect(vx + btn_w + 4, y, vw, 24)
        nr = pygame.Rect(vr.right + 4, y, btn_w, 24)
        state["fill_type_prev_rect"] = pr
        state["fill_type_next_rect"] = nr
        _button(pr, "<", font_=font_small)
        _button(vr, fill_labels.get(fill_mode, str(fill_mode).title()))
        _button(nr, ">", font_=font_small)
        y += 30
        # pattern controls: cycle motif and adjust tile size
        for _pk in ("pattern_type_rect", "pattern_size_minus_rect", "pattern_size_plus_rect"):
            state.setdefault(_pk, pygame.Rect(0, 0, 0, 0))
        if fill_pat is not None:
            _avail = PANEL_W - 40
            _mrow = pygame.Rect(x, y, _avail - 60, 24)
            state["pattern_type_rect"] = _mrow
            _button(_mrow, f"Motif: {str(fill_pat.get('type', 'stripes')).title()}")
            _smr = pygame.Rect(x + _avail - 56, y, 26, 24)
            _spr = pygame.Rect(x + _avail - 28, y, 26, 24)
            state["pattern_size_minus_rect"] = _smr
            state["pattern_size_plus_rect"] = _spr
            _button(_smr, "-", font_=font_small)
            _button(_spr, "+", font_=font_small)
            y += 28
            _sz = font_small.render(f"Tile: {int(round(float(fill_pat.get('size', 14))))} px", True, MUTED_COLOR)
            screen.blit(_sz, (x, y)); y += 18
        else:
            for _pk in ("pattern_type_rect", "pattern_size_minus_rect", "pattern_size_plus_rect"):
                state[_pk] = pygame.Rect(0, 0, 0, 0)
        # gradient stops (multi-stop) - not applicable to mesh gradients
        state["fill_stop_rects"] = {}
        state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
        if fill_grad is not None and str(fill_grad.get("type", "")) != "mesh":
            _get_stops = globals().get("get_gradient_stops")
            if callable(_get_stops):
                try:
                    stops = _get_stops(fill_grad) or []
                except Exception:
                    stops = list(fill_grad.get("stops") or [])
            else:
                stops = list(fill_grad.get("stops") or [])
            if not stops:
                stops = [{"pos": 0.0, "color": [0.0, 0.0, 0.0, 1.0]},
                         {"pos": 1.0, "color": [1.0, 1.0, 1.0, 1.0]}]
            nstops = len(stops)
            try:
                fill_grad_stop = int(state.get("fill_gradient_stop", 0) or 0)
            except Exception:
                fill_grad_stop = 0
            fill_grad_stop = max(0, min(fill_grad_stop, nstops - 1))
            state["fill_gradient_stop"] = fill_grad_stop

            avail_w = PANEL_W - 40
            btn_w = 22
            gap = 6
            sw_area_w = max(60, avail_w - 2 * (btn_w + gap))
            # Choose swatch size/gap so all stops remain visible and individually clickable.
            sw_gap = 6
            if nstops > 1:
                sw = int((sw_area_w - (nstops - 1) * sw_gap) / nstops)
            else:
                sw = 26
            if sw < 18:
                sw_gap = 4
                sw = int((sw_area_w - (nstops - 1) * sw_gap) / max(1, nstops))
            if sw < 14:
                sw_gap = 2
                sw = int((sw_area_w - (nstops - 1) * sw_gap) / max(1, nstops))
            sw = max(12, min(26, sw))
            total_sw_w = nstops * sw + max(0, nstops - 1) * sw_gap
            start_x = x
            if total_sw_w > sw_area_w and nstops > 1:
                # Compress spacing as a last resort to avoid overlapping hit targets.
                sw_gap = max(1, int((sw_area_w - nstops * sw) / (nstops - 1)))
                total_sw_w = nstops * sw + max(0, nstops - 1) * sw_gap
            if total_sw_w < sw_area_w:
                start_x = x  # left-align; keeps layout stable
            for i in range(nstops):
                r = pygame.Rect(start_x + i * (sw + sw_gap), y, sw, sw)
                # Keep within swatch area without stacking on top of another stop.
                if r.right > x + sw_area_w:
                    r.x = x + sw_area_w - sw
                state["fill_stop_rects"][str(i)] = r
                st = stops[i]
                if isinstance(st, dict):
                    cstop = color_rgba(st.get("color"), (0, 0, 0, 1))
                else:
                    try:
                        cstop = color_rgba(st[1], (0, 0, 0, 1))
                    except Exception:
                        cstop = (0.0, 0.0, 0.0, 1.0)
                draw_swatch(screen, r, cstop, i == fill_grad_stop, mouse_pos)
            bx = x + sw_area_w + gap
            add_r = pygame.Rect(bx, y, btn_w, sw)
            rem_r = pygame.Rect(bx + btn_w + 4, y, btn_w, sw)
            state["fill_stop_add_rect"] = add_r
            state["fill_stop_remove_rect"] = rem_r
            for r, label, enabled_btn in ((add_r, "+", True), (rem_r, "-", nstops > 2)):
                _button(r, label, enabled=enabled_btn)
            y += sw + 6

            # selected stop position (distance)
            sel_st = stops[fill_grad_stop] if 0 <= fill_grad_stop < nstops else stops[0]
            try:
                sel_pos = float((sel_st or {}).get("pos", 0.0)) if isinstance(sel_st, dict) else float(sel_st[0])
            except Exception:
                sel_pos = 0.0
            sel_pos = clamp(sel_pos, 0.0, 1.0)
            pos_label = font_small.render(f"Stop {fill_grad_stop + 1}  Pos {int(round(sel_pos * 100))}%", True, TEXT_COLOR)
            screen.blit(pos_label, (x, y))
            y += 16
            pos_h = 10
            pos_rect = pygame.Rect(x, y, PANEL_W - 40, pos_h)
            state["fill_stop_pos_rect"] = pos_rect
            for ix in range(pos_rect.w):
                tt = ix / max(1, pos_rect.w - 1)
                samp = SAMPLE_PLACEHOLDER
                try:
                    ordered = []
                    for s in stops:
                        if isinstance(s, dict):
                            ordered.append((float(s.get("pos", 0.0)), color_rgba(s.get("color"), (0, 0, 0, 1))))
                        else:
                            try:
                                ordered.append((float(s[0]), color_rgba(s[1], (0, 0, 0, 1))))
                            except Exception:
                                pass
                    ordered.sort(key=lambda t: t[0])
                    if ordered:
                        if tt <= ordered[0][0]:
                            sc = ordered[0][1]
                        elif tt >= ordered[-1][0]:
                            sc = ordered[-1][1]
                        else:
                            sc = ordered[-1][1]
                            for a, b in zip(ordered, ordered[1:]):
                                pa, ca = a; pb, cb = b
                                if pa <= tt <= pb:
                                    lt = 0.0 if pb - pa <= 1e-9 else (tt - pa) / (pb - pa)
                                    sc = tuple(ca[k] + (cb[k] - ca[k]) * lt for k in range(4))
                                    break
                        bgv = 235 if (ix // 6) % 2 == 0 else 210
                        a = float(sc[3]) if len(sc) >= 4 else 1.0
                        samp = (int((sc[0] * a + (bgv / 255.0) * (1 - a)) * 255),
                                int((sc[1] * a + (bgv / 255.0) * (1 - a)) * 255),
                                int((sc[2] * a + (bgv / 255.0) * (1 - a)) * 255))
                except Exception:
                    pass
                pygame.draw.line(screen, samp, (pos_rect.x + ix, pos_rect.y), (pos_rect.x + ix, pos_rect.bottom - 1))
            pygame.draw.rect(screen, BUTTON_BORDER, pos_rect, 1, border_radius=RADIUS_SM)
            # Draw markers for all stops so unselected stop colors/positions remain visible.
            for i, st in enumerate(stops):
                try:
                    sp = float((st or {}).get("pos", 0.0)) if isinstance(st, dict) else float(st[0])
                except Exception:
                    sp = 0.0
                sp = clamp(sp, 0.0, 1.0)
                if isinstance(st, dict):
                    scol = color_rgba(st.get("color"), (0, 0, 0, 1))
                else:
                    try:
                        scol = color_rgba(st[1], (0, 0, 0, 1))
                    except Exception:
                        scol = (0.0, 0.0, 0.0, 1.0)
                sx = pos_rect.x + int(sp * (pos_rect.w - 1))
                if i == fill_grad_stop:
                    pygame.draw.rect(screen, SURFACE, (sx - 3, pos_rect.y - 2, 6, pos_rect.h + 4), 2, border_radius=RADIUS_XS)
                    pygame.draw.rect(screen, HANDLE_OUTLINE, (sx - 3, pos_rect.y - 2, 6, pos_rect.h + 4), 1, border_radius=RADIUS_XS)
                else:
                    mr = pygame.Rect(sx - 3, pos_rect.y - 1, 6, pos_rect.h + 2)
                    # show the stop's own color on the marker for visibility
                    sr, sg, sb = [int(clamp(c, 0.0, 1.0) * 255) for c in scol[:3]]
                    pygame.draw.rect(screen, (sr, sg, sb), mr, border_radius=RADIUS_XS)
                    pygame.draw.rect(screen, SURFACE, mr, 1, border_radius=RADIUS_XS)
                    pygame.draw.rect(screen, BORDER_STRONG, mr.inflate(2, 2), BORDER_WIDTH, border_radius=RADIUS_XS)
            y += pos_h + 8
        else:
            state["fill_stop_rects"] = {}
            state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
            state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
            state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
    else:
        state["fill_type_prev_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_type_next_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_rects"] = {}
        state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)

    # SV square
    sv_w = PANEL_W - 40
    sv_h = 110
    sv_rect = pygame.Rect(x, y, sv_w, sv_h)
    state["sv_rect"] = sv_rect
    # draw SV gradient for current hue
    screen.blit(_sv_surface(ph, sv_w, sv_h), sv_rect.topleft)
    pygame.draw.rect(screen, BUTTON_BORDER, sv_rect, 1, border_radius=RADIUS_SM)
    # SV cursor
    cxp = sv_rect.x + int(ps * (sv_w - 1))
    cyp = sv_rect.y + int((1.0 - pv) * (sv_h - 1))
    draw_picker_cursor(screen, (cxp, cyp))
    y += sv_h + 8

    # Hue bar
    hue_h = 14
    hue_rect = pygame.Rect(x, y, sv_w, hue_h)
    state["hue_rect"] = hue_rect
    screen.blit(_hue_bar_surface(sv_w, hue_h), hue_rect.topleft)
    pygame.draw.rect(screen, BUTTON_BORDER, hue_rect, 1, border_radius=RADIUS_SM)
    hx = hue_rect.x + int((ph / 360.0) * (sv_w - 1))
    draw_hue_cursor(screen, hx, hue_rect)
    y += hue_h + 8

    # Alpha / opacity slider (stroke always; fill only when a fill color exists)
    show_alpha = (color_target == "stroke") or (cur_color is not None)
    state["alpha_rect"] = pygame.Rect(0, 0, 0, 0)
    if show_alpha:
        cur_alpha = color_alpha(cur_color, 1.0)
        screen.blit(font_small.render(f"Opacity {int(round(cur_alpha * 100))}%", True, TEXT_COLOR), (x, y))
        y += 16
        alpha_h = 12
        alpha_rect = pygame.Rect(x, y, sv_w, alpha_h)
        state["alpha_rect"] = alpha_rect
        # simple gradient bar from transparent to current rgb
        base_rgb = color_rgb(display_color, (1.0, 1.0, 1.0))
        for ix in range(sv_w):
            a = ix / max(1, sv_w - 1)
            # blend over a light checker-like background approximation
            bgv = 235 if (ix // 6) % 2 == 0 else 210
            r = int((base_rgb[0] * a + (bgv / 255.0) * (1 - a)) * 255)
            g = int((base_rgb[1] * a + (bgv / 255.0) * (1 - a)) * 255)
            b = int((base_rgb[2] * a + (bgv / 255.0) * (1 - a)) * 255)
            pygame.draw.line(screen, (r, g, b), (alpha_rect.x + ix, alpha_rect.y), (alpha_rect.x + ix, alpha_rect.y + alpha_h - 1))
        pygame.draw.rect(screen, BUTTON_BORDER, alpha_rect, 1, border_radius=RADIUS_SM)
        ax = alpha_rect.x + int(clamp(cur_alpha, 0.0, 1.0) * (sv_w - 1))
        pygame.draw.rect(screen, SURFACE, (ax - 3, alpha_rect.y - 2, 6, alpha_h + 4), 2, border_radius=RADIUS_XS)
        pygame.draw.rect(screen, HANDLE_OUTLINE, (ax - 3, alpha_rect.y - 2, 6, alpha_h + 4), 1, border_radius=RADIUS_XS)
        y += alpha_h + 8
    else:
        y += 2

    # Preset swatches
    presets = STROKE_SWATCHES
    sw = 26
    state["stroke_swatch_rects"] = [pygame.Rect(0, 0, 0, 0) for _ in presets]
    state["fill_swatch_rects"] = [pygame.Rect(0, 0, 0, 0) for _ in presets]
    for i, col in enumerate(presets):
        r = pygame.Rect(x + i * (sw + 6), y, sw, sw)
        if color_target == "stroke":
            state["stroke_swatch_rects"][i] = r
        else:
            state["fill_swatch_rects"][i] = r
        sel_match = (cur_color == col) if cur_color is not None else False
        draw_swatch(screen, r, col, sel_match, mouse_pos)
    y += sw + 10

    # Disable non-applicable style controls
    if not fill_enabled:
        state["tab_fill_rect"] = pygame.Rect(0, 0, 0, 0)
        state["nofill_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_type_rects"] = {}
        state["fill_stop_rects"] = {}
        state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
        if not stroke_color_enabled:
            state["tab_stroke_rect"] = pygame.Rect(0, 0, 0, 0)
    if not (stroke_color_enabled or fill_enabled):
        state["sv_rect"] = pygame.Rect(0, 0, 0, 0)
        state["hue_rect"] = pygame.Rect(0, 0, 0, 0)
        state["alpha_rect"] = pygame.Rect(0, 0, 0, 0)
        state["stroke_swatch_rects"] = [pygame.Rect(0, 0, 0, 0) for _ in STROKE_SWATCHES]
        state["fill_swatch_rects"] = [pygame.Rect(0, 0, 0, 0) for _ in STROKE_SWATCHES]
        state["fill_type_rects"] = {}
        state["fill_stop_rects"] = {}
        state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
    elif component_stroke_enabled and not fill_enabled:
        # only stroke color editable for selected curve; fill swatches/controls off
        state["fill_swatch_rects"] = [pygame.Rect(0, 0, 0, 0) for _ in STROKE_SWATCHES]
        state["fill_type_rects"] = {}
        state["fill_stop_rects"] = {}
        state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
        state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
    state["component_style_target"] = comp_style_target if component_stroke_enabled else None

    sel_label = "-" if sel_count == 0 else (str(next(iter(sel_strokes)) + 1) if sel_count == 1 else f"{sel_count}")
    stats = font_small.render(f"Strokes: {state['stroke_count']} | Selected: {sel_label}", True, MUTED_COLOR)
    screen.blit(stats, (x, y)); y += 20
    submode = state.get("selection_submode", "transform")
    return {"y": y, "help_lines": help_lines, "sel_stroke": sel_stroke, "submode": submode}


def _part_c2_tail(c):
    """Compat ctx-bag wrapper; core logic lives in render_color_tail_section."""
    _sync_in(c)
    out = render_color_tail_section(
        c.screen, c.fonts, c.mouse_pos, c.state, c.x, c.y, c._button, c._queue_tip, c.help_lines,
        c.sel_strokes, c.sel_count, c.submode, c.sel_stroke,
        getattr(c, 'stroke_color_enabled', True), getattr(c, 'fill_enabled', True),
        getattr(c, 'component_stroke_enabled', False), getattr(c, 'shape_style_enabled', True),
        getattr(c, 'color_target', 'stroke'), getattr(c, 'has_fill_now', False),
        getattr(c, 'comp_style_target', None), getattr(c, 'stroke', None),
        getattr(c, 'fill_pat', None), getattr(c, 'fill_grad', None),
        getattr(c, 'cur_color', None), getattr(c, 'display_color', None),
        getattr(c, 'ph', 0.0), getattr(c, 'ps', 0.0), getattr(c, 'pv', 0.0),
    )
    _sync_out(c)
    if isinstance(out, dict):
        for k, v in out.items():
            setattr(c, k, v)
