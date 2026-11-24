"""Eyedropper style pick/apply in selection mode."""

import copy
from models import hit_test_component, hit_test_stroke  # noqa: F401


from models.strokes import _effective_component_style  # noqa: F401
from models.waves import _get_distortion_styles, _is_distortion_style  # noqa: F401

def handle_eyedropper(ctx, event):
    if not ctx.eyedropper_pick:
        return None
    ctx.cpos = ctx.to_canvas(event.pos)
    hit = hit_test_stroke(ctx.cpos, ctx.strokes)
    if hit is not None and 0 <= hit < len(ctx.strokes):
        src_stroke = ctx.strokes[hit]
        src_comp_i = hit_test_component(src_stroke, ctx.cpos)
        if src_comp_i is None:
            src_comp_i = 0
        src_sc, src_sw = _effective_component_style(src_stroke, src_comp_i)
        src_fc = src_stroke.get("fill_color")
        src_fg = copy.deepcopy(src_stroke.get("fill_gradient")) if isinstance(src_stroke, dict) else None
        src_comps = ctx._stroke_components(src_stroke)
        if 0 <= src_comp_i < len(src_comps):
            src_dists = copy.deepcopy(_get_distortion_styles(src_comps[src_comp_i]))
        else:
            src_dists = []
        had_sel = bool(ctx.selected_strokes)
        if not had_sel:
            ctx.selected_strokes = {hit}
            if ctx.selection_submode == "curve":
                ctx.selected_curve = (hit, src_comp_i)
            else:
                ctx.selected_curve = None
        else:
            ctx.push_undo()
            for ctx.si in list(ctx.selected_strokes):
                if not (0 <= ctx.si < len(ctx.strokes)):
                    continue
                ctx.st = ctx.strokes[ctx.si]
                ctx.st["stroke_width"] = float(src_sw)
                ctx.st["fill_color"] = copy.deepcopy(src_fc) if src_fc is not None else None
                ctx.st["fill_gradient"] = copy.deepcopy(src_fg) if src_fg is not None else None
                # In curve submode, apply stroke style/waves to the
                # selected component but keep fill at stroke level.
                if (ctx.selection_submode == "curve" and ctx.selected_curve
                        and ctx.selected_curve[0] == ctx.si and len(ctx.selected_strokes) == 1):
                    ctx.ci = ctx.selected_curve[1]
                    ctx.comps = ctx._stroke_components(ctx.st)
                    if 0 <= ctx.ci < len(ctx.comps):
                        ctx.comps[ctx.ci] = copy.deepcopy(ctx.comps[ctx.ci])
                        ctx.comps[ctx.ci]["stroke_color"] = copy.deepcopy(src_sc)
                        ctx.comps[ctx.ci]["stroke_width"] = float(src_sw)
                        ctx.comps[ctx.ci].pop("wave", None)
                        ctx.comps[ctx.ci]["styles"] = [ctx.s for ctx.s in ctx.comps[ctx.ci].get("styles", []) if not _is_distortion_style(ctx.s)]
                        for ctx.wi, wv in enumerate(src_dists):
                            ctx._set_distortion_style(ctx.comps[ctx.ci], wv, ctx.wi)
                        ctx.st["components"] = ctx.comps
                else:
                    ctx.st["stroke_color"] = copy.deepcopy(src_sc)
                    ctx.comps = ctx._stroke_components(ctx.st)
                    if ctx.comps:
                        new_comps = []
                        for ctx.comp in ctx.comps:
                            ctx.comp = copy.deepcopy(ctx.comp)
                            # clear per-component stroke overrides to apply uniformly
                            ctx.comp.pop("stroke_color", None)
                            ctx.comp.pop("stroke_width", None)
                            ctx.comp.pop("wave", None)
                            ctx.comp["styles"] = [ctx.s for ctx.s in ctx.comp.get("styles", []) if not _is_distortion_style(ctx.s)]
                            for ctx.wi, wv in enumerate(src_dists):
                                ctx._set_distortion_style(ctx.comp, wv, ctx.wi)
                            new_comps.append(ctx.comp)
                        ctx.st["components"] = new_comps
        ctx.eyedropper_pick = False
        ctx.state["eyedropper_pick"] = False
    # If the click missed, stay in pick mode.
    return 'handled'
