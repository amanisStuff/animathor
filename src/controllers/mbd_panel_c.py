"""Panel click helpers (split for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

# _handle_panel_click_c

def _handle_panel_click_c(ctx, event):
    _matched = False
    if ctx.tool_mode == "selection" and ctx.selected_strokes and ctx.selection_submode == "transform":
        ctx._c_comp_style_target = None
        if ctx.selection_submode == "curve" and ctx.selected_curve and len(ctx.selected_strokes) == 1 and ctx.selected_curve[0] in ctx.selected_strokes:
            ctx._c_comp_style_target = ctx.selected_curve
        if ctx._c_comp_style_target is not None:
            ctx.color_target = "stroke"
            ctx.state["color_target"] = "stroke"
        if ctx.selection_submode == "curve" and ctx._c_comp_style_target is None:
            pass
        else:
            ctx._c_sel_list = sorted(ctx.selected_strokes)
            ctx._c_primary_i = ctx._c_sel_list[0]
            ctx._c_primary_obj = ctx.strokes[ctx._c_primary_i] if 0 <= ctx._c_primary_i < len(ctx.strokes) else None
            def _set_comp_stroke_color(si, ci, rgb, alpha):
                ctx.comps = ctx._stroke_components(ctx.strokes[si])
                if 0 <= ci < len(ctx.comps):
                    ctx.comps[ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
                    ctx.strokes[si]["components"] = ctx.comps
            ctx._c_set_comp_stroke_color = _set_comp_stroke_color
            if ctx._c_primary_obj is None:
                pass
            else:
                from controllers.mbd_panel_c_parts import handle_c_tabs_filltype, handle_c_stops, handle_c_picker
                if handle_c_tabs_filltype(ctx, event):
                    pass
                elif handle_c_stops(ctx, event):
                    pass
                elif handle_c_picker(ctx, event):
                    pass
    return None
    return "handled" if _matched else None
