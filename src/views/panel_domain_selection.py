"""View: panel_select split parts (SRP)."""
from panel_rects import publish_rect  # noqa: E402
from views.panel_sections import clear_section, draw_section_header, is_open  # noqa: E402

import math
import pygame
import config as cfg
from config import *
from controllers.coordinates import clamp
from models.geometry import hsv_to_rgb
from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip  # noqa: E402
from views.widgets import (  # noqa: E402
    draw_button, draw_card, draw_color_swatch as draw_swatch, draw_hue_cursor,
    draw_picker_cursor, draw_slider_knob, draw_toggle, draw_track,
    to_screen_rgb,
)

# Transform-field nudge arrows. font_small has real glyphs for both, so the
# steppers read as left/right controls rather than generic minus/plus signs.
XFORM_ARROW_LEFT = chr(0x25C0)   # ◀
XFORM_ARROW_RIGHT = chr(0x25B6)  # ▶

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

BOOL_KEYS = ("bool_union_rect", "bool_intersect_rect",
             "bool_subtract_rect", "bool_exclude_rect")
_xform_keys = ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
               "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
               "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
               "xform_rm_rect", "xform_rp_rect")
DIST_KEYS = ("distribute_h_rect", "distribute_v_rect")
PATH_KEYS = ("path_close_rect", "path_reverse_rect", "path_add_rect",
             "path_delete_rect", "path_smooth_rect", "path_corner_rect",
             "path_expand_rect")
APPEAR_KEYS = ("obj_opacity_rect", "shadow_toggle_rect",
               "shadow_blur_minus_rect", "shadow_blur_plus_rect")

def render_selection_a(screen, fonts, mouse_pos, state, x, y, _button, _queue_tip, help_lines,
                       sel_strokes, sel_count, submode, sel_stroke):
    """Explicit-contract render for selection panel section A."""
    font, font_small, font_title = fonts
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
    vw = PANEL_W - 40 - 44 - btn_w * 2 - MIN_ELEMENT_SPACING * 2
    pr = pygame.Rect(vx, y, btn_w, 28)
    vr = pygame.Rect(vx + btn_w + MIN_ELEMENT_SPACING, y, vw, 28)
    nr = pygame.Rect(vr.right + MIN_ELEMENT_SPACING, y, btn_w, 28)
    publish_rect(state, "nodes_mode_prev_rect", pr)
    publish_rect(state, "nodes_mode_next_rect", nr)
    publish_rect(state, "nodes_toggle_rect", pygame.Rect(0, 0, 0, 0))
    _button(pr, "<", font_=font_small)
    _button(vr, mode_labels.get(submode, "Transform"))
    _button(nr, ">", font_=font_small)
    _queue_tip(vr, None, "Selection mode (N to cycle)")
    y += 28 + MIN_ELEMENT_SPACING
    # Eyedropper (pick style) - tool within selection panel
    pick_active = bool(state.get("eyedropper_pick"))
    ed_rect = pygame.Rect(x, y, PANEL_W - 40, 28)
    publish_rect(state, "eyedropper_rect", ed_rect)
    ed_label = "Eyedropper: click a stroke..." if pick_active else "Eyedropper - pick style (I)"
    _button(ed_rect, ed_label, active=pick_active, icon="eyedropper")
    _queue_tip(ed_rect, "eyedropper")
    y += 28 + MIN_ELEMENT_SPACING

    # Secondary arrangement actions are grouped behind one header. Transform
    # values stay in their own always-open section below.
    arrange_open = False
    if submode == "transform" and sel_count > 0:
        y, arrange_open = draw_section_header(
            screen, font_small, mouse_pos, state, x, y,
            "selection_arrange", "Arrange", width=PANEL_W - 40)
    else:
        clear_section(state, "selection_arrange")
    if pick_active:
            hint = font_small.render("Samples stroke/fill color, size, wave effects", True, MUTED_COLOR)
            screen.blit(hint, (x, y)); y += 18

    sel_stroke = state.get("selected_obj")
    # Elevation / z-order controls (transform mode)
    state.setdefault("elev_front_rect", pygame.Rect(0,0,0,0))
    state.setdefault("elev_forward_rect", pygame.Rect(0,0,0,0))
    state.setdefault("elev_backward_rect", pygame.Rect(0,0,0,0))
    state.setdefault("elev_back_rect", pygame.Rect(0,0,0,0))
    if arrange_open and submode == "transform" and sel_count > 0:
            screen.blit(font_small.render("Elevation", True, TEXT_COLOR), (x, y)); y += 20
            gap = MIN_ELEMENT_SPACING
            bw = (PANEL_W - 40 - gap) // 2
            row_pitch = 24 + MIN_ELEMENT_SPACING
            labels = [("To Front", "elev_front_rect", "elev_front"), ("Forward", "elev_forward_rect", "elev_forward"),
                      ("Backward", "elev_backward_rect", "elev_backward"), ("To Back", "elev_back_rect", "elev_back")]
            for i, (label, key, icon_name) in enumerate(labels):
                row, col = divmod(i, 2)
                r = pygame.Rect(x + col * (bw + gap), y + row * row_pitch, bw, 24)
                state[key] = r
                _button(r, label, icon=icon_name)
                _queue_tip(r, icon_name)
            y += 2 * row_pitch + MIN_ELEMENT_SPACING
    else:
            publish_rect(state, "elev_front_rect", pygame.Rect(0,0,0,0))
            publish_rect(state, "elev_forward_rect", pygame.Rect(0,0,0,0))
            publish_rect(state, "elev_backward_rect", pygame.Rect(0,0,0,0))
            publish_rect(state, "elev_back_rect", pygame.Rect(0,0,0,0))

    # Text controls: shown when exactly one editable text object is selected.
    for _k in ("text_edit_rect", "text_font_rect",
                   "text_size_minus_rect", "text_size_plus_rect",
                   "text_on_path_rect", "text_off_path_rect"):
            state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    _txt_obj = sel_stroke if sel_count == 1 and isinstance(sel_stroke, dict) else None
    _text_active = _txt_obj is not None and bool(_txt_obj.get("is_text"))
    _text_open = False
    if _text_active:
            y, _text_open = draw_section_header(
                screen, font_small, mouse_pos, state, x, y,
                "selection_text", "Text", width=PANEL_W - 40)
    if _text_active and _text_open:
            content = str(_txt_obj.get("text_content", ""))
            shown = content if len(content) <= 26 else content[:25] + "..."
            er = pygame.Rect(x, y, PANEL_W - 40, 24)
            publish_rect(state, "text_edit_rect", er)
            _button(er, f"Edit: \"{shown}\"")
            _queue_tip(er, None, "Re-edit text content")
            y += 24 + MIN_ELEMENT_SPACING
            fr = pygame.Rect(x, y, PANEL_W - 40, 24)
            publish_rect(state, "text_font_rect", fr)
            _button(fr, f"Font: {_txt_obj.get('font_family', 'Sans')}")
            _queue_tip(fr, None, "Cycle font family")
            y += 24 + MIN_ELEMENT_SPACING
            fgap = MIN_ELEMENT_SPACING
            fhalf = (PANEL_W - 40 - fgap) // 2
            smr = pygame.Rect(x, y, fhalf, 24)
            spr = pygame.Rect(x + fhalf + fgap, y, fhalf, 24)
            publish_rect(state, "text_size_minus_rect", smr)
            publish_rect(state, "text_size_plus_rect", spr)
            _button(smr, "A-", font_=font_small)
            _button(spr, "A+", font_=font_small)
            _queue_tip(smr, None, "Decrease font size")
            _queue_tip(spr, None, "Increase font size")
            y += 24 + MIN_ELEMENT_SPACING
            sz = font_small.render(f"Size: {int(round(float(_txt_obj.get('font_size', 36))))}",
                                   True, MUTED_COLOR)
            screen.blit(sz, (x, y)); y += 18
            # Text on path
            onp = _txt_obj.get("text_path")
            if isinstance(onp, dict) and onp.get("segs"):
                opr = pygame.Rect(x, y, PANEL_W - 40, 24)
                publish_rect(state, "text_off_path_rect", opr)
                _button(opr, "Remove from Path")
                _queue_tip(opr, None, "Reflow text back to a straight baseline")
                y += 24 + MIN_ELEMENT_SPACING
            else:
                publish_rect(state, "text_off_path_rect", pygame.Rect(0, 0, 0, 0))
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
                publish_rect(state, "text_on_path_rect", ppr)
                _button(ppr, "Put on Path")
                _queue_tip(ppr, None, "Flow this text along the other selected path")
                y += 24 + MIN_ELEMENT_SPACING
            else:
                publish_rect(state, "text_on_path_rect", pygame.Rect(0, 0, 0, 0))
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
    if arrange_open and submode == "transform" and sel_count >= 2:
            screen.blit(font_small.render("Boolean", True, TEXT_COLOR), (x, y)); y += 20
            bgap = MIN_ELEMENT_SPACING
            bwidth = (PANEL_W - 40 - bgap) // 2
            row_pitch = 24 + MIN_ELEMENT_SPACING
            for bi, (blabel, bkey, bicon) in enumerate([
                    ("Union", "bool_union_rect", "union"),
                    ("Intersect", "bool_intersect_rect", "intersect"),
                    ("Subtract", "bool_subtract_rect", "subtract"),
                    ("Exclude", "bool_exclude_rect", "exclude")]):
                br = pygame.Rect(x + (bi % 2) * (bwidth + bgap),
                                 y + (bi // 2) * row_pitch, bwidth, 24)
                state[bkey] = br
                _button(br, blabel, icon=bicon)
                _queue_tip(br, bicon)
            y += 2 * row_pitch + MIN_ELEMENT_SPACING
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
    _xform_open = False
    if submode == "transform" and sel_count >= 1 and state.get("selection_bbox"):
            y, _xform_open = draw_section_header(
                screen, font_small, mouse_pos, state, x, y,
                "selection_transform", "Transform", width=PANEL_W - 40)
    if _xform_open and submode == "transform" and sel_count >= 1 and state.get("selection_bbox"):
            bb = state.get("selection_bbox")
            bx0, by0, bx1, by1 = bb
            bw, bh = max(0.0, bx1 - bx0), max(0.0, by1 - by0)
            vals = {"x": bx0, "y": by0, "w": bw, "h": bh, "r": 0.0}
            focus = state.get("xform_field_focus")
            buf = str(state.get("xform_field_buffer", ""))
            # Compact two-column grid: X/Y, W/H, R. Three rows instead of five
            # keep every field immediately visible while honouring the 8px gap.
            row_h = DRAG_FIELD_H
            gap = MIN_ELEMENT_SPACING
            row_pitch = row_h + MIN_ELEMENT_SPACING
            col_gap = MIN_ELEMENT_SPACING
            cell_w = (PANEL_W - 40 - col_gap) // 2
            btn_w = 18
            label_w = 14
            val_w = cell_w - label_w - btn_w * 2 - gap * 2
            defs = [("X", "x"), ("Y", "y"), ("W", "w"), ("H", "h"), ("R", "r")]
            for i, (lbl, key) in enumerate(defs):
                row, col = divmod(i, 2)
                cx = x + col * (cell_w + col_gap)
                ry = y + row * row_pitch
                screen.blit(font_small.render(lbl, True, MUTED_COLOR), (cx, ry + 4))
                minus_r = pygame.Rect(cx + label_w, ry, btn_w, row_h)
                val_r = pygame.Rect(minus_r.right + gap, ry, val_w, row_h)
                plus_r = pygame.Rect(val_r.right + gap, ry, btn_w, row_h)
                state[f"xform_{key}m_rect"] = minus_r
                state[f"xform_{key}_rect"] = val_r
                state[f"xform_{key}p_rect"] = plus_r
                _button(minus_r, XFORM_ARROW_LEFT, font_=font_small)
                _button(plus_r, XFORM_ARROW_RIGHT, font_=font_small)
                active = (focus == key)
                bg = SURFACE_SUBTLE if not active else ACTIVE_BG
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
            y += 3 * row_pitch + MIN_ELEMENT_SPACING
    else:
            for _k in _xform_keys:
                state[_k] = pygame.Rect(0, 0, 0, 0)

    if arrange_open and submode == "transform" and sel_count >= 1:
            screen.blit(font_small.render("Flip", True, TEXT_COLOR), (x, y)); y += 20
            mgap = MIN_ELEMENT_SPACING
            mwidth = (PANEL_W - 40 - mgap) // 2
            for mi, (mlabel, mkey, icon_name) in enumerate([
                    ("Horizontal", "mirror_h_rect", "flip_h"),
                    ("Vertical", "mirror_v_rect", "flip_v")]):
                mr = pygame.Rect(x + mi * (mwidth + mgap), y, mwidth, 24)
                state[mkey] = mr
                _button(mr, mlabel, icon=icon_name)
                _queue_tip(mr, icon_name)
            y += 24 + MIN_ELEMENT_SPACING

            screen.blit(font_small.render("Align", True, TEXT_COLOR), (x, y)); y += 20
            agap = MIN_ELEMENT_SPACING
            aw = (PANEL_W - 40 - 2 * agap) // 3
            align_defs = [
                ("Left", "align_left_rect", "align_left"),
                ("Center", "align_hcenter_rect", "align_hcenter"),
                ("Right", "align_right_rect", "align_right"),
                ("Top", "align_top_rect", "align_top"),
                ("Middle", "align_vmiddle_rect", "align_vmiddle"),
                ("Bottom", "align_bottom_rect", "align_bottom"),
            ]
            row_pitch = 22 + MIN_ELEMENT_SPACING
            for ai, (_alabel, akey, icon_name) in enumerate(align_defs):
                row, col = divmod(ai, 3)
                ar = pygame.Rect(x + col * (aw + agap), y + row * row_pitch, aw, 22)
                state[akey] = ar
                _button(ar, "", icon=icon_name)
                _queue_tip(ar, icon_name)
            y += 2 * row_pitch + MIN_ELEMENT_SPACING
    else:
            publish_rect(state, "mirror_h_rect", pygame.Rect(0, 0, 0, 0))
            publish_rect(state, "mirror_v_rect", pygame.Rect(0, 0, 0, 0))
            publish_rect(state, "align_left_rect", pygame.Rect(0, 0, 0, 0))
            publish_rect(state, "align_hcenter_rect", pygame.Rect(0, 0, 0, 0))
            publish_rect(state, "align_right_rect", pygame.Rect(0, 0, 0, 0))
            publish_rect(state, "align_top_rect", pygame.Rect(0, 0, 0, 0))
            publish_rect(state, "align_vmiddle_rect", pygame.Rect(0, 0, 0, 0))
            publish_rect(state, "align_bottom_rect", pygame.Rect(0, 0, 0, 0))

    # Even distribution (transform mode, 3+ selected shapes).
    DIST_KEYS = ("distribute_h_rect", "distribute_v_rect")
    for _k in DIST_KEYS:
            state.setdefault(_k, pygame.Rect(0, 0, 0, 0))

    return {"y": y, "help_lines": help_lines, "sel_stroke": sel_stroke, "submode": submode,
            "sel_count": sel_count, "sel_strokes": sel_strokes}


def _part_a(c):
    """Compat ctx-bag wrapper; core logic lives in render_selection_a."""
    out = render_selection_a(
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

def render_distribute_and_path_section(screen, fonts, state, x, y, _button, _queue_tip, help_lines,
                                       sel_strokes, sel_count, submode, sel_stroke):
    """Explicit-contract render for distribute/path controls (no ctx-bag/sync_in-sync_out)."""
    font, font_small, font_title = fonts
    if (is_open(state, "selection_arrange")
            and submode == "transform" and sel_count >= 3):
        screen.blit(font_small.render("Distribute", True, TEXT_COLOR), (x, y)); y += 20
        dgap = MIN_ELEMENT_SPACING
        dwidth = (PANEL_W - 40 - dgap) // 2
        for di, (dlabel, dkey) in enumerate([
                ("Horizontal", "distribute_h_rect"),
                ("Vertical", "distribute_v_rect")]):
            dr = pygame.Rect(x + di * (dwidth + dgap), y, dwidth, 24)
            state[dkey] = dr
            _button(dr, dlabel)
            _queue_tip(dr, None, f"{dlabel} spacing")
        y += 24 + MIN_ELEMENT_SPACING
    else:
        for _k in DIST_KEYS:
            state[_k] = pygame.Rect(0, 0, 0, 0)
    state.setdefault("curve_hide_rect", pygame.Rect(0,0,0,0))
    state.setdefault("curve_redraw_rect", pygame.Rect(0,0,0,0))
    state.setdefault("curve_cut_rect", pygame.Rect(0,0,0,0))
    state.setdefault("curve_join_rect", pygame.Rect(0,0,0,0))
    PATH_KEYS_LOCAL = ("path_close_rect", "path_reverse_rect", "path_add_rect",
                       "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                       "path_expand_rect")
    for _k in PATH_KEYS_LOCAL:
        state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
    return {"y": y, "help_lines": help_lines, "sel_stroke": sel_stroke, "submode": submode,
            "sel_count": sel_count, "sel_strokes": sel_strokes}


def _part_b(c):
    """Compat ctx-bag wrapper; core logic lives in render_distribute_and_path_section."""
    out = render_distribute_and_path_section(
        c.screen, c.fonts, c.state, c.x, c.y, c._button, c._queue_tip, c.help_lines,
        c.sel_strokes, c.sel_count, c.submode, c.sel_stroke,
    )
    if isinstance(out, dict):
        c.y = out.get("y", c.y)
        c.help_lines = out.get("help_lines", c.help_lines)
        c.sel_stroke = out.get("sel_stroke", c.sel_stroke)
        c.submode = out.get("submode", c.submode)
        c.sel_count = out.get("sel_count", c.sel_count)
        c.sel_strokes = out.get("sel_strokes", c.sel_strokes)
    from views.panel_select_parts_b import _part_b2
    _part_b2(c)