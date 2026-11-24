"""Selection interaction commits: transform toggle, marquee finalize."""

from models import rects_intersect, expand_group_selection


def commit_transform_toggle(ctx, event):
    """Finalize transform click-toggle / clear transform drag state."""
    if ctx.pan_drag is not None and getattr(ctx, 'space_panning', False):
        ctx.pan_drag = None
    ctx.pivot_drag = None
    if ctx.pending_transform_toggle is not None and ctx.tool_mode == "selection" and ctx.selection_submode == "transform":
        if not ctx.pending_transform_toggle.get("moved") and ctx.selected_strokes:
            ctx.transform_handle_mode = "rotate" if ctx.transform_handle_mode == "scale" else "scale"
        ctx.pending_transform_toggle = None
    ctx.transform_drag = None
    ctx.gradient_drag = None
    return None


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
