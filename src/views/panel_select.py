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
    font, font_small, font_title = fonts
    help_lines = []
    # Selection mode: transform operations and modern color selection
    sel_strokes = state.get("selected_strokes", set())
    sel_count = len(sel_strokes)
    # Submode: Transform / Edit Nodes / Curve
    submode = state.get("selection_submode", "transform")
    modes = (("Transform", "transform"), ("Nodes", "nodes"), ("Curve", "curve"))
    mode_labels = {k: lbl for lbl, k in modes}
    screen.blit(font_small.render("Mode", True, MUTED_COLOR), (x, y + 5))
    btn_w = 28
    vx = x + 44
    vw = PANEL_W - 40 - 44 - btn_w * 2 - 8
    pr = pygame.Rect(vx, y, btn_w, 28)
    vr = pygame.Rect(vx + btn_w + 4, y, vw, 28)
    nr = pygame.Rect(vr.right + 4, y, btn_w, 28)
    state["nodes_mode_prev_rect"] = pr
    state["nodes_mode_next_rect"] = nr
    state["nodes_toggle_rect"] = pygame.Rect(0, 0, 0, 0)
    _button(pr, "<", font_=font_small)
    _button(vr, mode_labels.get(submode, "Transform"))
    _button(nr, ">", font_=font_small)
    _queue_tip(vr, None, "Selection mode (N to cycle)")
    y += 34
    # Eyedropper (pick style) - tool within selection panel
    pick_active = bool(state.get("eyedropper_pick"))
    ed_rect = pygame.Rect(x, y, PANEL_W - 40, 28)
    state["eyedropper_rect"] = ed_rect
    ed_label = "Eyedropper: click a stroke..." if pick_active else "Eyedropper - pick style (I)"
    _button(ed_rect, ed_label, active=pick_active, icon="eyedropper")
    _queue_tip(ed_rect, "eyedropper")
    y += 32
    if pick_active:
        hint = font_small.render("Samples stroke/fill color, size, wave effects", True, MUTED_COLOR)
        screen.blit(hint, (x, y)); y += 18

    sel_stroke = state.get("selected_obj")
    # Elevation / z-order controls (transform mode)
    state.setdefault("elev_front_rect", pygame.Rect(0,0,0,0))
    state.setdefault("elev_forward_rect", pygame.Rect(0,0,0,0))
    state.setdefault("elev_backward_rect", pygame.Rect(0,0,0,0))
    state.setdefault("elev_back_rect", pygame.Rect(0,0,0,0))
    if submode == "transform" and sel_count > 0:
        screen.blit(font_small.render("Elevation", True, TEXT_COLOR), (x, y)); y += 20
        gap = 6
        bw = (PANEL_W - 40 - gap) // 2
        labels = [("To Front", "elev_front_rect", "elev_front"), ("Forward", "elev_forward_rect", "elev_forward"),
                  ("Backward", "elev_backward_rect", "elev_backward"), ("To Back", "elev_back_rect", "elev_back")]
        for i, (label, key, icon_name) in enumerate(labels):
            row, col = divmod(i, 2)
            r = pygame.Rect(x + col * (bw + gap), y + row * 28, bw, 24)
            state[key] = r
            _button(r, label, icon=icon_name)
            _queue_tip(r, icon_name)
        y += 2 * 28 + 8
    else:
        state["elev_front_rect"] = pygame.Rect(0,0,0,0)
        state["elev_forward_rect"] = pygame.Rect(0,0,0,0)
        state["elev_backward_rect"] = pygame.Rect(0,0,0,0)
        state["elev_back_rect"] = pygame.Rect(0,0,0,0)

    # Text controls: shown when exactly one editable text object is selected.
    for _k in ("text_edit_rect", "text_font_rect",
               "text_size_minus_rect", "text_size_plus_rect",
               "text_on_path_rect", "text_off_path_rect"):
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    _txt_obj = sel_stroke if sel_count == 1 and isinstance(sel_stroke, dict) else None
    if _txt_obj is not None and _txt_obj.get("is_text"):
        screen.blit(font_small.render("Text", True, TEXT_COLOR), (x, y)); y += 20
        content = str(_txt_obj.get("text_content", ""))
        shown = content if len(content) <= 26 else content[:25] + "..."
        er = pygame.Rect(x, y, PANEL_W - 40, 24)
        state["text_edit_rect"] = er
        _button(er, f"Edit: \"{shown}\"")
        _queue_tip(er, None, "Re-edit text content")
        y += 28
        fr = pygame.Rect(x, y, PANEL_W - 40, 24)
        state["text_font_rect"] = fr
        _button(fr, f"Font: {_txt_obj.get('font_family', 'Sans')}")
        _queue_tip(fr, None, "Cycle font family")
        y += 28
        fgap = 6
        fhalf = (PANEL_W - 40 - fgap) // 2
        smr = pygame.Rect(x, y, fhalf, 24)
        spr = pygame.Rect(x + fhalf + fgap, y, fhalf, 24)
        state["text_size_minus_rect"] = smr
        state["text_size_plus_rect"] = spr
        _button(smr, "A-", font_=font_small)
        _button(spr, "A+", font_=font_small)
        _queue_tip(smr, None, "Decrease font size")
        _queue_tip(spr, None, "Increase font size")
        y += 28
        sz = font_small.render(f"Size: {int(round(float(_txt_obj.get('font_size', 36))))}",
                               True, MUTED_COLOR)
        screen.blit(sz, (x, y)); y += 18
        # Text on path
        onp = _txt_obj.get("text_path")
        if isinstance(onp, dict) and onp.get("segs"):
            opr = pygame.Rect(x, y, PANEL_W - 40, 24)
            state["text_off_path_rect"] = opr
            _button(opr, "Remove from Path")
            _queue_tip(opr, None, "Reflow text back to a straight baseline")
            y += 28
        else:
            state["text_off_path_rect"] = pygame.Rect(0, 0, 0, 0)
        # Put on Path shown when 2 selected (text + path) - handled via state hint or selection info
        _can_put_on_path = False
        if sel_count == 2:
            _all_strokes = state.get("strokes")
            if isinstance(_all_strokes, list):
                sel_list = [i for i in sorted(sel_strokes) if 0 <= i < len(_all_strokes)]
                if len(sel_list) == 2:
                    a, b = _all_strokes[sel_list[0]], _all_strokes[sel_list[1]]
                    if isinstance(a, dict) and isinstance(b, dict):
                        if (a.get("is_text") and not b.get("is_text")) or (b.get("is_text") and not a.get("is_text")):
                            _can_put_on_path = True
        if _can_put_on_path:
            ppr = pygame.Rect(x, y, PANEL_W - 40, 24)
            state["text_on_path_rect"] = ppr
            _button(ppr, "Put on Path")
            _queue_tip(ppr, None, "Flow this text along the other selected path")
            y += 28
        else:
            state["text_on_path_rect"] = pygame.Rect(0, 0, 0, 0)
    else:
        for _k in ("text_edit_rect", "text_font_rect",
                   "text_size_minus_rect", "text_size_plus_rect",
                   "text_on_path_rect", "text_off_path_rect"):
            state[_k] = pygame.Rect(0, 0, 0, 0)

    # Boolean operations (transform mode, 2+ selected shapes)
    BOOL_KEYS = ("bool_union_rect", "bool_intersect_rect",
                 "bool_subtract_rect", "bool_exclude_rect")
    for _k in BOOL_KEYS:
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    if submode == "transform" and sel_count >= 2:
        screen.blit(font_small.render("Boolean", True, TEXT_COLOR), (x, y)); y += 20
        bgap = 6
        bwidth = (PANEL_W - 40 - bgap) // 2
        for bi, (blabel, bkey, bicon) in enumerate([
                ("Union", "bool_union_rect", "union"),
                ("Intersect", "bool_intersect_rect", "intersect"),
                ("Subtract", "bool_subtract_rect", "subtract"),
                ("Exclude", "bool_exclude_rect", "exclude")]):
            br = pygame.Rect(x + (bi % 2) * (bwidth + bgap),
                             y + (bi // 2) * 28, bwidth, 24)
            state[bkey] = br
            _button(br, blabel, icon=bicon)
            _queue_tip(br, bicon)
        y += 28 * 2 + 8
    else:
        for _k in BOOL_KEYS:
            state[_k] = pygame.Rect(0, 0, 0, 0)

    # Mirror (flip) and alignment tools (transform mode)
    for _k in ("mirror_h_rect", "mirror_v_rect",
               "align_left_rect", "align_hcenter_rect", "align_right_rect",
               "align_top_rect", "align_vmiddle_rect", "align_bottom_rect"):
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    # Numeric precision transform inputs (X/Y/W/H/Rotation).
    _xform_keys = ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                   "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                   "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                   "xform_rm_rect", "xform_rp_rect")
    for _k in _xform_keys:
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    if submode == "transform" and sel_count >= 1 and state.get("selection_bbox"):
        bb = state.get("selection_bbox")
        bx0, by0, bx1, by1 = bb
        bw, bh = max(0.0, bx1 - bx0), max(0.0, by1 - by0)
        vals = {"x": bx0, "y": by0, "w": bw, "h": bh, "r": 0.0}
        focus = state.get("xform_field_focus")
        buf = str(state.get("xform_field_buffer", ""))
        screen.blit(font_small.render("Transform", True, TEXT_COLOR), (x, y)); y += 20
        row_h = 24
        gap = 4
        btn_w = 22
        label_w = 18
        val_w = PANEL_W - 40 - label_w - btn_w * 2 - gap * 3
        defs = [("X", "x"), ("Y", "y"), ("W", "w"), ("H", "h"), ("R", "r")]
        for i, (lbl, key) in enumerate(defs):
            ry = y + i * (row_h + 4)
            screen.blit(font_small.render(lbl, True, MUTED_COLOR), (x, ry + 4))
            minus_r = pygame.Rect(x + label_w, ry, btn_w, row_h)
            val_r = pygame.Rect(minus_r.right + gap, ry, val_w, row_h)
            plus_r = pygame.Rect(val_r.right + gap, ry, btn_w, row_h)
            state[f"xform_{key}m_rect"] = minus_r
            state[f"xform_{key}_rect"] = val_r
            state[f"xform_{key}p_rect"] = plus_r
            _button(minus_r, "-", font_=font_small)
            _button(plus_r, "+", font_=font_small)
            active = (focus == key)
            bg = SURFACE_SUBTLE if not active else BUTTON_ACTIVE_BG
            border = ACCENT if active else PANEL_BORDER
            pygame.draw.rect(screen, bg, val_r, border_radius=RADIUS_SM)
            pygame.draw.rect(screen, border, val_r, width=BORDER_WIDTH_ACTIVE if active else BORDER_WIDTH, border_radius=RADIUS_SM)
            if active:
                disp = buf + "|"
            else:
                v = vals[key]
                disp = f"{v:.1f}" if key != "r" else f"{v:.0f}°"
            txt = font_small.render(str(disp), True, TEXT_COLOR)
            screen.blit(txt, (val_r.x + 6, val_r.y + 4))
        y += len(defs) * (row_h + 4) + 4
    else:
        for _k in _xform_keys:
            state[_k] = pygame.Rect(0, 0, 0, 0)

    if submode == "transform" and sel_count >= 1:
        screen.blit(font_small.render("Flip", True, TEXT_COLOR), (x, y)); y += 20
        mgap = 6
        mwidth = (PANEL_W - 40 - mgap) // 2
        for mi, (mlabel, mkey, icon_name) in enumerate([
                ("Horizontal", "mirror_h_rect", "flip_h"),
                ("Vertical", "mirror_v_rect", "flip_v")]):
            mr = pygame.Rect(x + mi * (mwidth + mgap), y, mwidth, 24)
            state[mkey] = mr
            _button(mr, mlabel, icon=icon_name)
            _queue_tip(mr, icon_name)
        y += 24 + 8

        screen.blit(font_small.render("Align", True, TEXT_COLOR), (x, y)); y += 20
        agap = 6
        aw = (PANEL_W - 40 - 2 * agap) // 3
        align_defs = [
            ("Left", "align_left_rect", "align_left"),
            ("Center", "align_hcenter_rect", "align_hcenter"),
            ("Right", "align_right_rect", "align_right"),
            ("Top", "align_top_rect", "align_top"),
            ("Middle", "align_vmiddle_rect", "align_vmiddle"),
            ("Bottom", "align_bottom_rect", "align_bottom"),
        ]
        for ai, (_alabel, akey, icon_name) in enumerate(align_defs):
            row, col = divmod(ai, 3)
            ar = pygame.Rect(x + col * (aw + agap), y + row * 26, aw, 22)
            state[akey] = ar
            _button(ar, "", icon=icon_name)
            _queue_tip(ar, icon_name)
        y += 2 * 26 + 8
    else:
        state["mirror_h_rect"] = pygame.Rect(0, 0, 0, 0)
        state["mirror_v_rect"] = pygame.Rect(0, 0, 0, 0)
        state["align_left_rect"] = pygame.Rect(0, 0, 0, 0)
        state["align_hcenter_rect"] = pygame.Rect(0, 0, 0, 0)
        state["align_right_rect"] = pygame.Rect(0, 0, 0, 0)
        state["align_top_rect"] = pygame.Rect(0, 0, 0, 0)
        state["align_vmiddle_rect"] = pygame.Rect(0, 0, 0, 0)
        state["align_bottom_rect"] = pygame.Rect(0, 0, 0, 0)

    # Even distribution (transform mode, 3+ selected shapes).
    DIST_KEYS = ("distribute_h_rect", "distribute_v_rect")
    for _k in DIST_KEYS:
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    if submode == "transform" and sel_count >= 3:
        screen.blit(font_small.render("Distribute", True, TEXT_COLOR), (x, y)); y += 20
        dgap = 6
        dwidth = (PANEL_W - 40 - dgap) // 2
        for di, (dlabel, dkey) in enumerate([
                ("Horizontal", "distribute_h_rect"),
                ("Vertical", "distribute_v_rect")]):
            dr = pygame.Rect(x + di * (dwidth + dgap), y, dwidth, 24)
            state[dkey] = dr
            _button(dr, dlabel)
            _queue_tip(dr, None, f"{dlabel} spacing")
        y += 32
    else:
        for _k in DIST_KEYS:
            state[_k] = pygame.Rect(0, 0, 0, 0)

    # Curve/stroke-edit controls
    state.setdefault("curve_hide_rect", pygame.Rect(0,0,0,0))
    state.setdefault("curve_redraw_rect", pygame.Rect(0,0,0,0))
    state.setdefault("curve_cut_rect", pygame.Rect(0,0,0,0))
    state.setdefault("curve_join_rect", pygame.Rect(0,0,0,0))

    # Path editing commands (Nodes mode, single selected path).
    PATH_KEYS = ("path_close_rect", "path_reverse_rect", "path_add_rect",
                 "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                 "path_expand_rect")
    for _k in PATH_KEYS:
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
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
    elif submode == "curve" and sel_count == 1 and sel_stroke is not None:
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
                elif style_type == "repeat":
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
                elif style_type == "thickness":
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
                else:
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
    else:
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
        state["stroke_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in presets]
        state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in presets]
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
            state["tab_fill_rect"] = pygame.Rect(0,0,0,0)
            state["nofill_rect"] = pygame.Rect(0,0,0,0)
            state["fill_type_rects"] = {}
            state["fill_stop_rects"] = {}
            state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
            state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
            state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
            if not stroke_color_enabled:
                state["tab_stroke_rect"] = pygame.Rect(0,0,0,0)
        if not (stroke_color_enabled or fill_enabled):
            state["sv_rect"] = pygame.Rect(0,0,0,0)
            state["hue_rect"] = pygame.Rect(0,0,0,0)
            state["alpha_rect"] = pygame.Rect(0,0,0,0)
            state["stroke_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
            state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
            state["fill_type_rects"] = {}
            state["fill_stop_rects"] = {}
            state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
            state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
            state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
        elif component_stroke_enabled and not fill_enabled:
            # only stroke color editable for selected curve; fill swatches/controls off
            state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
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

    return y, help_lines
