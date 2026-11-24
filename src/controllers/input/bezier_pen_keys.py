"""Bezier pen tool key handling."""

import pygame


def handle_bezier_pen_keys(ctx, event):
    # Bezier pen: Enter finishes open path, Escape cancels.
    if not (ctx.bezier_pen is not None and ctx.tool_mode == "draw"
            and ctx.draw_tool == "pen" and ctx.draw_shape == "pen"):
        return None
    if event.key == pygame.K_ESCAPE:
        ctx._bezier_pen_cancel()
        return 'continue'
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        if len(ctx.bezier_pen.get("anchors", [])) >= 2:
            ctx._bezier_pen_finish(close_path=False)
        else:
            ctx._bezier_pen_cancel()
        return 'continue'
    if event.key == pygame.K_BACKSPACE:
        # Remove last placed anchor (useful correction while drawing).
        ctx.anchors = ctx.bezier_pen.get("anchors", [])
        if len(ctx.anchors) > 1:
            ctx.anchors.pop()
            ctx.bezier_pen["mouse_down"] = False
            ctx.bezier_pen["dragging"] = False
        else:
            ctx._bezier_pen_cancel()
        return 'continue'
    return None
