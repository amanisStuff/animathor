"""Split helper for mbd_panel_b color section (SRP)."""
import copy, math, pygame
import config as cfg


def _b3_color(ctx, event, _w_hit):
    if not _w_hit and ctx.selected_strokes and (ctx.selection_submode == "transform" or (ctx.selection_submode == "curve" and ctx.selected_curve)):
        ctx._c_comp_style_target = None
        if ctx.selection_submode == "curve" and ctx.selected_curve and len(ctx.selected_strokes) == 1 and ctx.selected_curve[0] in ctx.selected_strokes:
            ctx._c_comp_style_target = ctx.selected_curve
        if ctx._c_comp_style_target is not None:
            ctx.color_target = "stroke"
            ctx.state["color_target"] = "stroke"
        if not (ctx.selection_submode == "curve" and ctx._c_comp_style_target is None):
            ctx._c_sel_list = sorted(ctx.selected_strokes)
            ctx._c_primary_i = ctx._c_sel_list[0]
            ctx._c_primary_obj = ctx.strokes[ctx._c_primary_i] if 0 <= ctx._c_primary_i < len(ctx.strokes) else None
            def _set_comp_stroke_color(si, ci, rgb, alpha):
                ctx.comps = ctx._stroke_components(ctx.strokes[si])
                if 0 <= ci < len(ctx.comps):
                    ctx.comps[ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
                    ctx.strokes[si]["components"] = ctx.comps
            ctx._c_set_comp_stroke_color = _set_comp_stroke_color
            if ctx._c_primary_obj is not None:
                from controllers.panel_actions.color_fill import (
                    handle_color_targets,
                    handle_fill_stops,
                    handle_color_picker,
                )
                handle_color_targets(ctx, event) or handle_fill_stops(ctx, event) or handle_color_picker(ctx, event)
    return _w_hit
