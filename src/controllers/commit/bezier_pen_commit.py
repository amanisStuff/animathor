"""Bezier pen mouse-up commit.

Core is a typed contract over ``ToolState``; ``commit_bezier_pen_mouseup`` is a
compat wrapper for extracted ctx-based callers.
"""


def commit_bezier_pen_mouseup_typed(tools, finish_pen):
    """Finish or release a Bezier pen gesture on mouse-up."""
    if not (tools.tool_mode == "draw" and tools.draw_tool == "pen"
            and tools.draw_shape == "pen" and tools.bezier_pen is not None
            and tools.bezier_pen.get("mouse_down")):
        return None
    if tools.bezier_pen.get("dragging_first"):
        finish_pen(close_path=True)
        return 'continue'
    tools.bezier_pen["mouse_down"] = False
    tools.bezier_pen["dragging"] = False
    return 'continue'


def commit_bezier_pen_mouseup(ctx, event):
    """Compat wrapper: extract typed tool state from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        return None
    result = commit_bezier_pen_mouseup_typed(app_state.tools, ctx._bezier_pen_finish)
    if result == 'continue':
        ctx.bezier_pen = app_state.tools.bezier_pen
    return result
