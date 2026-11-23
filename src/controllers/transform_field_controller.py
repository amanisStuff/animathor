"""Controller: numeric transform field editing (extracted from app_controller for SRP)."""
import math


def sel_bbox(ctx):
    sel = sorted(i for i in ctx.selected_strokes if 0 <= i < len(ctx.strokes))
    if not sel:
        return sel, None
    return sel, ctx.combined_bbox(ctx.strokes, sel)


def current_value(ctx, field):
    sel, bb = sel_bbox(ctx)
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    if field == "x":
        return float(x0)
    if field == "y":
        return float(y0)
    if field == "w":
        return max(0.0, float(x1 - x0))
    if field == "h":
        return max(0.0, float(y1 - y0))
    if field == "r":
        return 0.0
    return None


def apply_field(ctx, field, target, relative=False):
    """Apply numeric transform to selected strokes. Returns True on change."""
    sel, bb = sel_bbox(ctx)
    if not sel or not bb:
        return False
    x0, y0, x1, y1 = bb
    bw = max(0.0, float(x1 - x0))
    bh = max(0.0, float(y1 - y0))
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    try:
        val = float(target)
    except (TypeError, ValueError):
        return False
    if field == "x":
        dx = (val if relative else (val - x0))
        if abs(dx) < 1e-9:
            return False
        ctx.push_undo()
        for si in sel:
            ctx.strokes[si] = ctx.translate_stroke(ctx.strokes[si], dx, 0.0)
        return True
    if field == "y":
        dy = (val if relative else (val - y0))
        if abs(dy) < 1e-9:
            return False
        ctx.push_undo()
        for si in sel:
            ctx.strokes[si] = ctx.translate_stroke(ctx.strokes[si], 0.0, dy)
        return True
    if field == "w":
        if bw < 1e-9:
            return False
        new_w = (bw + val) if relative else val
        if new_w <= 0.0:
            return False
        sx = max(0.01, new_w / bw)
        if abs(sx - 1.0) < 1e-9:
            return False
        ctx.push_undo()
        for si in sel:
            ctx.strokes[si] = ctx.transform_stroke(ctx.strokes[si], cx, cy, 0.0, sx, 1.0)
        return True
    if field == "h":
        if bh < 1e-9:
            return False
        new_h = (bh + val) if relative else val
        if new_h <= 0.0:
            return False
        sy = max(0.01, new_h / bh)
        if abs(sy - 1.0) < 1e-9:
            return False
        ctx.push_undo()
        for si in sel:
            ctx.strokes[si] = ctx.transform_stroke(ctx.strokes[si], cx, cy, 0.0, 1.0, sy)
        return True
    if field == "r":
        delta_deg = val
        if abs(delta_deg) < 1e-9:
            return False
        ctx.push_undo()
        ang = math.radians(delta_deg)
        for si in sel:
            ctx.strokes[si] = ctx.rotate_stroke_around(ctx.strokes[si], cx, cy, ang)
        return True
    return False


def commit_field(ctx):
    field = ctx.xform_field_focus
    if field is None:
        return False
    buf = str(ctx.xform_field_buffer).strip()
    ctx.xform_field_focus = None
    ctx.xform_field_buffer = ""
    ctx.state["xform_field_focus"] = None
    ctx.state["xform_field_buffer"] = ""
    if buf == "" or buf in ("-", ".", "-."):
        return False
    try:
        val = float(buf)
    except ValueError:
        return False
    return apply_field(ctx, field, val, relative=False)


def cancel_field(ctx):
    ctx.xform_field_focus = None
    ctx.xform_field_buffer = ""
    ctx.state["xform_field_focus"] = None
    ctx.state["xform_field_buffer"] = ""
