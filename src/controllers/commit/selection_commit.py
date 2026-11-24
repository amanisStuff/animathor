"""Selection interaction commits: transform toggle, marquee finalize."""

from models import rects_intersect, expand_group_selection


def commit_transform_toggle(ctx, event):
    """Compat wrapper: transform-toggle is owned by TransformDragSession.end()."""
    from controllers.drag.transform_session import TransformDragSession
    return TransformDragSession().end(ctx, event)


def commit_marquee(ctx, event):
    """Finalize marquee selection if active."""
    if ctx.marquee_select is None or ctx.tool_mode != "selection":
        return None
    r = ctx.normalize_rect(ctx.marquee_select["start"], ctx.marquee_select.get("current", ctx.marquee_select["start"]))
    if abs(r[2] - r[0]) >= 3 or abs(r[3] - r[1]) >= 3:
        picked = {i for i, st in enumerate(ctx.strokes) if rects_intersect(r, ctx.stroke_bbox(st))}
        picked = expand_group_selection(ctx.strokes, picked)
        if ctx.marquee_select.get("add"):
            ctx.selected_strokes |= picked
        else:
            ctx.selected_strokes = picked
    elif not ctx.marquee_select.get("add"):
        ctx.selected_strokes.clear()
    ctx.marquee_select = None
    return 'handled'


def commit_transform_toggle_and_marquee(ctx, event):
    """Compat wrapper: transform toggle then marquee finalize."""
    commit_transform_toggle(ctx, event)
    return commit_marquee(ctx, event)
