"""Redraw-curve commit."""

import pygame
from models import finalize_drawing_points, redraw_stroke_component  # noqa: F401


def commit_redraw_curve(ctx, event):
    if ctx.redrawing_curve is None:
        return None
    if ctx.redrawing_curve.get("started"):
        ctx.si = ctx.redrawing_curve.get("stroke_idx")
        ctx.comp_i = ctx.redrawing_curve.get("comp_idx", ctx.redrawing_curve.get("seg_idx"))
        ctx.pts = list(ctx.redrawing_curve.get("points", []))
        ctx.fixed_start = ctx.redrawing_curve.get("fixed_start")
        ctx.fixed_end = ctx.redrawing_curve.get("fixed_end")
        if ctx.fixed_start is not None and ctx.pts:
            ctx.pts[0] = tuple(ctx.fixed_start)
        ctx.cpos = ctx.clamp_to_canvas(event.pos)
        ctx.shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        ctx.keys = pygame.key.get_pressed()
        straight_line = bool(ctx.keys[pygame.K_LSHIFT] or ctx.keys[pygame.K_RSHIFT]) if ctx.keys else False
        ctx.pts = finalize_drawing_points(ctx.pts, ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held, straight_line, fixed_end=ctx.fixed_end)
        if ctx.fixed_start is not None:
            if ctx.pts:
                ctx.pts[0] = tuple(ctx.fixed_start)
            else:
                ctx.pts = [tuple(ctx.fixed_start)]
        if ctx.fixed_end is not None:
            if len(ctx.pts) == 1:
                ctx.pts.append(tuple(ctx.fixed_end))
            elif ctx.pts:
                ctx.pts[-1] = tuple(ctx.fixed_end)
        if ctx.si is not None and ctx.comp_i is not None and 0 <= ctx.si < len(ctx.strokes) and len(ctx.pts) >= 2:
            ctx.push_undo()
            ctx.strokes[ctx.si] = redraw_stroke_component(ctx.strokes[ctx.si], ctx.comp_i, ctx.pts)
        ctx.redrawing_curve = None
    else:
        # Redraw mode armed but drawing not started yet (e.g. released on button); wait for canvas drag
        pass
    return 'handled'
