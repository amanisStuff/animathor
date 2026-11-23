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


def _b2b_disp(c):
    _sync_in(c)
    _style_slider=getattr(c,"_style_slider",None)
    BOX_H=getattr(c,'BOX_H',None); BOX_W=getattr(c,'BOX_W',None); _button=getattr(c,'_button',None); _gap_slider=getattr(c,'_gap_slider',None); _queue_tip=getattr(c,'_queue_tip',None); _sel_curves_panel=getattr(c,'_sel_curves_panel',None); active_style=getattr(c,'active_style',None); affect_items=getattr(c,'affect_items',None); affect_rects=getattr(c,'affect_rects',None); akey=getattr(c,'akey',None); alabel=getattr(c,'alabel',None); amp_v=getattr(c,'amp_v',None); arrow=getattr(c,'arrow',None); bake_rect=getattr(c,'bake_rect',None); bg=getattr(c,'bg',None); bg_col=getattr(c,'bg_col',None); box_rect=getattr(c,'box_rect',None); btn_gap=getattr(c,'btn_gap',None); btn_w=getattr(c,'btn_w',None); btns_y=getattr(c,'btns_y',None); bw=getattr(c,'bw',None); bx=getattr(c,'bx',None); by=getattr(c,'by',None); cap_txt=getattr(c,'cap_txt',None); ci=getattr(c,'ci',None); clamp_labels=getattr(c,'clamp_labels',None); clamp_mode=getattr(c,'clamp_mode',None); clamp_rect=getattr(c,'clamp_rect',None); clr_r=getattr(c,'clr_r',None); col=getattr(c,'col',None); coli=getattr(c,'coli',None); collapsed=getattr(c,'collapsed',None); cols=getattr(c,'cols',None); comp=getattr(c,'comp',None); comp_hidden=getattr(c,'comp_hidden',None); comp_i=getattr(c,'comp_i',None); comps=getattr(c,'comps',None); cp=getattr(c,'cp',None); cur_shape=getattr(c,'cur_shape',None); cut_active=getattr(c,'cut_active',None); cut_rect=getattr(c,'cut_rect',None); cxp=getattr(c,'cxp',None); cyc_t=getattr(c,'cyc_t',None); cyp=getattr(c,'cyp',None); d_rect=getattr(c,'d_rect',None); dist_all=getattr(c,'dist_all',None); done_r=getattr(c,'done_r',None); enabled=getattr(c,'enabled',None); enabled_sl=getattr(c,'enabled_sl',None); finish_instr=getattr(c,'finish_instr',None); fmt=getattr(c,'fmt',None); focused=getattr(c,'focused',None); font=getattr(c,'font',None); font_small=getattr(c,'font_small',None); font_title=getattr(c,'font_title',None); fonts=getattr(c,'fonts',None); frect=getattr(c,'frect',None); freq_v=getattr(c,'freq_v',None); ftxt=getattr(c,'ftxt',None); ftxt_disp=getattr(c,'ftxt_disp',None); fval=getattr(c,'fval',None); gap=getattr(c,'gap',None); gap_val=getattr(c,'gap_val',None); has_dist=getattr(c,'has_dist',None); has_wave_pts=getattr(c,'has_wave_pts',None); hbg=getattr(c,'hbg',None); hdr_rect=getattr(c,'hdr_rect',None); header_label=getattr(c,'header_label',None); help_lines=getattr(c,'help_lines',None); hi=getattr(c,'hi',None); hidden=getattr(c,'hidden',None); hint=getattr(c,'hint',None); hit=getattr(c,'hit',None); i=getattr(c,'i',None); icon_rect=getattr(c,'icon_rect',None); icon_wave=getattr(c,'icon_wave',None); info=getattr(c,'info',None); instr=getattr(c,'instr',None); is_active=getattr(c,'is_active',None); k=getattr(c,'k',None); key=getattr(c,'key',None); label=getattr(c,'label',None); label_what=getattr(c,'label_what',None); lbl=getattr(c,'lbl',None); lbl_surf=getattr(c,'lbl_surf',None); len_v=getattr(c,'len_v',None); lo=getattr(c,'lo',None); loc_v=getattr(c,'loc_v',None); mouse_pos=getattr(c,'mouse_pos',None); n_dist=getattr(c,'n_dist',None); noise_on=getattr(c,'noise_on',None); noise_v=getattr(c,'noise_v',None); nr=getattr(c,'nr',None); nsc_v=getattr(c,'nsc_v',None); nscale_v=getattr(c,'nscale_v',None); on=getattr(c,'on',None); phase_v=getattr(c,'phase_v',None); pick_r=getattr(c,'pick_r',None); picking=getattr(c,'picking',None); pr=getattr(c,'pr',None); prev_px=getattr(c,'prev_px',None); prev_py=getattr(c,'prev_py',None); prev_rect=getattr(c,'prev_rect',None); pt_count=getattr(c,'pt_count',None); px=getattr(c,'px',None); py=getattr(c,'py',None); r=getattr(c,'r',None); r_rect=getattr(c,'r_rect',None); ranges=getattr(c,'ranges',None); rect=getattr(c,'rect',None); redraw_rect=getattr(c,'redraw_rect',None); rem_rect=getattr(c,'rem_rect',None); rev=getattr(c,'rev',None); rev_rect=getattr(c,'rev_rect',None); rot_v=getattr(c,'rot_v',None); row=getattr(c,'row',None); row_h=getattr(c,'row_h',None); rowi=getattr(c,'rowi',None); s0=getattr(c,'s0',None); s1=getattr(c,'s1',None); sc=getattr(c,'sc',None); screen=getattr(c,'screen',None); seed_v=getattr(c,'seed_v',None); sel_count=getattr(c,'sel_count',None); sel_stroke=getattr(c,'sel_stroke',None); sel_strokes=getattr(c,'sel_strokes',None); shape=getattr(c,'shape',None); shape_items=getattr(c,'shape_items',None); shape_labels=getattr(c,'shape_labels',None); smooth_r=getattr(c,'smooth_r',None); smooth_rect=getattr(c,'smooth_rect',None); state=getattr(c,'state',None); stt=getattr(c,'stt',None); style_type=getattr(c,'style_type',None); styles=getattr(c,'styles',None); stype=getattr(c,'stype',None); submode=getattr(c,'submode',None); sv=getattr(c,'sv',None); sv_on=getattr(c,'sv_on',None); t=getattr(c,'t',None); t_rect=getattr(c,'t_rect',None); tog_rect=getattr(c,'tog_rect',None); total_w=getattr(c,'total_w',None); track=getattr(c,'track',None); tt=getattr(c,'tt',None); tx=getattr(c,'tx',None); txt=getattr(c,'txt',None); v=getattr(c,'v',None); val=getattr(c,'val',None); vr=getattr(c,'vr',None); vt=getattr(c,'vt',None); vw=getattr(c,'vw',None); w_rect=getattr(c,'w_rect',None); wave=getattr(c,'wave',None); wi=getattr(c,'wi',None); wlabel=getattr(c,'wlabel',None); wshape_i=getattr(c,'wshape_i',None); x=getattr(c,'x',None); x0=getattr(c,'x0',None); y=getattr(c,'y',None); y0=getattr(c,'y0',None)
    if style_type == "displacement":
        # Point-based displacement: sampled per point along the path,
        # affects anchor location (X/Y) and rotation/length of symmetric
        # handles. Non-destructive.
        state["displacement_profile_rects"] = {}
        state["wave_custom_box_rect"] = pygame.Rect(0, 0, 0, 0)
        state["wave_custom_draw"] = False
        state["wave_smooth_rect"] = pygame.Rect(0, 0, 0, 0)
        state["wave_reverse_rect"] = pygame.Rect(0, 0, 0, 0)
        state["wave_clamp_rect"] = pygame.Rect(0, 0, 0, 0)
        screen.blit(font_small.render("Point displacement (along path)", True, TEXT_COLOR), (x, y)); y += 20

        # Apply-to toggles (combinable): axes and handle properties
        screen.blit(font_small.render("Apply to", True, TEXT_COLOR), (x, y)); y += 20
        affect_rects = {}
        affect_items = [("affect_x", "X"), ("affect_y", "Y"), ("affect_rotate", "Rotate"), ("affect_length", "Length")]
        cols = 2
        gap = 6
        bw = (PANEL_W - 40 - gap * (cols - 1)) // cols
        for i, (akey, alabel) in enumerate(affect_items):
            rowi, coli = divmod(i, cols)
            r = pygame.Rect(x + coli * (bw + gap), y + rowi * 28, bw, 24)
            affect_rects[akey] = r
            on = bool(active_style.get(akey, True))
            _button(r, alabel, active=on)
        state["displacement_affect_rects"] = affect_rects
        y += ((len(affect_items) + cols - 1) // cols) * 28 + 6

        screen.blit(font_small.render("Parameters", True, TEXT_COLOR), (x, y)); y += 20
        loc_v = float(active_style.get("location", 0.0) or 0.0)
        rot_v = float(active_style.get("handle_rotate", 0.0) or 0.0)
        len_v = float(active_style.get("handle_length", 0.0) or 0.0)
        nsc_v = float(active_style.get("noise_scale", 1.0) or 1.0)
        seed_v = int(active_style.get("seed", 0) or 0)
        _style_slider("Location", "location", loc_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
        _style_slider("Handle rotate", "handle_rotate", rot_v, -180.0, 180.0, fmt=lambda v: str(int(round(v))))
        _style_slider("Handle length", "handle_length", len_v, -100.0, 100.0, fmt=lambda v: str(int(round(v))))
        _style_slider("Noise scale", "noise_scale", nsc_v, 0.1, 20.0, fmt=lambda v: f"{v:.1f}")
        _style_slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
        screen.blit(font_small.render("Affects selected axes/properties on unbaked nodes (edges fixed).", True, MUTED_COLOR), (x, y)); y += 18
        y += 4
    _sync_out(c)

def _b2b_rep(c):
    _sync_in(c)
    _style_slider=getattr(c,"_style_slider",None)
    BOX_H=getattr(c,'BOX_H',None); BOX_W=getattr(c,'BOX_W',None); _button=getattr(c,'_button',None); _gap_slider=getattr(c,'_gap_slider',None); _queue_tip=getattr(c,'_queue_tip',None); _sel_curves_panel=getattr(c,'_sel_curves_panel',None); active_style=getattr(c,'active_style',None); affect_items=getattr(c,'affect_items',None); affect_rects=getattr(c,'affect_rects',None); akey=getattr(c,'akey',None); alabel=getattr(c,'alabel',None); amp_v=getattr(c,'amp_v',None); arrow=getattr(c,'arrow',None); bake_rect=getattr(c,'bake_rect',None); bg=getattr(c,'bg',None); bg_col=getattr(c,'bg_col',None); box_rect=getattr(c,'box_rect',None); btn_gap=getattr(c,'btn_gap',None); btn_w=getattr(c,'btn_w',None); btns_y=getattr(c,'btns_y',None); bw=getattr(c,'bw',None); bx=getattr(c,'bx',None); by=getattr(c,'by',None); cap_txt=getattr(c,'cap_txt',None); ci=getattr(c,'ci',None); clamp_labels=getattr(c,'clamp_labels',None); clamp_mode=getattr(c,'clamp_mode',None); clamp_rect=getattr(c,'clamp_rect',None); clr_r=getattr(c,'clr_r',None); col=getattr(c,'col',None); coli=getattr(c,'coli',None); collapsed=getattr(c,'collapsed',None); cols=getattr(c,'cols',None); comp=getattr(c,'comp',None); comp_hidden=getattr(c,'comp_hidden',None); comp_i=getattr(c,'comp_i',None); comps=getattr(c,'comps',None); cp=getattr(c,'cp',None); cur_shape=getattr(c,'cur_shape',None); cut_active=getattr(c,'cut_active',None); cut_rect=getattr(c,'cut_rect',None); cxp=getattr(c,'cxp',None); cyc_t=getattr(c,'cyc_t',None); cyp=getattr(c,'cyp',None); d_rect=getattr(c,'d_rect',None); dist_all=getattr(c,'dist_all',None); done_r=getattr(c,'done_r',None); enabled=getattr(c,'enabled',None); enabled_sl=getattr(c,'enabled_sl',None); finish_instr=getattr(c,'finish_instr',None); fmt=getattr(c,'fmt',None); focused=getattr(c,'focused',None); font=getattr(c,'font',None); font_small=getattr(c,'font_small',None); font_title=getattr(c,'font_title',None); fonts=getattr(c,'fonts',None); frect=getattr(c,'frect',None); freq_v=getattr(c,'freq_v',None); ftxt=getattr(c,'ftxt',None); ftxt_disp=getattr(c,'ftxt_disp',None); fval=getattr(c,'fval',None); gap=getattr(c,'gap',None); gap_val=getattr(c,'gap_val',None); has_dist=getattr(c,'has_dist',None); has_wave_pts=getattr(c,'has_wave_pts',None); hbg=getattr(c,'hbg',None); hdr_rect=getattr(c,'hdr_rect',None); header_label=getattr(c,'header_label',None); help_lines=getattr(c,'help_lines',None); hi=getattr(c,'hi',None); hidden=getattr(c,'hidden',None); hint=getattr(c,'hint',None); hit=getattr(c,'hit',None); i=getattr(c,'i',None); icon_rect=getattr(c,'icon_rect',None); icon_wave=getattr(c,'icon_wave',None); info=getattr(c,'info',None); instr=getattr(c,'instr',None); is_active=getattr(c,'is_active',None); k=getattr(c,'k',None); key=getattr(c,'key',None); label=getattr(c,'label',None); label_what=getattr(c,'label_what',None); lbl=getattr(c,'lbl',None); lbl_surf=getattr(c,'lbl_surf',None); len_v=getattr(c,'len_v',None); lo=getattr(c,'lo',None); loc_v=getattr(c,'loc_v',None); mouse_pos=getattr(c,'mouse_pos',None); n_dist=getattr(c,'n_dist',None); noise_on=getattr(c,'noise_on',None); noise_v=getattr(c,'noise_v',None); nr=getattr(c,'nr',None); nsc_v=getattr(c,'nsc_v',None); nscale_v=getattr(c,'nscale_v',None); on=getattr(c,'on',None); phase_v=getattr(c,'phase_v',None); pick_r=getattr(c,'pick_r',None); picking=getattr(c,'picking',None); pr=getattr(c,'pr',None); prev_px=getattr(c,'prev_px',None); prev_py=getattr(c,'prev_py',None); prev_rect=getattr(c,'prev_rect',None); pt_count=getattr(c,'pt_count',None); px=getattr(c,'px',None); py=getattr(c,'py',None); r=getattr(c,'r',None); r_rect=getattr(c,'r_rect',None); ranges=getattr(c,'ranges',None); rect=getattr(c,'rect',None); redraw_rect=getattr(c,'redraw_rect',None); rem_rect=getattr(c,'rem_rect',None); rev=getattr(c,'rev',None); rev_rect=getattr(c,'rev_rect',None); rot_v=getattr(c,'rot_v',None); row=getattr(c,'row',None); row_h=getattr(c,'row_h',None); rowi=getattr(c,'rowi',None); s0=getattr(c,'s0',None); s1=getattr(c,'s1',None); sc=getattr(c,'sc',None); screen=getattr(c,'screen',None); seed_v=getattr(c,'seed_v',None); sel_count=getattr(c,'sel_count',None); sel_stroke=getattr(c,'sel_stroke',None); sel_strokes=getattr(c,'sel_strokes',None); shape=getattr(c,'shape',None); shape_items=getattr(c,'shape_items',None); shape_labels=getattr(c,'shape_labels',None); smooth_r=getattr(c,'smooth_r',None); smooth_rect=getattr(c,'smooth_rect',None); state=getattr(c,'state',None); stt=getattr(c,'stt',None); style_type=getattr(c,'style_type',None); styles=getattr(c,'styles',None); stype=getattr(c,'stype',None); submode=getattr(c,'submode',None); sv=getattr(c,'sv',None); sv_on=getattr(c,'sv_on',None); t=getattr(c,'t',None); t_rect=getattr(c,'t_rect',None); tog_rect=getattr(c,'tog_rect',None); total_w=getattr(c,'total_w',None); track=getattr(c,'track',None); tt=getattr(c,'tt',None); tx=getattr(c,'tx',None); txt=getattr(c,'txt',None); v=getattr(c,'v',None); val=getattr(c,'val',None); vr=getattr(c,'vr',None); vt=getattr(c,'vt',None); vw=getattr(c,'vw',None); w_rect=getattr(c,'w_rect',None); wave=getattr(c,'wave',None); wi=getattr(c,'wi',None); wlabel=getattr(c,'wlabel',None); wshape_i=getattr(c,'wshape_i',None); x=getattr(c,'x',None); x0=getattr(c,'x0',None); y=getattr(c,'y',None); y0=getattr(c,'y0',None)
    if style_type == "repeat":
        state["displacement_affect_rects"] = {}
        state["wave_shape_prev_rect"] = pygame.Rect(0,0,0,0)
        state["wave_shape_next_rect"] = pygame.Rect(0,0,0,0)
        state["wave_shape_rects"] = {}
        state["wave_formula_rect"] = pygame.Rect(0,0,0,0)
        state["wave_formula_focus"] = False
        state["wave_smooth_rect"] = pygame.Rect(0,0,0,0)
        state["wave_clear_rect"] = pygame.Rect(0,0,0,0)
        state["wave_done_rect"] = pygame.Rect(0,0,0,0)
        state["repeat_pick_curve_rect"] = pygame.Rect(0,0,0,0)
        state["displacement_profile_rects"] = {}
        screen.blit(font_small.render("Repeat curve (drawn pattern)", True, TEXT_COLOR), (x, y)); y += 20
        # Draw box for repeat_points
        BOX_W = 180; BOX_H = 80
        bx = x + 8; by = y + 8
        box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
        state["wave_custom_box_rect"] = box_rect
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
        gap = 4
        bw = (PANEL_W - 40 - gap * 2) // 3
        clr_r = pygame.Rect(x, btns_y, bw, 24)
        smooth_r = pygame.Rect(x + bw + gap, btns_y, bw, 24)
        done_r = pygame.Rect(x + (bw + gap) * 2, btns_y, PANEL_W - 40 - (bw + gap) * 2, 24)
        _button(clr_r, "Clear")
        _button(smooth_r, "Smooth")
        _button(done_r, "Done")
        state["wave_clear_rect"] = clr_r
        state["wave_smooth_rect"] = smooth_r
        state["wave_done_rect"] = done_r
        y += 30
        pick_r = pygame.Rect(x, y, PANEL_W - 40, 24)
        picking = bool(state.get("repeat_pick_mode"))
        _button(pick_r, "Picking curve..." if picking else "Copy Curve As Pattern", active=picking)
        state["repeat_pick_curve_rect"] = pick_r
        y += 30
        _style_slider("Amplitude (%)", "amplitude", float(active_style.get("amplitude", 8.0)), 0.0, 100.0, fmt=lambda v: f"{v:.1f}")
        _style_slider("Frequency", "frequency", float(active_style.get("frequency", 0.25)), 0.01, 5.0, fmt=lambda v: f"{v:.2f}")
        _style_slider("Phase (deg)", "phase", float(active_style.get("phase", 0.0)), 0.0, 360.0, fmt=lambda v: f"{v:.0f}")
        # Reverse / Clamp
        rev_rect = pygame.Rect(x, y, (PANEL_W - 44) // 2, 24)
        clamp_rect = pygame.Rect(rev_rect.right + 4, y, PANEL_W - 40 - rev_rect.w - 4, 24)
        _button(rev_rect, "Reverse", active=bool(active_style.get("reverse")))
        state["wave_reverse_rect"] = rev_rect
        _button(clamp_rect, f"Clamp: {active_style.get('clamp','none')}")
        state["wave_clamp_rect"] = clamp_rect
        y += 30
    _sync_out(c)

def _b2b_thick(c):
    _sync_in(c)
    _style_slider=getattr(c,"_style_slider",None)
    BOX_H=getattr(c,'BOX_H',None); BOX_W=getattr(c,'BOX_W',None); _button=getattr(c,'_button',None); _gap_slider=getattr(c,'_gap_slider',None); _queue_tip=getattr(c,'_queue_tip',None); _sel_curves_panel=getattr(c,'_sel_curves_panel',None); active_style=getattr(c,'active_style',None); affect_items=getattr(c,'affect_items',None); affect_rects=getattr(c,'affect_rects',None); akey=getattr(c,'akey',None); alabel=getattr(c,'alabel',None); amp_v=getattr(c,'amp_v',None); arrow=getattr(c,'arrow',None); bake_rect=getattr(c,'bake_rect',None); bg=getattr(c,'bg',None); bg_col=getattr(c,'bg_col',None); box_rect=getattr(c,'box_rect',None); btn_gap=getattr(c,'btn_gap',None); btn_w=getattr(c,'btn_w',None); btns_y=getattr(c,'btns_y',None); bw=getattr(c,'bw',None); bx=getattr(c,'bx',None); by=getattr(c,'by',None); cap_txt=getattr(c,'cap_txt',None); ci=getattr(c,'ci',None); clamp_labels=getattr(c,'clamp_labels',None); clamp_mode=getattr(c,'clamp_mode',None); clamp_rect=getattr(c,'clamp_rect',None); clr_r=getattr(c,'clr_r',None); col=getattr(c,'col',None); coli=getattr(c,'coli',None); collapsed=getattr(c,'collapsed',None); cols=getattr(c,'cols',None); comp=getattr(c,'comp',None); comp_hidden=getattr(c,'comp_hidden',None); comp_i=getattr(c,'comp_i',None); comps=getattr(c,'comps',None); cp=getattr(c,'cp',None); cur_shape=getattr(c,'cur_shape',None); cut_active=getattr(c,'cut_active',None); cut_rect=getattr(c,'cut_rect',None); cxp=getattr(c,'cxp',None); cyc_t=getattr(c,'cyc_t',None); cyp=getattr(c,'cyp',None); d_rect=getattr(c,'d_rect',None); dist_all=getattr(c,'dist_all',None); done_r=getattr(c,'done_r',None); enabled=getattr(c,'enabled',None); enabled_sl=getattr(c,'enabled_sl',None); finish_instr=getattr(c,'finish_instr',None); fmt=getattr(c,'fmt',None); focused=getattr(c,'focused',None); font=getattr(c,'font',None); font_small=getattr(c,'font_small',None); font_title=getattr(c,'font_title',None); fonts=getattr(c,'fonts',None); frect=getattr(c,'frect',None); freq_v=getattr(c,'freq_v',None); ftxt=getattr(c,'ftxt',None); ftxt_disp=getattr(c,'ftxt_disp',None); fval=getattr(c,'fval',None); gap=getattr(c,'gap',None); gap_val=getattr(c,'gap_val',None); has_dist=getattr(c,'has_dist',None); has_wave_pts=getattr(c,'has_wave_pts',None); hbg=getattr(c,'hbg',None); hdr_rect=getattr(c,'hdr_rect',None); header_label=getattr(c,'header_label',None); help_lines=getattr(c,'help_lines',None); hi=getattr(c,'hi',None); hidden=getattr(c,'hidden',None); hint=getattr(c,'hint',None); hit=getattr(c,'hit',None); i=getattr(c,'i',None); icon_rect=getattr(c,'icon_rect',None); icon_wave=getattr(c,'icon_wave',None); info=getattr(c,'info',None); instr=getattr(c,'instr',None); is_active=getattr(c,'is_active',None); k=getattr(c,'k',None); key=getattr(c,'key',None); label=getattr(c,'label',None); label_what=getattr(c,'label_what',None); lbl=getattr(c,'lbl',None); lbl_surf=getattr(c,'lbl_surf',None); len_v=getattr(c,'len_v',None); lo=getattr(c,'lo',None); loc_v=getattr(c,'loc_v',None); mouse_pos=getattr(c,'mouse_pos',None); n_dist=getattr(c,'n_dist',None); noise_on=getattr(c,'noise_on',None); noise_v=getattr(c,'noise_v',None); nr=getattr(c,'nr',None); nsc_v=getattr(c,'nsc_v',None); nscale_v=getattr(c,'nscale_v',None); on=getattr(c,'on',None); phase_v=getattr(c,'phase_v',None); pick_r=getattr(c,'pick_r',None); picking=getattr(c,'picking',None); pr=getattr(c,'pr',None); prev_px=getattr(c,'prev_px',None); prev_py=getattr(c,'prev_py',None); prev_rect=getattr(c,'prev_rect',None); pt_count=getattr(c,'pt_count',None); px=getattr(c,'px',None); py=getattr(c,'py',None); r=getattr(c,'r',None); r_rect=getattr(c,'r_rect',None); ranges=getattr(c,'ranges',None); rect=getattr(c,'rect',None); redraw_rect=getattr(c,'redraw_rect',None); rem_rect=getattr(c,'rem_rect',None); rev=getattr(c,'rev',None); rev_rect=getattr(c,'rev_rect',None); rot_v=getattr(c,'rot_v',None); row=getattr(c,'row',None); row_h=getattr(c,'row_h',None); rowi=getattr(c,'rowi',None); s0=getattr(c,'s0',None); s1=getattr(c,'s1',None); sc=getattr(c,'sc',None); screen=getattr(c,'screen',None); seed_v=getattr(c,'seed_v',None); sel_count=getattr(c,'sel_count',None); sel_stroke=getattr(c,'sel_stroke',None); sel_strokes=getattr(c,'sel_strokes',None); shape=getattr(c,'shape',None); shape_items=getattr(c,'shape_items',None); shape_labels=getattr(c,'shape_labels',None); smooth_r=getattr(c,'smooth_r',None); smooth_rect=getattr(c,'smooth_rect',None); state=getattr(c,'state',None); stt=getattr(c,'stt',None); style_type=getattr(c,'style_type',None); styles=getattr(c,'styles',None); stype=getattr(c,'stype',None); submode=getattr(c,'submode',None); sv=getattr(c,'sv',None); sv_on=getattr(c,'sv_on',None); t=getattr(c,'t',None); t_rect=getattr(c,'t_rect',None); tog_rect=getattr(c,'tog_rect',None); total_w=getattr(c,'total_w',None); track=getattr(c,'track',None); tt=getattr(c,'tt',None); tx=getattr(c,'tx',None); txt=getattr(c,'txt',None); v=getattr(c,'v',None); val=getattr(c,'val',None); vr=getattr(c,'vr',None); vt=getattr(c,'vt',None); vw=getattr(c,'vw',None); w_rect=getattr(c,'w_rect',None); wave=getattr(c,'wave',None); wi=getattr(c,'wi',None); wlabel=getattr(c,'wlabel',None); wshape_i=getattr(c,'wshape_i',None); x=getattr(c,'x',None); x0=getattr(c,'x0',None); y=getattr(c,'y',None); y0=getattr(c,'y0',None)
    if style_type == "thickness":
        state["displacement_affect_rects"] = {}
        state["wave_shape_prev_rect"] = pygame.Rect(0,0,0,0)
        state["wave_shape_next_rect"] = pygame.Rect(0,0,0,0)
        state["wave_shape_rects"] = {}
        state["wave_formula_rect"] = pygame.Rect(0,0,0,0)
        state["wave_formula_focus"] = False
        state["displacement_profile_rects"] = {}
        screen.blit(font_small.render("Thickness profile (no repetition)", True, TEXT_COLOR), (x, y)); y += 20
        BOX_W = 180; BOX_H = 80
        bx = x + 8; by = y + 8
        box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
        state["wave_custom_box_rect"] = box_rect
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
        gap = 4
        bw = (PANEL_W - 40 - gap * 2) // 3
        clr_r = pygame.Rect(x, btns_y, bw, 24)
        smooth_r = pygame.Rect(x + bw + gap, btns_y, bw, 24)
        done_r = pygame.Rect(x + (bw + gap) * 2, btns_y, PANEL_W - 40 - (bw + gap) * 2, 24)
        _button(clr_r, "Clear")
        _button(smooth_r, "Smooth")
        _button(done_r, "Done")
        state["wave_clear_rect"] = clr_r
        state["wave_smooth_rect"] = smooth_r
        state["wave_done_rect"] = done_r
        y += 30
        pick_r = pygame.Rect(x, y, PANEL_W - 40, 24)
        picking = bool(state.get("repeat_pick_mode"))
        _button(pick_r, "Picking curve..." if picking else "Copy Curve As Pattern", active=picking)
        state["repeat_pick_curve_rect"] = pick_r
        y += 30
        _style_slider("Amplitude (%)", "amplitude", float(active_style.get("amplitude", 8.0)), 0.0, 100.0, fmt=lambda v: f"{v:.1f}")
        rev_rect = pygame.Rect(x, y, (PANEL_W - 44) // 2, 24)
        clamp_rect = pygame.Rect(rev_rect.right + 4, y, PANEL_W - 40 - rev_rect.w - 4, 24)
        _button(rev_rect, "Reverse", active=bool(active_style.get("reverse")))
        state["wave_reverse_rect"] = rev_rect
        _button(clamp_rect, f"Clamp: {active_style.get('clamp','none')}")
        state["wave_clamp_rect"] = clamp_rect
        y += 30
    _sync_out(c)

def _b2b_wave(c):
    _sync_in(c)
    _style_slider=getattr(c,"_style_slider",None)
    BOX_H=getattr(c,'BOX_H',None); BOX_W=getattr(c,'BOX_W',None); _button=getattr(c,'_button',None); _gap_slider=getattr(c,'_gap_slider',None); _queue_tip=getattr(c,'_queue_tip',None); _sel_curves_panel=getattr(c,'_sel_curves_panel',None); active_style=getattr(c,'active_style',None); affect_items=getattr(c,'affect_items',None); affect_rects=getattr(c,'affect_rects',None); akey=getattr(c,'akey',None); alabel=getattr(c,'alabel',None); amp_v=getattr(c,'amp_v',None); arrow=getattr(c,'arrow',None); bake_rect=getattr(c,'bake_rect',None); bg=getattr(c,'bg',None); bg_col=getattr(c,'bg_col',None); box_rect=getattr(c,'box_rect',None); btn_gap=getattr(c,'btn_gap',None); btn_w=getattr(c,'btn_w',None); btns_y=getattr(c,'btns_y',None); bw=getattr(c,'bw',None); bx=getattr(c,'bx',None); by=getattr(c,'by',None); cap_txt=getattr(c,'cap_txt',None); ci=getattr(c,'ci',None); clamp_labels=getattr(c,'clamp_labels',None); clamp_mode=getattr(c,'clamp_mode',None); clamp_rect=getattr(c,'clamp_rect',None); clr_r=getattr(c,'clr_r',None); col=getattr(c,'col',None); coli=getattr(c,'coli',None); collapsed=getattr(c,'collapsed',None); cols=getattr(c,'cols',None); comp=getattr(c,'comp',None); comp_hidden=getattr(c,'comp_hidden',None); comp_i=getattr(c,'comp_i',None); comps=getattr(c,'comps',None); cp=getattr(c,'cp',None); cur_shape=getattr(c,'cur_shape',None); cut_active=getattr(c,'cut_active',None); cut_rect=getattr(c,'cut_rect',None); cxp=getattr(c,'cxp',None); cyc_t=getattr(c,'cyc_t',None); cyp=getattr(c,'cyp',None); d_rect=getattr(c,'d_rect',None); dist_all=getattr(c,'dist_all',None); done_r=getattr(c,'done_r',None); enabled=getattr(c,'enabled',None); enabled_sl=getattr(c,'enabled_sl',None); finish_instr=getattr(c,'finish_instr',None); fmt=getattr(c,'fmt',None); focused=getattr(c,'focused',None); font=getattr(c,'font',None); font_small=getattr(c,'font_small',None); font_title=getattr(c,'font_title',None); fonts=getattr(c,'fonts',None); frect=getattr(c,'frect',None); freq_v=getattr(c,'freq_v',None); ftxt=getattr(c,'ftxt',None); ftxt_disp=getattr(c,'ftxt_disp',None); fval=getattr(c,'fval',None); gap=getattr(c,'gap',None); gap_val=getattr(c,'gap_val',None); has_dist=getattr(c,'has_dist',None); has_wave_pts=getattr(c,'has_wave_pts',None); hbg=getattr(c,'hbg',None); hdr_rect=getattr(c,'hdr_rect',None); header_label=getattr(c,'header_label',None); help_lines=getattr(c,'help_lines',None); hi=getattr(c,'hi',None); hidden=getattr(c,'hidden',None); hint=getattr(c,'hint',None); hit=getattr(c,'hit',None); i=getattr(c,'i',None); icon_rect=getattr(c,'icon_rect',None); icon_wave=getattr(c,'icon_wave',None); info=getattr(c,'info',None); instr=getattr(c,'instr',None); is_active=getattr(c,'is_active',None); k=getattr(c,'k',None); key=getattr(c,'key',None); label=getattr(c,'label',None); label_what=getattr(c,'label_what',None); lbl=getattr(c,'lbl',None); lbl_surf=getattr(c,'lbl_surf',None); len_v=getattr(c,'len_v',None); lo=getattr(c,'lo',None); loc_v=getattr(c,'loc_v',None); mouse_pos=getattr(c,'mouse_pos',None); n_dist=getattr(c,'n_dist',None); noise_on=getattr(c,'noise_on',None); noise_v=getattr(c,'noise_v',None); nr=getattr(c,'nr',None); nsc_v=getattr(c,'nsc_v',None); nscale_v=getattr(c,'nscale_v',None); on=getattr(c,'on',None); phase_v=getattr(c,'phase_v',None); pick_r=getattr(c,'pick_r',None); picking=getattr(c,'picking',None); pr=getattr(c,'pr',None); prev_px=getattr(c,'prev_px',None); prev_py=getattr(c,'prev_py',None); prev_rect=getattr(c,'prev_rect',None); pt_count=getattr(c,'pt_count',None); px=getattr(c,'px',None); py=getattr(c,'py',None); r=getattr(c,'r',None); r_rect=getattr(c,'r_rect',None); ranges=getattr(c,'ranges',None); rect=getattr(c,'rect',None); redraw_rect=getattr(c,'redraw_rect',None); rem_rect=getattr(c,'rem_rect',None); rev=getattr(c,'rev',None); rev_rect=getattr(c,'rev_rect',None); rot_v=getattr(c,'rot_v',None); row=getattr(c,'row',None); row_h=getattr(c,'row_h',None); rowi=getattr(c,'rowi',None); s0=getattr(c,'s0',None); s1=getattr(c,'s1',None); sc=getattr(c,'sc',None); screen=getattr(c,'screen',None); seed_v=getattr(c,'seed_v',None); sel_count=getattr(c,'sel_count',None); sel_stroke=getattr(c,'sel_stroke',None); sel_strokes=getattr(c,'sel_strokes',None); shape=getattr(c,'shape',None); shape_items=getattr(c,'shape_items',None); shape_labels=getattr(c,'shape_labels',None); smooth_r=getattr(c,'smooth_r',None); smooth_rect=getattr(c,'smooth_rect',None); state=getattr(c,'state',None); stt=getattr(c,'stt',None); style_type=getattr(c,'style_type',None); styles=getattr(c,'styles',None); stype=getattr(c,'stype',None); submode=getattr(c,'submode',None); sv=getattr(c,'sv',None); sv_on=getattr(c,'sv_on',None); t=getattr(c,'t',None); t_rect=getattr(c,'t_rect',None); tog_rect=getattr(c,'tog_rect',None); total_w=getattr(c,'total_w',None); track=getattr(c,'track',None); tt=getattr(c,'tt',None); tx=getattr(c,'tx',None); txt=getattr(c,'txt',None); v=getattr(c,'v',None); val=getattr(c,'val',None); vr=getattr(c,'vr',None); vt=getattr(c,'vt',None); vw=getattr(c,'vw',None); w_rect=getattr(c,'w_rect',None); wave=getattr(c,'wave',None); wi=getattr(c,'wi',None); wlabel=getattr(c,'wlabel',None); wshape_i=getattr(c,'wshape_i',None); x=getattr(c,'x',None); x0=getattr(c,'x0',None); y=getattr(c,'y',None); y0=getattr(c,'y0',None)
    if True:
        state["displacement_affect_rects"] = {}
        # Wave style UI (existing behavior)
        wave = active_style
        # ---- shape selector ----
        screen.blit(font_small.render("Shape", True, TEXT_COLOR), (x, y)); y += 20
        shape_items = list(WAVE_SHAPE_LABELS)
        shape_labels = {k: lbl for k, lbl in shape_items}
        cur_shape = shape if shape in shape_labels else shape_items[0][0]
        btn_w = 28
        vw = PANEL_W - 40 - btn_w * 2 - 8
        pr = pygame.Rect(x, y, btn_w, 28)
        vr = pygame.Rect(x + btn_w + 4, y, vw, 28)
        nr = pygame.Rect(vr.right + 4, y, btn_w, 28)
        state["wave_shape_prev_rect"] = pr
        state["wave_shape_next_rect"] = nr
        state["wave_shape_rects"] = {}
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
        y += 32

        # Formula input (contextual: only for the formula shape)
        state["wave_formula_rect"] = pygame.Rect(0,0,0,0)
        if shape == "formula":
            screen.blit(font_small.render("Formula (x=p, t,s)", True, TEXT_COLOR), (x, y)); y += 18
            frect = pygame.Rect(x, y, PANEL_W - 40, 26)
            state["wave_formula_rect"] = frect
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
        state["wave_custom_box_rect"] = pygame.Rect(0, 0, 0, 0)
        if shape == "custom":
            bx = x + 8
            by = y + 8
            box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
            state["wave_custom_box_rect"] = box_rect
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
            smooth_rect = pygame.Rect(bx, by + BOX_H + 6, 74, 20)
            state["wave_smooth_rect"] = smooth_rect
            _button(smooth_rect, "Smooth", enabled=has_wave_pts)
            if has_wave_pts:
                pt_count = f"{len(cp)} samples"
            else:
                pt_count = "hold & drag to draw"
            instr = font_small.render(f"Custom: {pt_count}", True, TEXT_DISABLED)
            screen.blit(instr, (smooth_rect.right + 8, smooth_rect.y + 3))
            finish_instr = font_small.render("Esc to finish", True, TEXT_DISABLED)
            screen.blit(finish_instr, (smooth_rect.right + 8, smooth_rect.y + 18))
            y = by + BOX_H + 34
            state["wave_custom_draw"] = not bool(state.get("wave_custom_finished", False))

        screen.blit(font_small.render("Parameters", True, TEXT_COLOR), (x, y)); y += 20
        amp_v = float(wave.get("amplitude", 0.0))
        freq_v = float(wave.get("frequency", 0.0))
        phase_v = float(wave.get("phase", 0.0))
        noise_v = float(wave.get("noise", 0.0))
        seed_v = int(wave.get("seed", 0) or 0)
        nscale_v = float(wave.get("noise_scale", 2.0))
        noise_on = abs(noise_v) > 1e-6
        _style_slider("Amplitude", "amplitude", amp_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
        _style_slider("Frequency", "frequency", freq_v, 0.01, 1.0, fmt=lambda v: f"{v:.2f}")
        if shape == "noise":
            _style_slider("Phase", "phase", phase_v, 0.0, 360.0, fmt=lambda v: str(int(round(v))), enabled_sl=False)
            _style_slider("Noise scale", "noise_scale", nscale_v, 0.2, 10.0, fmt=lambda v: f"{v:.1f}")
            _style_slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
        else:
            _style_slider("Phase", "phase", phase_v, 0.0, 360.0, fmt=lambda v: str(int(round(v))))
            if noise_on:
                _style_slider("Noise", "noise", noise_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
                _style_slider("Noise scale", "noise_scale", nscale_v, 0.2, 10.0, fmt=lambda v: f"{v:.1f}")
                _style_slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
        # Reverse toggle: invert the wave (-f(x))
        rev = bool(wave.get("reverse"))
        rev_rect = pygame.Rect(x, y, PANEL_W - 40, 22)
        state["wave_reverse_rect"] = rev_rect
        _button(rev_rect, f"Reverse wave -f(x): {'ON' if rev else 'OFF'}", active=rev)
        y += 26
        # Clamp: apply the curve on only one side or the other
        clamp_mode = str(wave.get("clamp", "none") or "none").lower()
        if clamp_mode not in ("none", "positive", "negative"):
            clamp_mode = "none"
        clamp_labels = {"none": "Off", "positive": "One side (+)", "negative": "One side (-)"}
        clamp_rect = pygame.Rect(x, y, PANEL_W - 40, 22)
        state["wave_clamp_rect"] = clamp_rect
        _button(clamp_rect, f"Clamp curve: {clamp_labels[clamp_mode]}",
                active=clamp_mode != "none")
        y += 26
        y += 4
    _sync_out(c)
