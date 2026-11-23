"""Panel click helpers (split for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

# _handle_panel_click_b

def _handle_panel_click_b(ctx, event):
    _matched = False
    if ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("wave_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                # append a new wave style to the stack and edit it
                ctx.n = len(_get_distortion_styles(ctx.comps[ctx.comp_i]))
                ctx.w = default_wave_params()
                ctx.w["enabled"] = True
                ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.n)
                ctx.strokes[ctx.si]["components"] = ctx.comps
                ctx.state["wave_active_index"] = ctx.n
                ctx.state["wave_custom_finished"] = False
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
        ctx.state["wave_custom_draw"] = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("displacement_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                ctx.n = len(_get_distortion_styles(ctx.comps[ctx.comp_i]))
                ctx.d = default_displacement_params()
                ctx.d["enabled"] = True
                ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.d, ctx.n)
                ctx.strokes[ctx.si]["components"] = ctx.comps
                ctx.state["wave_active_index"] = ctx.n
                ctx.state["wave_custom_finished"] = False
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
        ctx.state["wave_custom_draw"] = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("repeat_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                ctx.n = len(_get_distortion_styles(ctx.comps[ctx.comp_i]))
                ctx.r = default_repeat_params()
                ctx.r["enabled"] = True
                ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.r, ctx.n)
                ctx.strokes[ctx.si]["components"] = ctx.comps
                ctx.state["wave_active_index"] = ctx.n
                ctx.state["wave_custom_finished"] = False
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
        ctx.state["wave_custom_draw"] = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("thickness_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                ctx.n = len(_get_distortion_styles(ctx.comps[ctx.comp_i]))
                th = default_thickness_params()
                th["enabled"] = True
                ctx._set_distortion_style(ctx.comps[ctx.comp_i], th, ctx.n)
                ctx.strokes[ctx.si]["components"] = ctx.comps
                ctx.state["wave_active_index"] = ctx.n
                ctx.state["wave_custom_finished"] = False
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
        ctx.state["wave_custom_draw"] = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("wave_bake_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            baked = bake_component_distortion(ctx.strokes[ctx.si], ctx.comp_i)
            if baked is not ctx.strokes[ctx.si]:
                ctx.push_undo()
                ctx.strokes[ctx.si] = baked
                comps_b = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(comps_b):
                    ctx.n = len(_get_distortion_styles(comps_b[ctx.comp_i]))
                    ctx.state["wave_active_index"] = (max(0, ctx.n - 1) if ctx.n else 0)
                else:
                    ctx.state["wave_active_index"] = 0
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
        ctx.state["wave_custom_draw"] = False
        ctx.state["wave_custom_finished"] = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("wave_remove_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                ctx.wi = int(ctx.state.get("wave_active_index", 0) or 0)
                _remove_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                ctx.strokes[ctx.si]["components"] = ctx.comps
                ctx.n = len(_get_distortion_styles(ctx.comps[ctx.comp_i]))
                ctx.state["wave_active_index"] = (max(0, min(ctx.wi, ctx.n - 1)) if ctx.n else 0)
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
        ctx.state["wave_custom_draw"] = False
        ctx.state["wave_custom_finished"] = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("wave_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                ctx.wi = int(ctx.state.get("wave_active_index", 0) or 0)
                ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                ctx.w["enabled"] = not bool(ctx.w.get("enabled"))
                ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                ctx.strokes[ctx.si]["components"] = ctx.comps
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and any(_rr.collidepoint(event.pos) for _ri, _rr in (ctx.state.get("wave_row_rects") or [])):
        _matched = True
        # click a stack row to make that wave the active/edited one
        for _ri, _rr in (ctx.state.get("wave_row_rects") or []):
            if _rr.collidepoint(event.pos):
                if _ri != int(ctx.state.get("wave_active_index", 0) or 0):
                    ctx.state["wave_active_index"] = _ri
                    ctx.state["wave_formula_focus"] = False
                    ctx.state["wave_custom_draw"] = False
                    ctx.state["wave_custom_finished"] = False
                    ctx.wave_formula_focus = False
                break
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
        _matched = True
        _w_hit = False
        ctx.wi = int(ctx.state.get("wave_active_index", 0) or 0)
        # displacement profile selector (flat/custom)
        for ctx.key, ctx.r in (ctx.state.get("displacement_profile_rects") or {}).items():
            if ctx.r.collidepoint(event.pos):
                ctx.si, ctx.comp_i = ctx.selected_curve
                if 0 <= ctx.si < len(ctx.strokes):
                    ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                    if 0 <= ctx.comp_i < len(ctx.comps):
                        ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                        ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                        if ctx.w.get("type") == "displacement":
                            ctx.w["profile"] = ctx.key
                            ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                            ctx.strokes[ctx.si]["components"] = ctx.comps
                            if ctx.key == "custom":
                                ctx.state["wave_custom_draw"] = True
                                ctx.state["wave_custom_finished"] = False
                                ctx.state["wave_formula_focus"] = False
                                ctx.wave_formula_focus = False
                            else:
                                ctx.state["wave_custom_draw"] = False
                                ctx.state["wave_custom_finished"] = False
                _w_hit = True
                break
        # displacement "apply to" toggles (X/Y/Rotate/Length), combinable
        if not _w_hit:
            for ctx.key, ctx.r in (ctx.state.get("displacement_affect_rects") or {}).items():
                if ctx.r.collidepoint(event.pos):
                    ctx.si, ctx.comp_i = ctx.selected_curve
                    if 0 <= ctx.si < len(ctx.strokes):
                        ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                        if 0 <= ctx.comp_i < len(ctx.comps):
                            ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                            ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                            if ctx.w.get("type") == "displacement":
                                ctx.w[ctx.key] = not bool(ctx.w.get(ctx.key, True))
                                ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                                ctx.strokes[ctx.si]["components"] = ctx.comps
                    _w_hit = True
                    break
        # formula input focus
        f_rect = ctx.state.get("wave_formula_rect", pygame.Rect(0,0,0,0))
        if (not _w_hit) and f_rect.collidepoint(event.pos) and f_rect.w > 0 and f_rect.h > 0:
            ctx.si, ctx.comp_i = ctx.selected_curve
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ctx.comps):
                    wchk = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                    if wchk.get("type") == "wave":
                        ctx.wave_formula_focus = True
                        ctx.state["wave_formula_focus"] = True
                        _w_hit = True
        # Reverse direction toggle for the active distortion style
        rev_r = ctx.state.get("wave_reverse_rect", pygame.Rect(0, 0, 0, 0))
        if (not _w_hit) and rev_r.w > 0 and rev_r.h > 0 and rev_r.collidepoint(event.pos):
            ctx.si, ctx.comp_i = ctx.selected_curve
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ctx.comps):
                    ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                    ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                    ctx.w["reverse"] = not bool(ctx.w.get("reverse"))
                    ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                    ctx.strokes[ctx.si]["components"] = ctx.comps
            _w_hit = True
        # Clamp: apply the style on only one side or the other
        clamp_r = ctx.state.get("wave_clamp_rect", pygame.Rect(0, 0, 0, 0))
        if (not _w_hit) and clamp_r.w > 0 and clamp_r.h > 0 and clamp_r.collidepoint(event.pos):
            ctx.si, ctx.comp_i = ctx.selected_curve
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ctx.comps):
                    ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                    ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                    ctx.mode = str(ctx.w.get("clamp", "none") or "none").lower()
                    cycle = ["none", "positive", "negative"]
                    try:
                        idx = cycle.index(ctx.mode)
                    except ValueError:
                        idx = 0
                    ctx.w["clamp"] = cycle[(idx + 1) % len(cycle)]
                    ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                    ctx.strokes[ctx.si]["components"] = ctx.comps
            _w_hit = True
        # Smooth button
        smooth_r = ctx.state.get("wave_smooth_rect", pygame.Rect(0, 0, 0, 0))
        if (not _w_hit) and smooth_r.w > 0 and smooth_r.h > 0 and smooth_r.collidepoint(event.pos):
            ctx.si, ctx.comp_i = ctx.selected_curve
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ctx.comps):
                    ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                    ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                    if ctx.w.get("type") == "repeat":
                        ctx.w["repeat_points"] = _smooth_repeat_points(ctx.w.get("repeat_points"))
                    elif ctx.w.get("type") == "thickness":
                        ctx.w["thickness_points"] = _smooth_repeat_points(ctx.w.get("thickness_points"))
                    else:
                        ctx.w["custom_points"] = _custom_smooth_samples(ctx.w.get("custom_points"))
                        ctx.state["wave_custom_finished"] = False
                    ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                    ctx.strokes[ctx.si]["components"] = ctx.comps
            _w_hit = True
        # Done button (finish custom draw)
        done_r = ctx.state.get("wave_done_rect", pygame.Rect(0, 0, 0, 0))
        if (not _w_hit) and done_r.w > 0 and done_r.h > 0 and done_r.collidepoint(event.pos):
            ctx.state["wave_custom_draw"] = False
            ctx.state["wave_custom_finished"] = True
            _w_hit = True
        # Clear button
        clear_r = ctx.state.get("wave_clear_rect", pygame.Rect(0, 0, 0, 0))
        if (not _w_hit) and clear_r.w > 0 and clear_r.h > 0 and clear_r.collidepoint(event.pos):
            ctx.si, ctx.comp_i = ctx.selected_curve
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ctx.comps):
                    ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                    ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                    if ctx.w.get("type") == "repeat":
                        ctx.w["repeat_points"] = []
                    elif ctx.w.get("type") == "thickness":
                        ctx.w["thickness_points"] = []
                    else:
                        ctx.w["custom_points"] = []
                    ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                    ctx.strokes[ctx.si]["components"] = ctx.comps
                    ctx.state["wave_custom_finished"] = False
            _w_hit = True
        # Pick curve as repeat pattern
        pick_r = ctx.state.get("repeat_pick_curve_rect", pygame.Rect(0, 0, 0, 0))
        if (not _w_hit) and pick_r.w > 0 and pick_r.h > 0 and pick_r.collidepoint(event.pos):
            if ctx.state.get("repeat_pick_mode"):
                ctx.state["repeat_pick_mode"] = False
                ctx.state["repeat_pick_target"] = None
                ctx.repeat_pick_mode = False
                ctx.repeat_pick_target = None
            else:
                ctx.state["repeat_pick_mode"] = True
                ctx.state["repeat_pick_target"] = (ctx.si, ctx.comp_i, int(ctx.wi))
                ctx.repeat_pick_mode = True
                ctx.repeat_pick_target = (ctx.si, ctx.comp_i, int(ctx.wi))
            _w_hit = True
        # custom wave draw mode: pressing inside the box starts a paint stroke
        box = ctx.state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
        if (not _w_hit) and box.w > 0 and box.h > 0 and box.collidepoint(event.pos):
            ctx.si, ctx.comp_i = ctx.selected_curve
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ctx.comps):
                    ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                    ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                    # spatial displacement uses procedural noise (no custom draw box)
                    if ctx.w.get("type") in ("wave", "repeat", "thickness"):
                        ctx.state["wave_custom_finished"] = False
                        ctx.state["wave_custom_draw"] = True
                        ctx.state["wave_formula_focus"] = False
                        ctx.wave_formula_focus = False
                        ctx.wave_custom_drag = _custom_wave_paint(ctx.w, box, event.pos, None)
                        ctx.state["wave_custom_drag"] = ctx.wave_custom_drag
                        ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
            _w_hit = True
        if not _w_hit:
            for ctx.key, (ctx.r, lo, hi) in (ctx.state.get("wave_slider_rects") or {}).items():
                if ctx.r.collidepoint(event.pos):
                    ctx.si, ctx.comp_i = ctx.selected_curve
                    if 0 <= ctx.si < len(ctx.strokes):
                        ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                        if 0 <= ctx.comp_i < len(ctx.comps):
                            ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                            ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                            ctx.t = (event.pos[0] - ctx.r.x) / max(1, ctx.r.w - 1)
                            ctx.val = lo + ctx.clamp(ctx.t, 0.0, 1.0) * (hi - lo)
                            if ctx.key in ("amplitude", "noise", "phase", "seed", "amount", "location", "handle_rotate", "handle_length"):
                                ctx.val = float(int(round(ctx.val)))
                            elif ctx.key in ("frequency", "noise_scale"):
                                ctx.val = float(ctx.val)
                            else:
                                ctx.val = float(ctx.val)
                            ctx.w[ctx.key] = ctx.val
                            ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                            ctx.strokes[ctx.si]["components"] = ctx.comps
                            ctx.wave_slider_drag = {"key": ctx.key, "rect": ctx.r, "lo": lo, "hi": hi, "si": ctx.si, "comp_i": ctx.comp_i, "wi": ctx.wi}
                    _w_hit = True
                    break
        if not _w_hit and any(
            ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
            for ctx.k in ("wave_shape_prev_rect", "wave_shape_next_rect")
        ):
            _wsdir = -1 if ctx.state.get("wave_shape_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
            _wshapes = [ctx.k for ctx.k, _ in WAVE_SHAPE_LABELS]
            ctx.si, ctx.comp_i = ctx.selected_curve
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ctx.comps):
                    ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                    ctx.w = ctx._get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                    if ctx.w.get("type") == "wave":
                        _cur_ws = ctx.w.get("shape", "sine")
                        if _cur_ws not in _wshapes:
                            _cur_ws = _wshapes[0]
                        _nws = _wshapes[(_wshapes.index(_cur_ws) + _wsdir) % len(_wshapes)]
                        ctx.w["shape"] = _nws
                        ctx.w["enabled"] = True
                        if _nws == "custom" and "custom_points" not in ctx.w:
                            ctx.w["custom_points"] = []
                        ctx._set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
                        if _nws == "custom":
                            ctx.state["wave_custom_draw"] = True
                            ctx.state["wave_custom_finished"] = False
                            ctx.state["wave_formula_focus"] = False
                            ctx.wave_formula_focus = False
                        else:
                            ctx.state["wave_custom_draw"] = False
                            ctx.state["wave_custom_finished"] = False
            _w_hit = True
        if not _w_hit and ctx.selected_strokes and (ctx.selection_submode == "transform" or (ctx.selection_submode == "curve" and ctx.selected_curve)):
            # Modern color picker interactions
            ctx.comp_style_target = None
            if ctx.selection_submode == "curve" and ctx.selected_curve and len(ctx.selected_strokes) == 1 and ctx.selected_curve[0] in ctx.selected_strokes:
                ctx.comp_style_target = ctx.selected_curve
            if ctx.comp_style_target is not None:
                ctx.color_target = "stroke"
                ctx.state["color_target"] = "stroke"
            if not (ctx.selection_submode == "curve" and ctx.comp_style_target is None):
                ctx.sel_list = sorted(ctx.selected_strokes)
                ctx.primary_i = ctx.sel_list[0]
                primary_obj = ctx.strokes[ctx.primary_i] if 0 <= ctx.primary_i < len(ctx.strokes) else None
                def _set_comp_stroke_color(si, ci, rgb, alpha):
                    ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                    if 0 <= ctx.ci < len(ctx.comps):
                        ctx.comps[ctx.ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], ctx.alpha)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
                if primary_obj is not None and ctx.state["tab_stroke_rect"].collidepoint(event.pos):
                    ctx.color_target = "stroke"
                    ctx.state["color_target"] = ctx.color_target
                    if ctx.comp_style_target is not None:
                        sc, _sw = _effective_component_style(primary_obj, ctx.comp_style_target[1])
                        sc = sc or (0.1, 0.1, 0.15)
                    else:
                        sc = primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
                    ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*sc)
                    ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                elif primary_obj is not None and ctx.state["tab_fill_rect"].collidepoint(event.pos) and ctx.comp_style_target is None:
                    ctx.color_target = "fill"
                    ctx.state["color_target"] = ctx.color_target
                    fg = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) and primary_obj.get("fill_gradient", {}).get("type") in ("linear","radial") else None)
                    if fg is not None:
                        stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                        fc = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                    else:
                        fc = primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
                    ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                    ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                elif primary_obj is not None and ctx.state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and ctx.color_target == "fill" and ctx.comp_style_target is None:
                    for ctx.si in ctx.sel_list:
                        if 0 <= ctx.si < len(ctx.strokes):
                            ctx.strokes[ctx.si]["fill_color"] = None
                            ctx.strokes[ctx.si]["fill_gradient"] = None
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and any(
                    ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                    for ctx.k in ("fill_type_prev_rect", "fill_type_next_rect")
                ):
                    _fdir = -1 if ctx.state.get("fill_type_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                    _fmodes = ["solid", "linear", "radial", "conic", "spiral", "diamond", "square", "mesh", "pattern"]
                    _pfg_cur = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                    _ppat_cur = get_fill_pattern(primary_obj) if 'get_fill_pattern' in ctx.globals() else primary_obj.get("fill_pattern")
                    if _ppat_cur is not None:
                        _cur_fill_mode = "pattern"
                    elif _pfg_cur is not None:
                        _cur_fill_mode = str(_pfg_cur.get("type", "linear"))
                    elif primary_obj.get("fill_color") is not None:
                        _cur_fill_mode = "solid"
                    else:
                        _cur_fill_mode = "solid"
                    if _cur_fill_mode not in _fmodes:
                        _cur_fill_mode = "solid"
                    ftype = _fmodes[(_fmodes.index(_cur_fill_mode) + _fdir) % len(_fmodes)]
                    if ftype is not None:
                        cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                        grad_types = ("linear", "radial", "conic", "spiral", "diamond", "square", "mesh")
                        for ctx.si in ctx.sel_list:
                            if 0 <= ctx.si < len(ctx.strokes):
                                ctx.st = ctx.strokes[ctx.si]
                                fg = ctx.get_fill_gradient(ctx.st) if 'get_fill_gradient' in ctx.globals() else (ctx.st.get("fill_gradient") if isinstance(ctx.st.get("fill_gradient"), dict) else None)
                                if ftype == "solid":
                                    if fg is not None:
                                        si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else max(0, min(cur_stop_i, max(0, len(fg.get("stops") or []) - 1)))
                                        col0 = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in ctx.globals() else (0.0, 0.0, 0.0, 1.0)
                                    else:
                                        col0 = ctx.st.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                                    ctx.st["fill_color"] = tuple(color_rgba(col0, (0.45, 0.72, 1.0, 1.0)))
                                    ctx.st["fill_gradient"] = None
                                elif ftype in grad_types:
                                    if fg is not None and str(fg.get("type")) in grad_types:
                                        if ftype == "mesh" or str(fg.get("type")) == "mesh":
                                            ctx.base = ctx.st.get("fill_color")
                                            if ctx.base is None and isinstance(fg.get("stops"), list) and fg.get("stops"):
                                                try:
                                                    ctx.base = get_gradient_stop_color(fg, 0) if 'get_gradient_stop_color' in ctx.globals() else (fg.get("stops")[0] or {}).get("color")
                                                except Exception:
                                                    ctx.base = None
                                            ctx.base = color_rgba(ctx.base or (0.2, 0.4, 0.9, 1.0), (0.2, 0.4, 0.9, 1.0))
                                            c1m = (1.0, 1.0, 1.0, float(ctx.base[3]))
                                            if ftype == "mesh" and 'default_mesh_gradient' in ctx.globals():
                                                ctx.st["fill_gradient"] = default_mesh_gradient(ctx.base, c1m)
                                            elif ftype == "linear" and 'default_linear_gradient' in ctx.globals():
                                                ctx.st["fill_gradient"] = ctx.default_linear_gradient(ctx.base, c1m, 0.0)
                                            elif ftype == "radial" and 'default_radial_gradient' in ctx.globals():
                                                ctx.st["fill_gradient"] = ctx.default_radial_gradient((1.0, 1.0, 1.0, float(ctx.base[3])), ctx.base)
                                            elif 'default_shaped_gradient' in ctx.globals():
                                                ctx.st["fill_gradient"] = ctx.default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(ctx.base[3])), ctx.base)
                                            else:
                                                ctx.st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(ctx.base)}, {"pos": 1.0, "color": list(c1m)}]}
                                        else:
                                            ng = dict(fg)
                                            ng["type"] = ftype
                                            if ftype == "linear" and "angle" not in ng:
                                                ng["angle"] = 0.0
                                            if ftype in ("radial", "conic", "spiral", "diamond", "square"):
                                                if "center" not in ng:
                                                    ng["center"] = [0.5, 0.5]
                                                if "radii" not in ng:
                                                    ng["radii"] = [0.5, 0.5]
                                                if "angle" not in ng:
                                                    ng["angle"] = 0.0
                                                if ftype == "spiral" and "turns" not in ng:
                                                    ng["turns"] = 2.0
                                            if 'normalize_gradient' in ctx.globals():
                                                try:
                                                    ng = ctx.normalize_gradient(ng)
                                                except Exception:
                                                    pass
                                            ctx.st["fill_gradient"] = ng
                                    else:
                                        ctx.base = ctx.st.get("fill_color") or (0.2, 0.4, 0.9, 1.0)
                                        c0 = color_rgba(ctx.base, (0.2, 0.4, 0.9, 1.0))
                                        ctx.c1 = (1.0, 1.0, 1.0, float(c0[3]))
                                        if ftype == "mesh" and 'default_mesh_gradient' in ctx.globals():
                                            ctx.st["fill_gradient"] = default_mesh_gradient(c0, ctx.c1)
                                        elif ftype == "linear" and 'default_linear_gradient' in ctx.globals():
                                            ctx.st["fill_gradient"] = ctx.default_linear_gradient(c0, ctx.c1, 0.0)
                                        elif ftype == "radial" and 'default_radial_gradient' in ctx.globals():
                                            ctx.st["fill_gradient"] = ctx.default_radial_gradient((1.0, 1.0, 1.0, float(c0[3])), c0)
                                        elif 'default_shaped_gradient' in ctx.globals():
                                            ctx.st["fill_gradient"] = ctx.default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(c0[3])), c0)
                                        else:
                                            ctx.st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(c0)}, {"pos": 1.0, "color": list(ctx.c1)}]}
                                    ctx.st["fill_color"] = None
                                elif ftype == "pattern":
                                    pat = get_fill_pattern(ctx.st) if 'get_fill_pattern' in ctx.globals() else None
                                    if pat is None and 'new_pattern' in ctx.globals():
                                        pat = new_pattern("stripes")
                                    ctx.st["fill_pattern"] = pat
                                    ctx.st["fill_color"] = None
                                    ctx.st["fill_gradient"] = None
                        pfg = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                        if pfg is not None:
                            ctx.state["fill_gradient_stop"] = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                            fc = get_gradient_stop_color(pfg, int(ctx.state.get("fill_gradient_stop", 0) or 0)) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                            ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                            ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                        elif ftype == "solid":
                            fc = primary_obj.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                            ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                            ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                            ctx.state["fill_gradient_stop"] = 0
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and ctx.state.get("pattern_type_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                    for ctx.si in ctx.sel_list:
                        if 0 <= ctx.si < len(ctx.strokes):
                            pat = get_fill_pattern(ctx.strokes[ctx.si]) if 'get_fill_pattern' in ctx.globals() else None
                            if pat is not None and 'cycle_pattern_type' in ctx.globals():
                                ctx.strokes[ctx.si]["fill_pattern"] = cycle_pattern_type(pat)
                            elif pat is None and 'new_pattern' in ctx.globals():
                                ctx.strokes[ctx.si]["fill_pattern"] = new_pattern("stripes")
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and ctx.state.get("pattern_size_minus_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                    for ctx.si in ctx.sel_list:
                        if 0 <= ctx.si < len(ctx.strokes):
                            pat = get_fill_pattern(ctx.strokes[ctx.si]) if 'get_fill_pattern' in ctx.globals() else None
                            if pat is not None:
                                pat = dict(pat)
                                pat["size"] = max(2.0, float(pat.get("size", 14.0)) - 2.0)
                                ctx.strokes[ctx.si]["fill_pattern"] = pat
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and ctx.state.get("pattern_size_plus_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                    for ctx.si in ctx.sel_list:
                        if 0 <= ctx.si < len(ctx.strokes):
                            pat = get_fill_pattern(ctx.strokes[ctx.si]) if 'get_fill_pattern' in ctx.globals() else None
                            if pat is not None:
                                pat = dict(pat)
                                pat["size"] = min(120.0, float(pat.get("size", 14.0)) + 2.0)
                                ctx.strokes[ctx.si]["fill_pattern"] = pat
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and ctx.state.get("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                    cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                    for ctx.si in ctx.sel_list:
                        if 0 <= ctx.si < len(ctx.strokes):
                            fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                            if fg is not None and 'add_gradient_stop' in ctx.globals():
                                si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                                ng, ni = add_gradient_stop(fg, si_clamped)
                                ctx.strokes[ctx.si]["fill_gradient"] = ng
                                ctx.strokes[ctx.si]["fill_color"] = None
                    pfg = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                    if pfg is not None:
                        si_clamped = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                        ni = min(si_clamped + 1, max(0, len(pfg.get("stops") or []) - 1))
                        ctx.state["fill_gradient_stop"] = ni
                        fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                        ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                        ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and ctx.state.get("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                    cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                    for ctx.si in ctx.sel_list:
                        if 0 <= ctx.si < len(ctx.strokes):
                            fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                            if fg is not None and 'remove_gradient_stop' in ctx.globals():
                                si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                                ng, ni = remove_gradient_stop(fg, si_clamped)
                                ctx.strokes[ctx.si]["fill_gradient"] = ng
                                ctx.strokes[ctx.si]["fill_color"] = None
                    pfg = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                    if pfg is not None:
                        ni = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                        ctx.state["fill_gradient_stop"] = ni
                        fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                        ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                        ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and ctx.state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                    fg = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                    if fg is not None:
                        cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                        pr = ctx.state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
                        # If a stop marker on the ramp is clicked, select that stop.
                        stops_for_pick = get_gradient_stops(fg) if 'get_gradient_stops' in ctx.globals() else list(fg.get("stops") or [])
                        if stops_for_pick:
                            best_i = None
                            ctx.best_d = 1e9
                            for si_pick, st_pick in enumerate(stops_for_pick):
                                try:
                                    ctx.sp = float((st_pick or {}).get("pos", 0.0)) if isinstance(st_pick, dict) else float(st_pick[0])
                                except Exception:
                                    ctx.sp = 0.0
                                ctx.sp = ctx.clamp(ctx.sp, 0.0, 1.0)
                                sxp = pr.x + ctx.sp * max(1, pr.w - 1)
                                ctx.d = abs(event.pos[0] - sxp)
                                if ctx.d <= 7 and ctx.d < ctx.best_d:
                                    ctx.best_d = ctx.d
                                    best_i = si_pick
                            if best_i is not None:
                                cur_stop_i = int(best_i)
                                ctx.state["fill_gradient_stop"] = cur_stop_i
                        rel = (event.pos[0] - pr.x) / max(1, pr.w - 1)
                        rel = ctx.clamp(rel, 0.0, 1.0)
                        if 'set_gradient_stop_pos' in ctx.globals():
                            for ctx.si in ctx.sel_list:
                                if 0 <= ctx.si < len(ctx.strokes):
                                    sfg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                                    if sfg is not None:
                                        sidx = clamp_gradient_stop_index(sfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                                        ng, _ni = set_gradient_stop_pos(sfg, sidx, rel)
                                        ctx.strokes[ctx.si]["fill_gradient"] = ng
                                        ctx.strokes[ctx.si]["fill_color"] = None
                            pfg2 = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else None
                            if pfg2 is not None:
                                sidx = clamp_gradient_stop_index(pfg2, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                                _ngp, ni = set_gradient_stop_pos(pfg2, sidx, rel)
                                ctx.state["fill_gradient_stop"] = ni
                                fc = get_gradient_stop_color(_ngp, ni) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                                ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                                ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                        ctx.fill_stop_pos_drag = True
                        ctx.state["fill_stop_pos_drag"] = True
                elif primary_obj is not None and ctx.color_target == "fill" and ctx.comp_style_target is None and any(ctx.r.collidepoint(event.pos) for ctx.r in (ctx.state.get("fill_stop_rects") or {}).values()):
                    # reverse so if any overlap occurs, topmost/latest wins
                    ctx.items = list((ctx.state.get("fill_stop_rects") or {}).items())
                    skey = ctx.next((ctx.k for ctx.k, ctx.r in reversed(ctx.items) if ctx.r.collidepoint(event.pos)), None)
                    if skey is not None:
                        try:
                            ctx.state["fill_gradient_stop"] = int(skey)
                        except Exception:
                            ctx.state["fill_gradient_stop"] = 0
                        fg = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in ctx.globals() else None
                        if fg is not None:
                            si_clamped = clamp_gradient_stop_index(fg, int(ctx.state.get("fill_gradient_stop", 0) or 0)) if 'clamp_gradient_stop_index' in ctx.globals() else int(ctx.state.get("fill_gradient_stop", 0) or 0)
                            ctx.state["fill_gradient_stop"] = si_clamped
                            fc = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                            ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                            ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                elif primary_obj is not None and ctx.state["sv_rect"].collidepoint(event.pos):
                    ctx.picker_drag_sv = True
                    ctx.sv = ctx.state["sv_rect"]
                    ctx.picker_s = ctx.clamp((event.pos[0] - ctx.sv.x) / max(1, ctx.sv.w - 1), 0.0, 1.0)
                    ctx.picker_v = ctx.clamp(1.0 - (event.pos[1] - ctx.sv.y) / max(1, ctx.sv.h - 1), 0.0, 1.0)
                    ctx.col = ctx.hsv_to_rgb(ctx.picker_h, ctx.picker_s, ctx.picker_v)
                    if ctx.comp_style_target is not None:
                        ctx.si, ctx.ci = ctx.comp_style_target
                        if 0 <= ctx.si < len(ctx.strokes):
                            cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                            ctx.alpha = color_alpha(cur_sc, 1.0)
                            _set_comp_stroke_color(ctx.si, ctx.ci, ctx.col, ctx.alpha)
                    else:
                        for ctx.si in ctx.sel_list:
                            if 0 <= ctx.si < len(ctx.strokes):
                                if ctx.color_target == "stroke":
                                    ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("stroke_color"), 1.0)
                                    ctx.strokes[ctx.si]["stroke_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                                else:
                                    fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                                    if fg is not None:
                                        stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                        ctx.alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1), 1.0)
                                        ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                                    else:
                                        ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("fill_color"), 1.0)
                                        ctx.strokes[ctx.si]["fill_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                                        ctx.strokes[ctx.si]["fill_gradient"] = None
                    ctx.state["picker_drag_sv"] = True
                    ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                elif primary_obj is not None and ctx.state["hue_rect"].collidepoint(event.pos):
                    ctx.picker_drag_hue = True
                    hr = ctx.state["hue_rect"]
                    ctx.picker_h = ctx.clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                    ctx.col = ctx.hsv_to_rgb(ctx.picker_h, ctx.picker_s, ctx.picker_v)
                    if ctx.comp_style_target is not None:
                        ctx.si, ctx.ci = ctx.comp_style_target
                        if 0 <= ctx.si < len(ctx.strokes):
                            cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                            ctx.alpha = color_alpha(cur_sc, 1.0)
                            _set_comp_stroke_color(ctx.si, ctx.ci, ctx.col, ctx.alpha)
                    else:
                        for ctx.si in ctx.sel_list:
                            if 0 <= ctx.si < len(ctx.strokes):
                                if ctx.color_target == "stroke":
                                    ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("stroke_color"), 1.0)
                                    ctx.strokes[ctx.si]["stroke_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                                else:
                                    fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                                    if fg is not None:
                                        stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                        ctx.alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1), 1.0)
                                        ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                                    else:
                                        ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("fill_color"), 1.0)
                                        ctx.strokes[ctx.si]["fill_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                                        ctx.strokes[ctx.si]["fill_gradient"] = None
                    ctx.state["picker_drag_hue"] = True
                    ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                elif primary_obj is not None and ctx.state.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    ar = ctx.state["alpha_rect"]
                    new_alpha = ctx.clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                    if ctx.comp_style_target is not None:
                        ctx.si, ctx.ci = ctx.comp_style_target
                        if 0 <= ctx.si < len(ctx.strokes):
                            cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                            ctx.base = color_rgb(cur_sc, (0.1,0.1,0.15))
                            _set_comp_stroke_color(ctx.si, ctx.ci, ctx.base, new_alpha)
                    else:
                        for ctx.si in ctx.sel_list:
                            if 0 <= ctx.si < len(ctx.strokes):
                                if ctx.color_target == "stroke":
                                    ctx.strokes[ctx.si]["stroke_color"] = set_color_alpha(ctx.strokes[ctx.si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                                else:
                                    fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                                    if fg is not None:
                                        stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                        cstop = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1)
                                        ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (cstop[0], cstop[1], cstop[2], new_alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                                    elif ctx.strokes[ctx.si].get("fill_color") is not None:
                                        ctx.strokes[ctx.si]["fill_color"] = set_color_alpha(ctx.strokes[ctx.si].get("fill_color"), new_alpha)
                    ctx.picker_drag_alpha = True
                    ctx.state["picker_drag_alpha"] = True
                elif primary_obj is not None:
                    # preset swatches
                    ctx.rects = ctx.state["stroke_swatch_rects"] if ctx.color_target == "stroke" else ctx.state["fill_swatch_rects"]
                    for ctx.i, ctx.r in enumerate(ctx.rects):
                        if ctx.r.w > 0 and ctx.r.collidepoint(event.pos) and ctx.i < len(ctx.STROKE_SWATCHES):
                            ctx.col = ctx.STROKE_SWATCHES[ctx.i]
                            if ctx.comp_style_target is not None:
                                ctx.si, ctx.ci = ctx.comp_style_target
                                if 0 <= ctx.si < len(ctx.strokes):
                                    cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                                    ctx.alpha = color_alpha(cur_sc, 1.0)
                                    _set_comp_stroke_color(ctx.si, ctx.ci, ctx.col, ctx.alpha)
                            else:
                                for ctx.si in ctx.sel_list:
                                    if 0 <= ctx.si < len(ctx.strokes):
                                        if ctx.color_target == "stroke":
                                            ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("stroke_color"), 1.0)
                                            ctx.strokes[ctx.si]["stroke_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                                        else:
                                            fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                                            if fg is not None:
                                                stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                                ctx.alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1), 1.0)
                                                ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                                            else:
                                                ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("fill_color"), 1.0)
                                                ctx.strokes[ctx.si]["fill_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                                                ctx.strokes[ctx.si]["fill_gradient"] = None
                            ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*ctx.col)
                            ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                            break
    return "handled" if _matched else None
