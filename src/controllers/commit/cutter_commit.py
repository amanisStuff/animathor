"""Cutter/razor swipe commit.

Core logic is a typed contract over AppState substates; ``commit_cutter`` is a
compat wrapper for extracted ctx-based callers.
"""

import math
from models import cut_strokes_with_path  # noqa: F401


def commit_cutter_typed(drag, document, selection, tools, state, event,
                        clamp_to_canvas, push_undo):
    """Finalize a razor swipe and apply the cut to typed document state."""
    if not drag.cutting:
        return None
    drag.cutting = False
    cpos = clamp_to_canvas(event.pos)
    if (not drag.cut_points
            or math.hypot(cpos[0] - drag.cut_points[-1][0],
                          cpos[1] - drag.cut_points[-1][1]) >= 1.0):
        drag.cut_points.append(cpos)
    if len(drag.cut_points) >= 2:
        only = None
        if (tools.tool_mode == "selection" and selection.selection_submode == "curve"
                and selection.selected_strokes):
            only = set(selection.selected_strokes)
        new_strokes, cut_idx = cut_strokes_with_path(
            document.strokes, drag.cut_points, only_indices=only,
            gap=drag.cut_gap / 2.0,
        )
        if cut_idx:
            push_undo()
            document.strokes[:] = new_strokes
            if tools.tool_mode == "selection":
                selection.selected_strokes = {
                    i for i in cut_idx if 0 <= i < len(document.strokes)
                }
                selection.selected_curve = None
                selection.selected_curves.clear()
                if selection.selection_submode == "curve":
                    tools.curve_cut_mode = False
                    state["curve_cut_mode"] = False
            selection.selected_point = None
            drag.transform_drag = None
    drag.cut_points = []
    return 'continue'


def commit_cutter(ctx, event):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None or not app_state.drag.cutting:
        return None
    result = commit_cutter_typed(
        app_state.drag, app_state.document, app_state.selection, app_state.tools,
        ctx.state, event, ctx.clamp_to_canvas, ctx.push_undo,
    )
    if result == 'continue':
        ctx.cutting = app_state.drag.cutting
        ctx.cut_points = app_state.drag.cut_points
        ctx.curve_cut_mode = app_state.tools.curve_cut_mode
    return result
