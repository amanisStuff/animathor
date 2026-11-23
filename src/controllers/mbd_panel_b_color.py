"""Split helper for mbd_panel_b color section (SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *


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
                from controllers.mbd_panel_b_color_parts import handle_bc_part1, handle_bc_part2, handle_bc_part3
                handle_bc_part1(ctx, event) or handle_bc_part2(ctx, event) or handle_bc_part3(ctx, event)
    return _w_hit
