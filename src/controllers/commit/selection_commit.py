"""Selection interaction commits: transform toggle, marquee finalize.

Marquee core is a typed contract; the ctx-based functions are compat wrappers.
"""

from models import rects_intersect, expand_group_selection  # noqa: F401


def commit_transform_toggle(ctx, event):
    """Compat wrapper: transform-toggle is owned by TransformDragSession.end()."""
    from controllers.drag.transform_session import TransformDragSession
    return TransformDragSession().end(ctx, event)


def commit_marquee_typed(drag, selection, document, tools, normalize_rect, stroke_bbox):
    """Finalize marquee selection using typed substates."""
    marquee = drag.marquee_select
    if marquee is None or tools.tool_mode != "selection":
        return None
    r = normalize_rect(marquee["start"], marquee.get("current", marquee["start"]))
    if abs(r[2] - r[0]) >= 3 or abs(r[3] - r[1]) >= 3:
        picked = {i for i, st in enumerate(document.strokes) if rects_intersect(r, stroke_bbox(st))}
        picked = expand_group_selection(document.strokes, picked)
        if marquee.get("add"):
            selection.selected_strokes |= picked
        else:
            selection.selected_strokes = picked
    elif not marquee.get("add"):
        selection.selected_strokes.clear()
    drag.marquee_select = None
    return 'handled'


def commit_marquee(ctx, event):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        return None
    result = commit_marquee_typed(
        app_state.drag, app_state.selection, app_state.document, app_state.tools,
        ctx.normalize_rect, ctx.stroke_bbox,
    )
    if result == 'handled':
        ctx.marquee_select = app_state.drag.marquee_select
        ctx.selected_strokes = app_state.selection.selected_strokes
    return result


def commit_transform_toggle_and_marquee(ctx, event):
    """Compat wrapper: transform toggle then marquee finalize."""
    commit_transform_toggle(ctx, event)
    return commit_marquee(ctx, event)
