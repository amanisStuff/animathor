"""Wave / displacement / repeat / thickness effects panel actions."""
import copy, math, pygame
import config as cfg

from models.waves import (
    WAVE_SHAPE_LABELS,
    _get_distortion_styles,
    _remove_distortion_style,
    default_displacement_params,
    default_repeat_params,
    default_thickness_params,
    default_wave_params,
)
from models.waves_extra import (
    _custom_smooth_samples,
    _custom_wave_paint,
    _smooth_repeat_points,
    bake_component_distortion,
)


def handle_b_part1(ctx, event):
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
    return _matched


def handle_b_part2(ctx, event):
    _matched = False
    if ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes and ctx.state.get("wave_bake_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
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
    return _matched


def _b3_wave_hits(ctx, event, _w_hit):
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
    return _w_hit


def _b3_wave_sliders(ctx, event, _w_hit):
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
    return _w_hit

from controllers.panel.color_target import _b3_color


def handle_b_part3(ctx, event):
    _matched = False
    if ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
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
        _w_hit = _b3_wave_hits(ctx, event, _w_hit)
        _w_hit = _b3_wave_sliders(ctx, event, _w_hit)
        _w_hit = _b3_color(ctx, event, _w_hit)
    return _matched

# Semantic aliases
handle_wave_effects_primary = handle_b_part1
handle_wave_effects_secondary = handle_b_part2
handle_wave_effect_hits = _b3_wave_hits
handle_wave_effects_sliders = _b3_wave_sliders
handle_wave_effects_tertiary = handle_b_part3
