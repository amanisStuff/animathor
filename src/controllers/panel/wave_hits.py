"""wave hits."""
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


def _b3_wave_hits(ctx, event, _w_hit):
    if not _w_hit:
        for key, r in (state.get("displacement_affect_rects") or {}).items():
            if r.collidepoint(event.pos):
                si, comp_i = selection.selected_curve
                if 0 <= si < len(document.strokes):
                    comps = stroke_components(document.strokes[si])
                    if 0 <= comp_i < len(comps):
                        comps[comp_i] = dict(comps[comp_i])
                        w = get_distortion_style(comps[comp_i], wi)
                        if w.get("type") == "displacement":
                            w[key] = not bool(w.get(key, True))
                            set_distortion_style(comps[comp_i], w, wi)
                            document.strokes[si]["components"] = comps
                _w_hit = True
                break
    # formula input focus
    f_rect = state.get("wave_formula_rect", pygame.Rect(0,0,0,0))
    if (not _w_hit) and f_rect.collidepoint(event.pos) and f_rect.w > 0 and f_rect.h > 0:
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                wchk = get_distortion_style(comps[comp_i], wi)
                if wchk.get("type") == "wave":
                    ui.wave_formula_focus = True
                    state["wave_formula_focus"] = True
                    _w_hit = True
    # Reverse direction toggle for the active distortion style
    rev_r = state.get("wave_reverse_rect", pygame.Rect(0, 0, 0, 0))
    if (not _w_hit) and rev_r.w > 0 and rev_r.h > 0 and rev_r.collidepoint(event.pos):
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                w = get_distortion_style(comps[comp_i], wi)
                w["reverse"] = not bool(w.get("reverse"))
                set_distortion_style(comps[comp_i], w, wi)
                document.strokes[si]["components"] = comps
        _w_hit = True
    # Clamp: apply the style on only one side or the other
    clamp_r = state.get("wave_clamp_rect", pygame.Rect(0, 0, 0, 0))
    if (not _w_hit) and clamp_r.w > 0 and clamp_r.h > 0 and clamp_r.collidepoint(event.pos):
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                w = get_distortion_style(comps[comp_i], wi)
                ctx.mode = str(w.get("clamp", "none") or "none").lower()
                cycle = ["none", "positive", "negative"]
                try:
                    idx = cycle.index(ctx.mode)
                except ValueError:
                    idx = 0
                w["clamp"] = cycle[(idx + 1) % len(cycle)]
                set_distortion_style(comps[comp_i], w, wi)
                document.strokes[si]["components"] = comps
        _w_hit = True
    # Smooth button
    smooth_r = state.get("wave_smooth_rect", pygame.Rect(0, 0, 0, 0))
    if (not _w_hit) and smooth_r.w > 0 and smooth_r.h > 0 and smooth_r.collidepoint(event.pos):
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                w = get_distortion_style(comps[comp_i], wi)
                if w.get("type") == "repeat":
                    w["repeat_points"] = _smooth_repeat_points(w.get("repeat_points"))
                elif w.get("type") == "thickness":
                    w["thickness_points"] = _smooth_repeat_points(w.get("thickness_points"))
                else:
                    w["custom_points"] = _custom_smooth_samples(w.get("custom_points"))
                    state["wave_custom_finished"] = False
                set_distortion_style(comps[comp_i], w, wi)
                document.strokes[si]["components"] = comps
        _w_hit = True
    # Done button (finish custom draw)
    done_r = state.get("wave_done_rect", pygame.Rect(0, 0, 0, 0))
    if (not _w_hit) and done_r.w > 0 and done_r.h > 0 and done_r.collidepoint(event.pos):
        state["wave_custom_draw"] = False
        state["wave_custom_finished"] = True
        _w_hit = True
    # Clear button
    clear_r = state.get("wave_clear_rect", pygame.Rect(0, 0, 0, 0))
    if (not _w_hit) and clear_r.w > 0 and clear_r.h > 0 and clear_r.collidepoint(event.pos):
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                w = get_distortion_style(comps[comp_i], wi)
                if w.get("type") == "repeat":
                    w["repeat_points"] = []
                elif w.get("type") == "thickness":
                    w["thickness_points"] = []
                else:
                    w["custom_points"] = []
                set_distortion_style(comps[comp_i], w, wi)
                document.strokes[si]["components"] = comps
                state["wave_custom_finished"] = False
        _w_hit = True
    # Pick curve as repeat pattern
    pick_r = state.get("repeat_pick_curve_rect", pygame.Rect(0, 0, 0, 0))
    if (not _w_hit) and pick_r.w > 0 and pick_r.h > 0 and pick_r.collidepoint(event.pos):
        if state.get("repeat_pick_mode"):
            state["repeat_pick_mode"] = False
            state["repeat_pick_target"] = None
            ctx.repeat_pick_mode = False
            ctx.repeat_pick_target = None
        else:
            state["repeat_pick_mode"] = True
            state["repeat_pick_target"] = (si, comp_i, int(wi))
            ctx.repeat_pick_mode = True
            ctx.repeat_pick_target = (si, comp_i, int(wi))
        _w_hit = True
    # custom wave draw mode: pressing inside the box starts a paint stroke
    box = state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
    if (not _w_hit) and box.w > 0 and box.h > 0 and box.collidepoint(event.pos):
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                w = get_distortion_style(comps[comp_i], wi)
                # spatial displacement uses procedural noise (no custom draw box)
                if w.get("type") in ("wave", "repeat", "thickness"):
                    state["wave_custom_finished"] = False
                    state["wave_custom_draw"] = True
                    state["wave_formula_focus"] = False
                    ui.wave_formula_focus = False
                    ctx.wave_custom_drag = _custom_wave_paint(w, box, event.pos, None)
                    state["wave_custom_drag"] = ctx.wave_custom_drag
                    set_distortion_style(comps[comp_i], w, wi)
                    document.strokes[si]["components"] = comps
        _w_hit = True
    return _w_hit


def _b3_wave_sliders(ctx, event, _w_hit):
    if not _w_hit:
        for key, (r, lo, hi) in (state.get("wave_slider_rects") or {}).items():
            if r.collidepoint(event.pos):
                si, comp_i = selection.selected_curve
                if 0 <= si < len(document.strokes):
                    comps = stroke_components(document.strokes[si])
                    if 0 <= comp_i < len(comps):
                        comps[comp_i] = dict(comps[comp_i])
                        w = get_distortion_style(comps[comp_i], wi)
                        ctx.t = (event.pos[0] - r.x) / max(1, r.w - 1)
                        ctx.val = lo + ctx.clamp(ctx.t, 0.0, 1.0) * (hi - lo)
                        if key in ("amplitude", "noise", "phase", "seed", "amount", "location", "handle_rotate", "handle_length"):
                            ctx.val = float(int(round(ctx.val)))
                        elif key in ("frequency", "noise_scale"):
                            ctx.val = float(ctx.val)
                        else:
                            ctx.val = float(ctx.val)
                        w[key] = ctx.val
                        set_distortion_style(comps[comp_i], w, wi)
                        document.strokes[si]["components"] = comps
                        ctx.wave_slider_drag = {"key": key, "rect": r, "lo": lo, "hi": hi, "si": si, "comp_i": comp_i, "wi": wi}
                _w_hit = True
                break
    if not _w_hit and any(
        state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for ctx.k in ("wave_shape_prev_rect", "wave_shape_next_rect")
    ):
        _wsdir = -1 if state.get("wave_shape_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
        _wshapes = [ctx.k for ctx.k, _ in WAVE_SHAPE_LABELS]
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                w = get_distortion_style(comps[comp_i], wi)
                if w.get("type") == "wave":
                    _cur_ws = w.get("shape", "sine")
                    if _cur_ws not in _wshapes:
                        _cur_ws = _wshapes[0]
                    _nws = _wshapes[(_wshapes.index(_cur_ws) + _wsdir) % len(_wshapes)]
                    w["shape"] = _nws
                    w["enabled"] = True
                    if _nws == "custom" and "custom_points" not in w:
                        w["custom_points"] = []
                    set_distortion_style(comps[comp_i], w, wi)
                    document.strokes[si]["components"] = comps
                    if _nws == "custom":
                        state["wave_custom_draw"] = True
                        state["wave_custom_finished"] = False
                        state["wave_formula_focus"] = False
                        ui.wave_formula_focus = False
                    else:
                        state["wave_custom_draw"] = False
                        state["wave_custom_finished"] = False
        _w_hit = True
    return _w_hit
