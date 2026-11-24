"""Cutter/razor swipe commit."""

import math
import pygame
from models import cut_strokes_with_path  # noqa: F401


def commit_cutter(ctx, event):
    if not ctx.cutting:
        return None
    ctx.cutting = False
    ctx.cpos = ctx.clamp_to_canvas(event.pos)
    if not ctx.cut_points or math.hypot(ctx.cpos[0] - ctx.cut_points[-1][0],
                                    ctx.cpos[1] - ctx.cut_points[-1][1]) >= 1.0:
        ctx.cut_points.append(ctx.cpos)
    if len(ctx.cut_points) >= 2:
        ctx.only = None
        if (ctx.tool_mode == "selection" and ctx.selection_submode == "curve"
                and ctx.selected_strokes):
            ctx.only = set(ctx.selected_strokes)
        new_strokes, cut_idx = cut_strokes_with_path(
            ctx.strokes, ctx.cut_points, only_indices=ctx.only,
            gap=ctx.cut_gap / 2.0)
        if cut_idx:
            ctx.push_undo()
            ctx.strokes[:] = new_strokes
            if ctx.tool_mode == "selection":
                # For single-piece replacements (gap 0) indices are
                # preserved; for multi-piece splits, select affected
                # strokes best-effort by mapping original indices.
                sel_after = set()
                ctx.base = 0
                cut_set = set(cut_idx)
                for oi in range(len(ctx.strokes) - 0):  # placeholder, recompute below
                    pass
                # Recompute mapping from original stroke index to new indices.
                # We need original count; infer by reversing: iterate over
                # original strokes isn't directly available, so approximate:
                # if every cut produced exactly 1 piece total count matches
                # original; otherwise fall back to selecting all new strokes
                # in positions of cut regions is complex. Simpler: when in
                # curve mode (single-stroke selection typical) select same
                # indices as cut_idx; else leave selection cleared.
                if ctx.selection_submode == "curve":
                    ctx.selected_strokes = set(ctx.i for ctx.i in cut_idx if 0 <= ctx.i < len(ctx.strokes))
                else:
                    ctx.selected_strokes = set(ctx.i for ctx.i in cut_idx if 0 <= ctx.i < len(ctx.strokes))
                ctx.selected_curve = None
                ctx.selected_curves.clear()
                if ctx.selection_submode == "curve":
                    # One-shot action: turn the razor off so the
                    # new curve halves can be clicked/selected.
                    ctx.curve_cut_mode = False
                    ctx.state["curve_cut_mode"] = False
            ctx.selected_point = None
            ctx.transform_drag = None
    ctx.cut_points = []
    return 'continue'
