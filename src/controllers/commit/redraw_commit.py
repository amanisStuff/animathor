"""Redraw-curve commit.

Core logic is a typed contract over ``DragState`` / ``DocumentState``;
``commit_redraw_curve`` is a compat wrapper for extracted ctx-based callers.
"""

import pygame
from models import finalize_drawing_points, redraw_stroke_component  # noqa: F401


def commit_redraw_curve_typed(drag, document, event, clamp_to_canvas,
                              snap_radius, push_undo):
    """Finalize an active redraw gesture into a document mutation."""
    redrawing = drag.redrawing_curve
    if redrawing is None:
        return None
    if redrawing.get("started"):
        si = redrawing.get("stroke_idx")
        comp_i = redrawing.get("comp_idx", redrawing.get("seg_idx"))
        pts = list(redrawing.get("points", []))
        fixed_start = redrawing.get("fixed_start")
        fixed_end = redrawing.get("fixed_end")
        if fixed_start is not None and pts:
            pts[0] = tuple(fixed_start)
        cpos = clamp_to_canvas(event.pos)
        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        keys = pygame.key.get_pressed()
        straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
        pts = finalize_drawing_points(pts, cpos, document.strokes, snap_radius(),
                                      shift_held, straight_line, fixed_end=fixed_end)
        if fixed_start is not None:
            if pts:
                pts[0] = tuple(fixed_start)
            else:
                pts = [tuple(fixed_start)]
        if fixed_end is not None:
            if len(pts) == 1:
                pts.append(tuple(fixed_end))
            elif pts:
                pts[-1] = tuple(fixed_end)
        if (si is not None and comp_i is not None and 0 <= si < len(document.strokes)
                and len(pts) >= 2):
            push_undo()
            document.strokes[si] = redraw_stroke_component(document.strokes[si], comp_i, pts)
        drag.redrawing_curve = None
    return 'handled'


def commit_redraw_curve(ctx, event):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        return None
    result = commit_redraw_curve_typed(
        app_state.drag, app_state.document, event,
        ctx.clamp_to_canvas, ctx.snap_radius, ctx.push_undo,
    )
    if result == 'handled':
        ctx.redrawing_curve = app_state.drag.redrawing_curve
    return result
