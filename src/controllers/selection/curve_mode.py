"""Curve selection submode handler."""

import copy
from models import *  # noqa: F401,F403
from views import *  # noqa: F401,F403
from controllers.coordinates import *  # noqa: F401,F403


def handle_curve_mode(ctx, event):
    ctx.cpos = ctx.to_canvas(event.pos)
    handled_curve = False
    # Curve mode: select/edit curves (components) only; node editing is in Nodes mode
    ctx.selected_point = None
    if ctx.curve_cut_mode and (ctx.selected_curves or ctx.selected_strokes):
        # Razor swipe across the selected curve/stroke.
        ctx.cutting = True
        ctx.cut_points = [ctx.cpos]
        handled_curve = True
    if not handled_curve:
        hit = hit_test_stroke(ctx.cpos, ctx.strokes)
        hit_curve = None
        if hit is not None and 0 <= hit < len(ctx.strokes):
            ctx.comp_i = hit_test_component(ctx.strokes[hit], ctx.cpos)
            if ctx.comp_i is not None:
                hit_curve = (hit, int(ctx.comp_i))
        if hit_curve is not None:
            if ctx.state.get("repeat_pick_mode") and ctx.state.get("repeat_pick_target"):
                tgt = ctx.state.get("repeat_pick_target")
                try:
                    tsi, tci, twi = int(tgt[0]), int(tgt[1]), int(tgt[2])
                except Exception:
                    tsi, tci, twi = -1, -1, 0
                if 0 <= tsi < len(ctx.strokes):
                    src_si, src_ci = hit_curve
                    src_comps = ctx._stroke_components(ctx.strokes[src_si])
                    if 0 <= src_ci < len(src_comps):
                        src_segs = src_comps[src_ci].get("segs") or []
                        rp = _segs_to_repeat_points(src_segs)
                        if rp:
                            tgt_comps = ctx._stroke_components(ctx.strokes[tsi])
                            if 0 <= tci < len(tgt_comps):
                                tgt_comps[tci] = dict(tgt_comps[tci])
                                ctx.w = ctx._get_distortion_style(tgt_comps[tci], twi)
                                if ctx.w.get("type") == "thickness":
                                    ctx.w["thickness_points"] = rp
                                else:
                                    ctx.w["repeat_points"] = rp
                                    ctx.w["type"] = "repeat"
                                ctx.w["enabled"] = True
                                ctx._set_distortion_style(tgt_comps[tci], ctx.w, twi)
                                ctx.strokes[tsi]["components"] = tgt_comps
                ctx.state["repeat_pick_mode"] = False
                ctx.state["repeat_pick_target"] = None
                ctx.repeat_pick_mode = False
                ctx.repeat_pick_target = None
                handled_curve = True
            elif ctx.shift:
                if hit_curve in ctx.selected_curves:
                    ctx.selected_curves.discard(hit_curve)
                    if ctx.selected_curve == hit_curve:
                        ctx.selected_curve = next(iter(ctx.selected_curves), None)
                else:
                    ctx.selected_curves.add(hit_curve)
                    ctx.selected_curve = hit_curve
                ctx.selected_strokes = {ctx.si for (ctx.si, _ci) in ctx.selected_curves}
                handled_curve = True
            else:
                ctx.selected_curves = {hit_curve}
                ctx.selected_curve = hit_curve
                ctx.selected_strokes = {ctx.si for (ctx.si, _ci) in ctx.selected_curves}
                handled_curve = True
        elif hit is None and not ctx.shift:
            ctx.selected_curves.clear()
            ctx.selected_curve = None
            ctx.selected_strokes.clear()
    # keep active curve consistent with multi-selection
    if ctx.selected_curves and ctx.selected_curve not in ctx.selected_curves:
        ctx.selected_curve = next(iter(ctx.selected_curves), None)
    if not ctx.selected_curves:
        ctx.selected_curve = None
        # if a stroke was selected via other means, keep stroke selection only
        # when there are no curve hits; curve mode primarily tracks curves
        if handled_curve:
            ctx.selected_strokes.clear()
    return 'handled'
