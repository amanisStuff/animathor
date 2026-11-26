"""Tool menu commands (tool switching, snapping, submode, shortcuts)."""
from controllers.commands import ids as CMD  # noqa: E402
import copy
import math
import pygame
import config as cfg

def _menu_tools(ctx, key):
    if key == CMD.WORKSPACE:
        ctx.workspace = "library" if ctx.workspace == "draw" else "draw"
        ctx.state["workspace"] = ctx.workspace
    elif key == CMD.TOOL_SELECT:
        ctx._bezier_pen_commit_or_cancel()
        ctx.tool_mode = "selection"; ctx.drawing = False; ctx.current_points = []
        ctx.selected_point = None; ctx.drag_last = None; ctx.transform_drag = None
        ctx.curve_cut_mode = False; ctx.eyedropper_pick = False
    elif key == CMD.TOOL_EYEDROPPER:
        ctx._bezier_pen_commit_or_cancel()
        ctx.tool_mode = "selection"; ctx.drawing = False; ctx.current_points = []
        ctx.eyedropper_pick = True
        ctx.cutting = False; ctx.cut_points = []
        ctx.curve_cut_mode = False
        ctx.redrawing_curve = None
        ctx.selected_point = None; ctx.drag_last = None; ctx.transform_drag = None
    elif key == CMD.TOOL_PEN:
        ctx.tool_mode = "draw"; ctx.draw_tool = "pen"; ctx.drawing = False; ctx.current_points = []
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None
        ctx.eyedropper_pick = False
    elif key == CMD.TOOL_ERASER:
        ctx._bezier_pen_commit_or_cancel()
        ctx.tool_mode = "draw"; ctx.draw_tool = "eraser"; ctx.drawing = False; ctx.current_points = []
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None
        ctx.eyedropper_pick = False
    elif key == CMD.TOOL_BUCKET:
        ctx._bezier_pen_commit_or_cancel()
        ctx.tool_mode = "draw"; ctx.draw_tool = "bucket"; ctx.drawing = False; ctx.current_points = []
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None
        ctx.eyedropper_pick = False
    elif key == CMD.TOOL_CUTTER:
        ctx._bezier_pen_commit_or_cancel()
        ctx.tool_mode = "draw"; ctx.draw_tool = "cutter"; ctx.drawing = False; ctx.current_points = []
        ctx.cutting = False; ctx.cut_points = []
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None
        ctx.eyedropper_pick = False
    elif key == CMD.TOOL_TEXT:
        ctx._bezier_pen_commit_or_cancel()
        ctx.tool_mode = "draw"; ctx.draw_tool = "text"; ctx.drawing = False; ctx.current_points = []
        ctx.text_entry = None
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None
        ctx.eyedropper_pick = False
    elif key == CMD.CYCLE_SUBMODE:
        modes = ["transform", "nodes", "curve"]
        ctx.selection_submode = modes[(modes.index(ctx.selection_submode) + 1) % len(modes)] if ctx.selection_submode in modes else "transform"
        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.redrawing_curve = None
        ctx.curve_cut_mode = False
    elif key == CMD.SHORTCUTS:
        ctx.help_open = not ctx.help_open
    else:
        return False
    return True
