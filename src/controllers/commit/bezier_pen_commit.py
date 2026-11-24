"""Bezier pen mouse-up commit."""


def commit_bezier_pen_mouseup(ctx, event):
    if not (ctx.tool_mode == "draw" and ctx.draw_tool == "pen"
            and ctx.draw_shape == "pen" and ctx.bezier_pen is not None
            and ctx.bezier_pen.get("mouse_down")):
        return None
    if ctx.bezier_pen.get("dragging_first"):
        ctx._bezier_pen_finish(close_path=True)
        return 'continue'
    ctx.bezier_pen["mouse_down"] = False
    ctx.bezier_pen["dragging"] = False
    return 'continue'
