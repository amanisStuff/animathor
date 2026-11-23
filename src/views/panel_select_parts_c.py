"""View: panel_select split parts C/D (SRP)."""
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


def _part_c(c):
    _sync_in(c)
    screen=c.screen; fonts=c.fonts; mouse_pos=c.mouse_pos; state=c.state; x=c.x; y=c.y
    _button=c._button; _queue_tip=c._queue_tip; help_lines=c.help_lines
    font, font_small, font_title = fonts
    sel_strokes=c.sel_strokes; sel_count=c.sel_count; submode=c.submode; sel_stroke=c.sel_stroke
    if sel_count == 0:
        info = font_small.render("Select a stroke", True, MUTED_COLOR)
        screen.blit(info, (x, y)); y += 28
        # clear style control rects
        state["tab_stroke_rect"] = pygame.Rect(0,0,0,0)
        state["tab_fill_rect"] = pygame.Rect(0,0,0,0)
        state["sv_rect"] = pygame.Rect(0,0,0,0)
        state["hue_rect"] = pygame.Rect(0,0,0,0)
        state["nofill_rect"] = pygame.Rect(0,0,0,0)
        state["alpha_rect"] = pygame.Rect(0,0,0,0)
        state["width_profile_rects"] = {}
        for i in range(len(state["stroke_swatch_rects"])): state["stroke_swatch_rects"][i] = pygame.Rect(0,0,0,0)
        for i in range(len(state["fill_swatch_rects"])): state["fill_swatch_rects"][i] = pygame.Rect(0,0,0,0)
        c.y=y; c.help_lines=help_lines; c.sel_stroke=sel_stroke; c.submode=submode
        c.sel_count=sel_count; c.sel_strokes=sel_strokes
        _sync_out(c)
    else:
        _sync_out(c)
        _part_c2(c)
        _sync_in(c)
    _sync_out(c)


def _part_c2(c):
    _sync_in(c)
    screen=c.screen; fonts=c.fonts; mouse_pos=c.mouse_pos; state=c.state; x=c.x; y=c.y
    _button=c._button; _queue_tip=c._queue_tip; help_lines=c.help_lines
    font, font_small, font_title = fonts
    sel_strokes=c.sel_strokes; sel_count=c.sel_count; submode=c.submode; sel_stroke=c.sel_stroke

    stroke_color_enabled=getattr(c,'stroke_color_enabled',True)
    fill_enabled=getattr(c,'fill_enabled',True)
    component_stroke_enabled=getattr(c,'component_stroke_enabled',False)
    point_width_enabled=getattr(c,'point_width_enabled',False)
    width_enabled=getattr(c,'width_enabled',False)
    shape_style_enabled=getattr(c,'shape_style_enabled',True)
    color_target=getattr(c,'color_target','stroke')
    has_fill_now=getattr(c,'has_fill_now',False)
    comp_style_target=getattr(c,'comp_style_target',None)
    point_style_target=getattr(c,'point_style_target',None)
    stroke=getattr(c,'stroke',None)
    eff_sc=getattr(c,'eff_sc',None)
    eff_sw=getattr(c,'eff_sw',None)
    fill_pat=getattr(c,'fill_pat',None)
    fill_grad=getattr(c,'fill_grad',None)
    cur_color=getattr(c,'cur_color',None)
    h=getattr(c,'h',0); s=getattr(c,'s',0); vcol=getattr(c,'vcol',0)
    fill_color=getattr(c,'fill_color',None)
    display_color=getattr(c,'display_color',None)
    sv_w=getattr(c,'sv_w',180); sv_h=getattr(c,'sv_h',180)
    ph=getattr(c,'ph',0); ps=getattr(c,'ps',0); pv=getattr(c,'pv',0); sv=getattr(c,'sv',0); hue=getattr(c,'hue',0)
    picker_h=getattr(c,'picker_h',0); picker_s=getattr(c,'picker_s',0); picker_v=getattr(c,'picker_v',0)
    grad=getattr(c,'grad',None); stops=getattr(c,'stops',None); stop_idx=getattr(c,'stop_idx',0)

    stroke = sel_stroke if sel_stroke is not None else state.get("selected_obj")
    if sel_count > 1:
        screen.blit(font_small.render(f"Multiple selected ({sel_count})", True, MUTED_COLOR), (x, y)); y += 20

    comp_style_target = None
    point_style_target = None
    if submode == "curve" and sel_count == 1 and state.get("selected_curve") and stroke is not None:
        scv = state.get("selected_curve")
        if scv and scv[0] in sel_strokes:
            comp_style_target = scv[1]
    if submode == "nodes" and sel_count == 1 and stroke is not None:
        sp = state.get("selected_point")
        if sp and sp[1] in ("p0", "p3"):
            point_style_target = sp  # (seg_i, anchor_name)
    shape_style_enabled = (submode == "transform")
    component_stroke_enabled = (comp_style_target is not None)
    point_width_enabled = (point_style_target is not None)
    width_enabled = shape_style_enabled or component_stroke_enabled or point_width_enabled
    stroke_color_enabled = shape_style_enabled or component_stroke_enabled
    fill_enabled = shape_style_enabled
    if component_stroke_enabled and state.get("color_target") == "fill":
        # fill can't apply to individual curve stroke
        state["color_target"] = "stroke"
    color_target = state.get("color_target", "stroke")
    state["style_controls_enabled"] = shape_style_enabled  # shape-level color picker (fill etc.)

    # effective values for display/controls
    eff_sw = stroke.get("stroke_width", 3.0) if stroke else 3.0
    eff_sc = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if stroke else (0.1, 0.1, 0.15)
    if component_stroke_enabled and stroke is not None:
        eff_sc, eff_sw = _effective_component_style(stroke, comp_style_target)
    elif point_width_enabled and stroke is not None:
        seg_i, an = point_style_target
        pw = get_point_width(stroke, seg_i, an)
        if pw is None:
            # fallback to segment endpoint/component width
            ws, we = _segment_endpoint_widths(stroke, seg_i)
            pw = ws if an == "p0" else we
        eff_sw = float(pw)
    state["point_style_target"] = point_style_target if point_width_enabled else None

    # Stroke width
    screen.blit(font.render("Stroke width", True, TEXT_COLOR if width_enabled else MUTED_COLOR), (x, y)); y += 22
    wv = font_title.render(str(int(round(eff_sw))), True, ACCENT if width_enabled else MUTED_COLOR)
    screen.blit(wv, (x, y - 2)); y += 30
    state["width_slider"].track.topleft = (x, y)
    state["width_slider"].track.width = PANEL_W - 40
    state["width_slider"].value = int(round(clamp(eff_sw, state["width_slider"].min_v, state["width_slider"].max_v)))
    state["width_slider"].draw(screen)
    y += 20
    algo_label = next((lbl for k, lbl in TRACE_ALGORITHMS if k == stroke.get("algorithm", "fit")), stroke.get("algorithm", "fit"))
    if sel_count == 1:
        screen.blit(font_small.render(f"Tracing: {algo_label}", True, MUTED_COLOR), (x, y)); y += 20
    else:
        y += 4

    # Width profile / taper (variable width along path), shape-level.
    for _k in ("width_profile_prev_rect", "width_profile_next_rect"):
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    if shape_style_enabled and stroke is not None and 'WIDTH_PROFILES' in globals():
        profiles = [p for p in WIDTH_PROFILES]
        labels = {
            "uniform": "Uniform",
            "taper_in": "Taper in",
            "taper_out": "Taper out",
            "taper_both": "Taper both",
            "pressure": "Pressure",
        }
        cur_prof = stroke.get("width_profile")
        if cur_prof not in profiles:
            cur_prof = "uniform" if not stroke.get("point_widths") else "uniform"
        screen.blit(font_small.render("Width profile", True, MUTED_COLOR), (x, y + 4))
        btn_w = 28
        vx = x + 92
        vw = PANEL_W - 40 - 92 - btn_w * 2 - 8
        pr = pygame.Rect(vx, y, btn_w, 24)
        vr = pygame.Rect(vx + btn_w + 4, y, vw, 24)
        nr = pygame.Rect(vr.right + 4, y, btn_w, 24)
        state["width_profile_prev_rect"] = pr
        state["width_profile_next_rect"] = nr
        _button(pr, "<", font_=font_small)
        _button(vr, labels.get(cur_prof, str(cur_prof)))
        _button(nr, ">", font_=font_small)
        y += 28
    else:
        state["width_profile_prev_rect"] = pygame.Rect(0, 0, 0, 0)
        state["width_profile_next_rect"] = pygame.Rect(0, 0, 0, 0)

    # Cap / join / dash / miter: all shape-level stroke styling.
    STYLE_STEP_KEYS = ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
                       "dash_prev_rect", "dash_next_rect")
    for _k in STYLE_STEP_KEYS:
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    if shape_style_enabled and stroke is not None:
        cap_now = stroke.get("line_cap", "round")
        join_now = stroke.get("line_join", "round")
        dash_now = stroke.get("dash") or "solid"
        def _style_stepper(label, value, prev_key, next_key):
            nonlocal y
            screen.blit(font_small.render(label, True, MUTED_COLOR), (x, y + 4))
            btn_w = 28
            vx = x + 52
            vw = PANEL_W - 40 - 52 - btn_w * 2 - 8
            pr = pygame.Rect(vx, y, btn_w, 24)
            vr = pygame.Rect(vx + btn_w + 4, y, vw, 24)
            nr = pygame.Rect(vr.right + 4, y, btn_w, 24)
            state[prev_key] = pr; state[next_key] = nr
            _button(pr, "<", font_=font_small)
            _button(vr, value)
            _button(nr, ">", font_=font_small)
            y += 28
        _style_stepper("Cap", str(cap_now).title(), "cap_prev_rect", "cap_next_rect")
        _style_stepper("Join", str(join_now).title(), "join_prev_rect", "join_next_rect")
        _style_stepper("Dash", str(dash_now).title(), "dash_prev_rect", "dash_next_rect")
        if join_now == "miter":
            screen.blit(font_small.render(
                f"Miter limit: {float(stroke.get('miter_limit', 10.0)):g}",
                True, MUTED_COLOR), (x, y)); y += 18
    else:
        for _k in STYLE_STEP_KEYS:
            state[_k] = pygame.Rect(0, 0, 0, 0)

    # Arrowheads / end markers (open paths only).
    for _k in ("marker_start_rect", "marker_end_rect"):
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    if shape_style_enabled and stroke is not None:
        _mk = get_markers(stroke) if 'get_markers' in globals() else {"start": "none", "end": "none"}
        screen.blit(font_small.render("Markers", True, TEXT_COLOR), (x, y)); y += 18
        _mgap = 4
        _mbw = (PANEL_W - 40 - _mgap) // 2
        _sr = pygame.Rect(x, y, _mbw, 24)
        _er = pygame.Rect(x + _mbw + _mgap, y, _mbw, 24)
        state["marker_start_rect"] = _sr
        state["marker_end_rect"] = _er
        open_start = (state.get("marker_dropdown") == "start")
        open_end = (state.get("marker_dropdown") == "end")
        _button(_sr, "Start: " + str(_mk["start"]).replace("_", " ").title(),
                active=open_start, show_caret=True)
        _button(_er, "End: " + str(_mk["end"]).replace("_", " ").title(),
                active=open_end, show_caret=True)
        y += 28
        if stroke_is_closed(stroke):
            hint = font_small.render("Closed paths have no marker ends", True, MUTED_COLOR)
            screen.blit(hint, (x, y)); y += 18
    else:
        state["marker_start_rect"] = pygame.Rect(0, 0, 0, 0)
        state["marker_end_rect"] = pygame.Rect(0, 0, 0, 0)

    # Appearance: object opacity and drop shadow.
    APPEAR_KEYS = ("obj_opacity_rect", "shadow_toggle_rect",
                   "shadow_blur_minus_rect", "shadow_blur_plus_rect")
    for _k in APPEAR_KEYS:
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    if shape_style_enabled and stroke is not None:
        _app = get_appearance(stroke)
        screen.blit(font_small.render("Appearance", True, TEXT_COLOR), (x, y)); y += 18
        # Object opacity slider.
        screen.blit(font_small.render(
            f"Opacity {int(round(_app['opacity'] * 100))}%", True, MUTED_COLOR), (x, y))
        y += 16
        op_h = 12
        op_rect = pygame.Rect(x, y, PANEL_W - 40, op_h)
        state["obj_opacity_rect"] = op_rect
        pygame.draw.rect(screen, BUTTON_BORDER, op_rect, 1, border_radius=RADIUS_SM)
        fill_w = int(op_rect.w * clamp(_app["opacity"], 0.0, 1.0))
        if fill_w > 0:
            pygame.draw.rect(screen, ACCENT,
                             pygame.Rect(op_rect.x, op_rect.y, fill_w, op_h),
                             border_radius=RADIUS_XS)
        knock = op_rect.x + fill_w
        pygame.draw.rect(screen, HANDLE_OUTLINE,
                         pygame.Rect(knock - 2, op_rect.y - 2, 4, op_h + 4), 1,
                         border_radius=RADIUS_XS)
        y += op_h + 8
        # Drop shadow toggle + blur stepper.
        sh_on = _app["shadow"] is not None
        sh_r = pygame.Rect(x, y, PANEL_W - 40, 24)
        state["shadow_toggle_rect"] = sh_r
        _button(sh_r, "Shadow: ON" if sh_on else "Shadow: OFF", active=sh_on)
        _queue_tip(sh_r, None, "Toggle drop shadow")
        y += 28
        if sh_on:
            blur_val = int(round(float(_app["shadow"].get("blur", 4.0))))
            screen.blit(font_small.render(f"Shadow blur {blur_val}px", True, MUTED_COLOR),
                        (x, y)); y += 16
            bmw = (PANEL_W - 40 - 6) // 2
            minus_r = pygame.Rect(x, y, bmw, 22)
            plus_r = pygame.Rect(x + bmw + 6, y, bmw, 22)
            state["shadow_blur_minus_rect"] = minus_r
            state["shadow_blur_plus_rect"] = plus_r
            _button(minus_r, "- Blur")
            _button(plus_r, "+ Blur")
    else:
        for _k in APPEAR_KEYS:
            state[_k] = pygame.Rect(0, 0, 0, 0)
    _sync_out(c)
    _part_c2_mid(c)
    _sync_in(c)
    _sync_out(c)
    from views.panel_select_parts_c2 import _part_c2_tail
    _part_c2_tail(c)
    _sync_in(c)
    _sync_out(c)

def _part_c2_mid(c):
    _sync_in(c)
    screen=c.screen; fonts=c.fonts; mouse_pos=c.mouse_pos; state=c.state; x=c.x; y=c.y
    _button=c._button; _queue_tip=c._queue_tip; help_lines=c.help_lines
    font, font_small, font_title = fonts
    sel_strokes=c.sel_strokes; sel_count=c.sel_count; submode=c.submode; sel_stroke=c.sel_stroke
    stroke_color_enabled=getattr(c,'stroke_color_enabled',True)
    fill_enabled=getattr(c,'fill_enabled',True)
    component_stroke_enabled=getattr(c,'component_stroke_enabled',False)
    point_width_enabled=getattr(c,'point_width_enabled',False)
    width_enabled=getattr(c,'width_enabled',False)
    shape_style_enabled=getattr(c,'shape_style_enabled',True)
    color_target=getattr(c,'color_target','stroke')
    has_fill_now=getattr(c,'has_fill_now',False)
    comp_style_target=getattr(c,'comp_style_target',None)
    point_style_target=getattr(c,'point_style_target',None)
    stroke=getattr(c,'stroke',None)
    eff_sc=getattr(c,'eff_sc',None)
    eff_sw=getattr(c,'eff_sw',None)
    fill_pat=getattr(c,'fill_pat',None)
    fill_grad=getattr(c,'fill_grad',None)
    cur_color=getattr(c,'cur_color',None)
    h=getattr(c,'h',0); s=getattr(c,'s',0); vcol=getattr(c,'vcol',0)
    fill_color=getattr(c,'fill_color',None)
    display_color=getattr(c,'display_color',None)
    sv_w=getattr(c,'sv_w',180); sv_h=getattr(c,'sv_h',180)
    ph=getattr(c,'ph',0); ps=getattr(c,'ps',0); pv=getattr(c,'pv',0); sv=getattr(c,'sv',0); hue=getattr(c,'hue',0)
    picker_h=getattr(c,'picker_h',0); picker_s=getattr(c,'picker_s',0); picker_v=getattr(c,'picker_v',0)
    grad=getattr(c,'grad',None); stops=getattr(c,'stops',None); stop_idx=getattr(c,'stop_idx',0)

    if submode == "nodes":
        if point_width_enabled:
            screen.blit(font_small.render("Stroke width applies to selected point (lines between points)", True, MUTED_COLOR), (x, y)); y += 18
        else:
            screen.blit(font_small.render("Select an anchor point to set its stroke width", True, MUTED_COLOR), (x, y)); y += 18
    elif submode == "curve" and not component_stroke_enabled:
        screen.blit(font_small.render("Select a curve to edit its stroke", True, MUTED_COLOR), (x, y)); y += 18
    elif submode == "curve" and component_stroke_enabled:
        screen.blit(font_small.render("Stroke applies to selected curve", True, MUTED_COLOR), (x, y)); y += 18

    # --- Modern color picker ---
    screen.blit(font.render("Color", True, TEXT_COLOR if (stroke_color_enabled or fill_enabled) else MUTED_COLOR), (x, y)); y += 22
    # target tabs
    tab_w = (PANEL_W - 40 - 8) // 2
    tab_stroke = pygame.Rect(x, y, tab_w, 26)
    tab_fill = pygame.Rect(x + tab_w + 8, y, tab_w, 26)
    state["tab_stroke_rect"] = tab_stroke if stroke_color_enabled else pygame.Rect(0,0,0,0)
    state["tab_fill_rect"] = tab_fill if fill_enabled else pygame.Rect(0,0,0,0)
    for rect, label, key in ((tab_stroke, "Stroke", "stroke"), (tab_fill, "Fill", "fill")):
        enabled_tab = stroke_color_enabled if key == "stroke" else fill_enabled
        active = (color_target == key) and enabled_tab
        _button(rect, label, active=active, enabled=enabled_tab)
    y += 32

    # current color for target
    fill_grad = None
    fill_pat = None
    fill_grad_stop = int(state.get("fill_gradient_stop", 0) or 0)
    if color_target == "stroke":
        cur_color = eff_sc if stroke_color_enabled else (stroke.get("stroke_color", (0.1, 0.1, 0.15)) if stroke else (0.1,0.1,0.15))
        cur_color = cur_color or (0.1, 0.1, 0.15)
        display_color = cur_color
    else:
        fill_grad = get_fill_gradient(stroke) if (stroke is not None and 'get_fill_gradient' in globals()) else (stroke.get("fill_gradient") if isinstance(stroke, dict) and isinstance(stroke.get("fill_gradient"), dict) and stroke.get("fill_gradient", {}).get("type") in ("linear","radial") else None)
        fill_pat = get_fill_pattern(stroke) if (stroke is not None and 'get_fill_pattern' in globals()) else (stroke.get("fill_pattern") if isinstance(stroke, dict) else None)
        if fill_grad is not None:
            stops_n = 0
            try:
                if 'get_gradient_stops' in globals() and callable(globals().get('get_gradient_stops')):
                    stops_n = len(get_gradient_stops(fill_grad) or [])
                else:
                    stops_n = len(fill_grad.get("stops") or [])
            except Exception:
                stops_n = len(fill_grad.get("stops") or [])
            if stops_n <= 0:
                fill_grad_stop = 0
            else:
                fill_grad_stop = max(0, min(fill_grad_stop, stops_n - 1))
            state["fill_gradient_stop"] = fill_grad_stop
            cur_color = get_gradient_stop_color(fill_grad, fill_grad_stop) if 'get_gradient_stop_color' in globals() else (1.0,1.0,1.0,1.0)
        else:
            cur_color = stroke.get("fill_color", None) if stroke else None
        display_color = cur_color if cur_color is not None else (1.0, 1.0, 1.0)
    h, s, vcol = rgb_to_hsv(*display_color)
    # keep picker state in sync if not dragging
    if not state.get("picker_drag_sv") and not state.get("picker_drag_hue"):
        state["picker_h"] = h
        state["picker_s"] = s
        state["picker_v"] = vcol
    ph = state.get("picker_h", h)
    ps = state.get("picker_s", s)
    pv = state.get("picker_v", vcol)

    # preview + hex + no-fill
    preview = pygame.Rect(x, y, 34, 34)
    pygame.draw.rect(screen, SURFACE, preview, border_radius=RADIUS_MD)
    inner = preview.inflate(-6, -6)
    has_fill_now = (cur_color is not None) or (color_target == "fill" and (fill_grad is not None or fill_pat is not None))
    if color_target == "fill" and not has_fill_now:
        pygame.draw.rect(screen, SURFACE_SUBTLE, inner, border_radius=RADIUS_SM)
        pygame.draw.line(screen, NO_SWATCH_COLOR, inner.topleft, inner.bottomright, BORDER_WIDTH_ACTIVE)
        hex_txt = "None"
    else:
        if color_target == "fill" and fill_pat is not None:
            # pattern preview: striped thumbnail in the pattern colours
            pg = fill_pat.get("fg") or (0.2, 0.3, 0.5, 1.0)
            pbg = fill_pat.get("bg")
            if pbg:
                pygame.draw.rect(screen, to_screen_rgb(pbg), inner, border_radius=RADIUS_SM)
            else:
                pygame.draw.rect(screen, SURFACE_SUBTLE, inner, border_radius=RADIUS_SM)
            fg_screen = to_screen_rgb(pg)
            for off in range(-inner.h, inner.w, 8):
                pygame.draw.line(screen, fg_screen,
                                 (inner.x + off, inner.bottom - 1),
                                 (inner.x + off + inner.h, inner.y), 2)
        elif color_target == "fill" and fill_grad is not None:
            # gradient preview (multi-stop)
            stops = get_gradient_stops(fill_grad) if 'get_gradient_stops' in globals() else (fill_grad.get("stops") or [])
            for ix in range(inner.w):
                t = ix / max(1, inner.w - 1)
                sc = (0.0, 0.0, 0.0, 1.0)
                try:
                    ordered = sorted(stops, key=lambda s: float((s or {}).get("pos", 0.0))) if stops else []
                    if not ordered:
                        sc = (0.0, 0.0, 0.0, 1.0)
                    elif t <= float(ordered[0].get("pos", 0.0)):
                        sc = color_rgba(ordered[0].get("color"), (0, 0, 0, 1))
                    elif t >= float(ordered[-1].get("pos", 1.0)):
                        sc = color_rgba(ordered[-1].get("color"), (1, 1, 1, 1))
                    else:
                        sc = color_rgba(ordered[-1].get("color"), (1, 1, 1, 1))
                        for a, b in zip(ordered, ordered[1:]):
                            pa = float(a.get("pos", 0.0)); pb = float(b.get("pos", 1.0))
                            if pa <= t <= pb:
                                lt = 0.0 if pb - pa <= 1e-9 else (t - pa) / (pb - pa)
                                ca = color_rgba(a.get("color"), (0, 0, 0, 1))
                                cb = color_rgba(b.get("color"), (1, 1, 1, 1))
                                sc = tuple(ca[k] + (cb[k] - ca[k]) * lt for k in range(4))
                                break
                except Exception:
                    sc = (0.0, 0.0, 0.0, 1.0)
                a = float(sc[3]) if len(sc) >= 4 else 1.0
                bgv = 235 if (ix // 6) % 2 == 0 else 210
                r = int((sc[0] * a + (bgv / 255.0) * (1 - a)) * 255)
                g = int((sc[1] * a + (bgv / 255.0) * (1 - a)) * 255)
                b = int((sc[2] * a + (bgv / 255.0) * (1 - a)) * 255)
                pygame.draw.line(screen, (r, g, b), (inner.x + ix, inner.y), (inner.x + ix, inner.bottom - 1))
        else:
            rgb_show = to_screen_rgb(color_rgb(display_color))
            pygame.draw.rect(screen, rgb_show, inner, border_radius=RADIUS_SM)
        hex_txt = rgb_to_hex(display_color)
    pygame.draw.rect(screen, BUTTON_BORDER, preview, 1, border_radius=RADIUS_MD)
    screen.blit(font_small.render(hex_txt, True, TEXT_COLOR), (x + 42, y + 9))
    _sync_out(c)


def _part_d(c):
    _sync_in(c)
    screen=c.screen; fonts=c.fonts; mouse_pos=c.mouse_pos; state=c.state; x=c.x; y=c.y
    _button=c._button; _queue_tip=c._queue_tip; help_lines=c.help_lines
    font, font_small, font_title = fonts
    sel_strokes=c.sel_strokes; sel_count=c.sel_count; submode=c.submode; sel_stroke=c.sel_stroke
    if state.get("redrawing_curve"):
        help_lines = [
            "Draw to redraw selected stroke.",
            "Start/end stay fixed.",
            "Release mouse to apply.",
        ]
    elif sel_count == 0:
        help_lines = [
            "Click stroke to select.",
            "Shift+click: multi-select.",
            "N: cycle Transform/Nodes/Curve.",
            "Shortcuts: Ctrl+Z/Ctrl+Y, C, Esc",
        ]
    elif sel_count > 1:
        help_lines = [
            f"{sel_count} shapes selected.",
            "Shift+click: toggle selection.",
            "Drag/handles: move or transform.",
            "N: cycle Transform/Nodes/Curve.",
            "Delete: remove selected.",
        ]
    elif submode == "transform":
        help_lines = [
            "Drag inside box to move.",
            "Drag handles to scale/rotate.",
            "N: cycle Transform/Nodes/Curve.",
            "Delete: remove selected.",
        ]
    elif submode == "nodes":
        help_lines = [
            "Drag anchors/handles to edit.",
            "Smooth joins mirror handles.",
            "N: cycle Transform/Nodes/Curve.",
            "Delete: remove selected.",
        ]
    else:
        help_lines = [
            "Click a curve/component to select.",
            "Shift+click to select multiple curves.",
            "Select multiple curves and use Join to merge.",
            "Redraw/Split edit the active curve.",
            "N: cycle Transform/Nodes/Curve.",
        ]

    c.y=y; c.help_lines=help_lines; c.sel_stroke=sel_stroke; c.submode=submode
    c.sel_count=sel_count; c.sel_strokes=sel_strokes
    _sync_out(c)