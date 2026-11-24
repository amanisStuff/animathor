"""Redraw-curve interaction start."""

import pygame
from models import *  # noqa: F401,F403
from views import *  # noqa: F401,F403
from controllers.coordinates import *  # noqa: F401,F403


def handle_redraw_mode(ctx, event):
    if ctx.redrawing_curve is None:
        return None
    # Redraw selected stroke/component: focused draw with snap features
    ctx.cpos = ctx.to_canvas(event.pos)
    ctx.fixed_start = ctx.redrawing_curve.get("fixed_start")
    if ctx.fixed_start is not None:
        start_pos = tuple(ctx.fixed_start)
    else:
        ctx.shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        start_pos = draw_snap_point(ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held) or ctx.cpos
    ctx.redrawing_curve["points"] = [start_pos]
    ctx.redrawing_curve["started"] = True
    dm = getattr(ctx, 'drag_manager', None)
    if dm is not None:
        from controllers.drag.redraw_session import RedrawDragSession
        dm.begin(RedrawDragSession(), ctx, event)
    return 'handled'
