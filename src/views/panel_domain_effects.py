"""View: panel_select parts B (SRP)."""
"""View: panel section (split for complexity)."""
import math
import pygame
import config as cfg
from config import *
from views.panel_select_parts import _draw_wave_graph, _value_ramp, _sv_surface, _hue_bar_surface
from controllers.coordinates import clamp
from models.strokes import _component_ranges, _stroke_components, segs_of
from models.waves import WAVE_SHAPE_LABEL_DICT, _component_styles, _get_distortion_styles
from models.waves_extra import _distortion_style_preview_polyline
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


def _part_b2b_main(c):
    _sync_in(c)
    _style_slider=getattr(c,"_style_slider",None)
    BOX_H=getattr(c,'BOX_H',None); BOX_W=getattr(c,'BOX_W',None); _button=getattr(c,'_button',None); _gap_slider=getattr(c,'_gap_slider',None); _queue_tip=getattr(c,'_queue_tip',None); _sel_curves_panel=getattr(c,'_sel_curves_panel',None); active_style=getattr(c,'active_style',None); affect_items=getattr(c,'affect_items',None); affect_rects=getattr(c,'affect_rects',None); akey=getattr(c,'akey',None); alabel=getattr(c,'alabel',None); amp_v=getattr(c,'amp_v',None); arrow=getattr(c,'arrow',None); bake_rect=getattr(c,'bake_rect',None); bg=getattr(c,'bg',None); bg_col=getattr(c,'bg_col',None); box_rect=getattr(c,'box_rect',None); btn_gap=getattr(c,'btn_gap',None); btn_w=getattr(c,'btn_w',None); btns_y=getattr(c,'btns_y',None); bw=getattr(c,'bw',None); bx=getattr(c,'bx',None); by=getattr(c,'by',None); cap_txt=getattr(c,'cap_txt',None); ci=getattr(c,'ci',None); clamp_labels=getattr(c,'clamp_labels',None); clamp_mode=getattr(c,'clamp_mode',None); clamp_rect=getattr(c,'clamp_rect',None); clr_r=getattr(c,'clr_r',None); col=getattr(c,'col',None); coli=getattr(c,'coli',None); collapsed=getattr(c,'collapsed',None); cols=getattr(c,'cols',None); comp=getattr(c,'comp',None); comp_hidden=getattr(c,'comp_hidden',None); comp_i=getattr(c,'comp_i',None); comps=getattr(c,'comps',None); cp=getattr(c,'cp',None); cur_shape=getattr(c,'cur_shape',None); cut_active=getattr(c,'cut_active',None); cut_rect=getattr(c,'cut_rect',None); cxp=getattr(c,'cxp',None); cyc_t=getattr(c,'cyc_t',None); cyp=getattr(c,'cyp',None); d_rect=getattr(c,'d_rect',None); dist_all=getattr(c,'dist_all',None); done_r=getattr(c,'done_r',None); enabled=getattr(c,'enabled',None); enabled_sl=getattr(c,'enabled_sl',None); finish_instr=getattr(c,'finish_instr',None); fmt=getattr(c,'fmt',None); focused=getattr(c,'focused',None); font=getattr(c,'font',None); font_small=getattr(c,'font_small',None); font_title=getattr(c,'font_title',None); fonts=getattr(c,'fonts',None); frect=getattr(c,'frect',None); freq_v=getattr(c,'freq_v',None); ftxt=getattr(c,'ftxt',None); ftxt_disp=getattr(c,'ftxt_disp',None); fval=getattr(c,'fval',None); gap=getattr(c,'gap',None); gap_val=getattr(c,'gap_val',None); has_dist=getattr(c,'has_dist',None); has_wave_pts=getattr(c,'has_wave_pts',None); hbg=getattr(c,'hbg',None); hdr_rect=getattr(c,'hdr_rect',None); header_label=getattr(c,'header_label',None); help_lines=getattr(c,'help_lines',None); hi=getattr(c,'hi',None); hidden=getattr(c,'hidden',None); hint=getattr(c,'hint',None); hit=getattr(c,'hit',None); i=getattr(c,'i',None); icon_rect=getattr(c,'icon_rect',None); icon_wave=getattr(c,'icon_wave',None); info=getattr(c,'info',None); instr=getattr(c,'instr',None); is_active=getattr(c,'is_active',None); k=getattr(c,'k',None); key=getattr(c,'key',None); label=getattr(c,'label',None); label_what=getattr(c,'label_what',None); lbl=getattr(c,'lbl',None); lbl_surf=getattr(c,'lbl_surf',None); len_v=getattr(c,'len_v',None); lo=getattr(c,'lo',None); loc_v=getattr(c,'loc_v',None); mouse_pos=getattr(c,'mouse_pos',None); n_dist=getattr(c,'n_dist',None); noise_on=getattr(c,'noise_on',None); noise_v=getattr(c,'noise_v',None); nr=getattr(c,'nr',None); nsc_v=getattr(c,'nsc_v',None); nscale_v=getattr(c,'nscale_v',None); on=getattr(c,'on',None); phase_v=getattr(c,'phase_v',None); pick_r=getattr(c,'pick_r',None); picking=getattr(c,'picking',None); pr=getattr(c,'pr',None); prev_px=getattr(c,'prev_px',None); prev_py=getattr(c,'prev_py',None); prev_rect=getattr(c,'prev_rect',None); pt_count=getattr(c,'pt_count',None); px=getattr(c,'px',None); py=getattr(c,'py',None); r=getattr(c,'r',None); r_rect=getattr(c,'r_rect',None); ranges=getattr(c,'ranges',None); rect=getattr(c,'rect',None); redraw_rect=getattr(c,'redraw_rect',None); rem_rect=getattr(c,'rem_rect',None); rev=getattr(c,'rev',None); rev_rect=getattr(c,'rev_rect',None); rot_v=getattr(c,'rot_v',None); row=getattr(c,'row',None); row_h=getattr(c,'row_h',None); rowi=getattr(c,'rowi',None); s0=getattr(c,'s0',None); s1=getattr(c,'s1',None); sc=getattr(c,'sc',None); screen=getattr(c,'screen',None); seed_v=getattr(c,'seed_v',None); sel_count=getattr(c,'sel_count',None); sel_stroke=getattr(c,'sel_stroke',None); sel_strokes=getattr(c,'sel_strokes',None); shape=getattr(c,'shape',None); shape_items=getattr(c,'shape_items',None); shape_labels=getattr(c,'shape_labels',None); smooth_r=getattr(c,'smooth_r',None); smooth_rect=getattr(c,'smooth_rect',None); state=getattr(c,'state',None); stt=getattr(c,'stt',None); style_type=getattr(c,'style_type',None); styles=getattr(c,'styles',None); stype=getattr(c,'stype',None); submode=getattr(c,'submode',None); sv=getattr(c,'sv',None); sv_on=getattr(c,'sv_on',None); t=getattr(c,'t',None); t_rect=getattr(c,'t_rect',None); tog_rect=getattr(c,'tog_rect',None); total_w=getattr(c,'total_w',None); track=getattr(c,'track',None); tt=getattr(c,'tt',None); tx=getattr(c,'tx',None); txt=getattr(c,'txt',None); v=getattr(c,'v',None); val=getattr(c,'val',None); vr=getattr(c,'vr',None); vt=getattr(c,'vt',None); vw=getattr(c,'vw',None); w_rect=getattr(c,'w_rect',None); wave=getattr(c,'wave',None); wi=getattr(c,'wi',None); wlabel=getattr(c,'wlabel',None); wshape_i=getattr(c,'wshape_i',None); x=getattr(c,'x',None); x0=getattr(c,'x0',None); y=getattr(c,'y',None); y0=getattr(c,'y0',None)

    screen=c.screen; fonts=c.fonts; mouse_pos=c.mouse_pos; state=c.state; x=c.x; y=c.y
    _button=c._button; _queue_tip=c._queue_tip; help_lines=c.help_lines
    font, font_small, font_title = fonts
    sel_strokes=c.sel_strokes; sel_count=c.sel_count; submode=c.submode; sel_stroke=c.sel_stroke
    _sel_curves_panel=getattr(c,'_sel_curves_panel',set())
    if submode == "curve" and sel_count == 1 and sel_stroke is not None:
        sc = state.get("selected_curve")
        if sc and sc[0] in sel_strokes:
            comp_i = sc[1]
            comps = _stroke_components(sel_stroke)
            label_what = "stroke" if len(comps) > 1 else "curve"
            screen.blit(font_small.render(f"Selected {label_what}: {comp_i + 1}/{max(1,len(comps))}", True, MUTED_COLOR), (x, y)); y += 22
            hidden = set(sel_stroke.get("hidden_segs", set()) or set()) if isinstance(sel_stroke, dict) else set()
            ranges = _component_ranges(sel_stroke)
            comp_hidden = []
            if 0 <= comp_i < len(ranges):
                s0, s1 = ranges[comp_i]
                comp_hidden = [i for i in range(s0, min(s1, len(segs_of(sel_stroke)))) if i in hidden]
            if 0 <= comp_i < len(comps):
                ci = comps[comp_i]
                info = f"Settings: {ci.get('algorithm','fit')}, pts {ci.get('draw_max_points',4)}"
                screen.blit(font_small.render(info, True, MUTED_COLOR), (x, y)); y += 18
            if comp_hidden:
                hint = "Hidden curve segment(s)" if len(comp_hidden) < (ranges[comp_i][1]-ranges[comp_i][0] if 0 <= comp_i < len(ranges) else 999) else "Hidden curve"
                screen.blit(font_small.render(f"Hint: {hint} (shown dashed in edit modes)", True, TEXT_WARNING), (x, y)); y += 18
            total_w = PANEL_W - 40
            btn_gap = 6
            btn_w = (total_w - btn_gap) // 2
            redraw_rect = pygame.Rect(x, y, btn_w, 30)
            cut_rect = pygame.Rect(x + btn_w + btn_gap, y, total_w - btn_w - btn_gap, 30)
            state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
            state["curve_redraw_rect"] = redraw_rect
            state["curve_cut_rect"] = cut_rect
            _button(redraw_rect, "Redraw", icon="curve_redraw")
            _queue_tip(redraw_rect, "curve_redraw")
            cut_active = bool(state.get("curve_cut_mode"))
            _button(cut_rect, "Split curve", active=cut_active, icon="cutter")
            _queue_tip(cut_rect, "curve_cut")
            y += 38
            if cut_active:
                screen.blit(font_small.render("Drag across the selected curve to cut it.",
                                              True, ACCENT), (x, y)); y += 20

                # Optional gap: 0 keeps the stroke connected at the new node.
                screen.blit(font.render("Gap", True, TEXT_COLOR), (x, y)); y += 24
                gap_val = int(state.get("cut_gap", 0) or 0)
                val = font_title.render(f"{gap_val} px", True, ACCENT)
                screen.blit(val, (x, y - 2))
                hint = font_small.render("(0 = stays connected)", True, MUTED_COLOR)
                screen.blit(hint, (x + val.get_width() + 10, y + 4)); y += 30
                _gap_slider = state.get("cut_gap_slider")
                if _gap_slider is not None:
                    _gap_slider.track.topleft = (x, y)
                    _gap_slider.track.width = PANEL_W - 40
                    _gap_slider.value = gap_val
                    _gap_slider.draw(screen)
                y += 26
            else:
                _gap_slider = state.get("cut_gap_slider")
                if _gap_slider is not None:
                    _gap_slider.track.width = 0

            # Curve styles list (non-destructive). Styles are added to this curve.
            comp = comps[comp_i] if 0 <= comp_i < len(comps) else {}
            styles = _component_styles(comp)
            dist_all = _get_distortion_styles(comp)
            has_dist = len(dist_all) > 0
            n_dist = len(dist_all)
            collapsed = bool(state.get("wave_list_collapsed"))
            arrow = ">" if collapsed else "v"
            header_label = f"{arrow} Curve styles"
            if has_dist:
                header_label += f" ({n_dist})"
            hdr_rect = pygame.Rect(x, y, PANEL_W - 40, 22)
            state["wave_list_header_rect"] = hdr_rect
            hbg = BUTTON_HOVER if hdr_rect.collidepoint(mouse_pos) else None
            if hbg:
                pygame.draw.rect(screen, hbg, hdr_rect, border_radius=RADIUS_MD)
            screen.blit(font_small.render(header_label, True, TEXT_COLOR), (x + 4, y + 3))
            y += 24

            state["wave_add_rect"] = pygame.Rect(0,0,0,0)
            state["displacement_add_rect"] = pygame.Rect(0,0,0,0)
            state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
            state["wave_bake_rect"] = pygame.Rect(0,0,0,0)
            state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
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

            def _draw_add_style_buttons(x0, y0):
                # Add buttons: wave distortion, displacement, repeat curve, thickness
                gap = 4
                bw = (PANEL_W - 40 - gap * 3) // 4
                w_rect = pygame.Rect(x0, y0, bw, 24)
                d_rect = pygame.Rect(x0 + bw + gap, y0, bw, 24)
                r_rect = pygame.Rect(x0 + (bw + gap) * 2, y0, bw, 24)
                t_rect = pygame.Rect(x0 + (bw + gap) * 3, y0, PANEL_W - 40 - (bw + gap) * 3, 24)
                for rect, key, label in ((w_rect, "wave_add", "Wave"), (d_rect, "displacement_add", "Displace"), (r_rect, "repeat_add", "Repeat"), (t_rect, "thickness_add", "Thick")):
                    _button(rect, label, icon=key)
                    _queue_tip(rect, key)
                state["wave_add_rect"] = w_rect
                state["displacement_add_rect"] = d_rect
                state["repeat_add_rect"] = r_rect
                state["thickness_add_rect"] = t_rect
                return y0 + 30

            if collapsed:
                # keep details hidden but allow adding styles
                y = _draw_add_style_buttons(x, y)
            elif has_dist:
                # active (expanded) distortion style index, clamped to the stack
                wi = int(state.get("wave_active_index", 0) or 0)
                if not (0 <= wi < n_dist):
                    wi = max(0, n_dist - 1)
                active_style = dist_all[wi]
                style_type = str(active_style.get("type", "wave") or "wave")
                enabled = bool(active_style.get("enabled"))
                shape = str(active_style.get("shape", "sine") or "sine").lower()

                # ---- modifier stack rows: click a row to edit that style ----
                row_h = 26
                for i, sv in enumerate(dist_all):
                    row = pygame.Rect(x, y, PANEL_W - 40, row_h)
                    is_active = (i == wi)
                    sv_on = bool(sv.get("enabled"))
                    _button(row, "", active=is_active)
                    stype = str(sv.get("type", "wave") or "wave")
                    if stype == "displacement":
                        lbl = f"Displacement {i + 1}"
                    elif stype == "repeat":
                        lbl = f"Repeat {i + 1}"
                    elif stype == "thickness":
                        lbl = f"Thickness {i + 1}"
                    else:
                        wshape_i = str(sv.get("shape", "sine") or "sine").lower()
                        if wshape_i == "noise":
                            lbl = f"Noise {i + 1}"
                        else:
                            wlabel = WAVE_SHAPE_LABEL_DICT.get(wshape_i, "Wave")
                            lbl = f"Wave {i + 1} \u00b7 {wlabel}"
                    t = font_small.render(lbl, True, TEXT_COLOR if is_active else MUTED_COLOR)
                    screen.blit(t, (row.x + 8, row.y + 5))
                    if is_active:
                        tog_rect = pygame.Rect(row.right - 74, row.y + 3, 46, row_h - 6)
                        rem_rect = pygame.Rect(row.right - 26, row.y + 3, 22, row_h - 6)
                        state["wave_toggle_rect"] = tog_rect
                        state["wave_remove_rect"] = rem_rect
                        draw_toggle(screen, tog_rect, sv_on, font_small, mouse_pos=mouse_pos)
                        _queue_tip(tog_rect, "wave_toggle")
                        draw_button(screen, rem_rect, "\u00d7", font_small,
                                    mouse_pos=mouse_pos, color=DANGER, radius=RADIUS_MD)
                        _queue_tip(rem_rect, "wave_remove")
                    else:
                        stt = font_small.render("ON" if sv_on else "OFF", True, ACCENT if sv_on else MUTED_COLOR)
                        screen.blit(stt, (row.right - 8 - stt.get_width(), row.y + 5))
                    state["wave_row_rects"].append((i, row))
                    y += row_h + 2
                y += 4

                # ---- live preview of the active style (instant feedback) ----
                screen.blit(font_small.render("Preview", True, TEXT_COLOR), (x, y))
                cap_txt = ""
                if style_type in ("wave", "repeat"):
                    fval = float(active_style.get("frequency", 0.0))
                    if fval > 1.0:
                        cap_txt = f"density {fval:.1f}" if shape == "noise" else f"{fval:.1f} cycles"
                    else:
                        cap_txt = f"cycle {fval:.2f}x diag"
                else:
                    cap_txt = str(active_style.get("profile", "flat"))
                if cap_txt:
                    cyc_t = font_small.render(cap_txt, True, MUTED_COLOR)
                    screen.blit(cyc_t, (x + PANEL_W - 40 - cyc_t.get_width(), y))
                y += 18
                prev_rect = pygame.Rect(x, y, PANEL_W - 40, 36)
                _draw_wave_graph(screen, prev_rect, _distortion_style_preview_polyline(active_style), ACCENT if enabled else PLOT_LINE_DISABLED)
                if not enabled:
                    hint = font_small.render("disabled - click ON to apply", True, TEXT_DISABLED)
                    screen.blit(hint, hint.get_rect(center=prev_rect.center))
                y += 36 + 6

                # ---- add more styles on top of the stack ----
                y = _draw_add_style_buttons(x, y)
                bake_rect = pygame.Rect(x, y, PANEL_W - 40, 24)
                _button(bake_rect, "Bake styles", icon="wave_apply")
                _queue_tip(bake_rect, "wave_apply")
                state["wave_bake_rect"] = bake_rect
                y += 30
                y += 2

                # ---- parameters (contextual) ----
                def _style_slider(label, key, val, lo, hi, fmt=None, enabled_sl=True):
                    nonlocal y
                    col = TEXT_COLOR if enabled_sl else MUTED_COLOR
                    screen.blit(font_small.render(label, True, col), (x, y))
                    txt = fmt(val) if fmt else str(val)
                    vt = font_small.render(txt, True, ACCENT if enabled_sl else MUTED_COLOR)
                    screen.blit(vt, (x + PANEL_W - 40 - vt.get_width(), y))
                    y += 18
                    track = pygame.Rect(x, y, PANEL_W - 40, 6)
                    if hi == lo:
                        tx = track.x
                    else:
                        tx = int(track.x + (clamp(val, lo, hi) - lo) / (hi - lo) * track.w)
                    draw_track(screen, track, filled_to=tx, enabled=enabled_sl)
                    draw_slider_knob(screen, tx, track.centery, enabled=enabled_sl)
                    if enabled_sl:
                        hit = track.inflate(0, 16)
                        state.setdefault("wave_slider_rects", {})[key] = (hit, lo, hi)
                    y += 8
                c._style_slider = _style_slider

                if style_type == "displacement":
                    _sync_out(c); 
                    from views.panel_select_parts_b2_styles import _b2b_disp
                    _b2b_disp(c); _sync_in(c)
                elif style_type == "repeat":
                    _sync_out(c); 
                    from views.panel_select_parts_b2_styles import _b2b_rep
                    _b2b_rep(c); _sync_in(c)
                elif style_type == "thickness":
                    _sync_out(c); 
                    from views.panel_select_parts_b2_styles import _b2b_thick
                    _b2b_thick(c); _sync_in(c)
                else:
                    _sync_out(c); 
                    from views.panel_select_parts_b2_styles import _b2b_wave
                    _b2b_wave(c); _sync_in(c)
            else:
                y = _draw_add_style_buttons(x, y)
                screen.blit(font_small.render("No curve styles added", True, MUTED_COLOR), (x, y)); y += 18
        else:
            screen.blit(font_small.render("Click a stroke to edit separately", True, MUTED_COLOR), (x, y)); y += 24
            state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
            state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
            state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
            state["curve_join_rect"] = pygame.Rect(0,0,0,0)
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

    elif submode == "curve":
        screen.blit(font_small.render("Click a stroke to edit separately", True, MUTED_COLOR), (x, y)); y += 24
        state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
        state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
        state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
        state["curve_join_rect"] = pygame.Rect(0,0,0,0)
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
    else:
        state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
        state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
        state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
        state["curve_join_rect"] = pygame.Rect(0,0,0,0)
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

    c.y=y; c.help_lines=help_lines; c.sel_stroke=sel_stroke; c.submode=submode
    c.sel_count=sel_count; c.sel_strokes=sel_strokes
    _sync_out(c)




