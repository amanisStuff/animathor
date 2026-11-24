"""Controller: numeric transform field editing (extracted from app_controller for SRP).

Operates on typed ``SelectionState`` / ``DocumentState`` / ``UiCacheState``
substates with services passed explicitly (Phase 1: no ctx bag).
"""
import math


def _sel_bbox(selection, document, combined_bbox):
    sel = sorted(i for i in selection.selected_strokes if 0 <= i < len(document.strokes))
    if not sel:
        return sel, None
    return sel, combined_bbox(document.strokes, sel)


def sel_bbox(selection, document, combined_bbox):
    return _sel_bbox(selection, document, combined_bbox)


def current_value(selection, document, field, combined_bbox):
    sel, bb = _sel_bbox(selection, document, combined_bbox)
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


def apply_field(selection, document, field, target, combined_bbox,
                push_undo, translate_stroke, transform_stroke, rotate_stroke_around,
                relative=False):
    """Apply numeric transform to selected strokes. Returns True on change."""
    sel, bb = _sel_bbox(selection, document, combined_bbox)
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
    strokes = document.strokes
    if field == "x":
        dx = (val if relative else (val - x0))
        if abs(dx) < 1e-9:
            return False
        push_undo()
        for si in sel:
            strokes[si] = translate_stroke(strokes[si], dx, 0.0)
        return True
    if field == "y":
        dy = (val if relative else (val - y0))
        if abs(dy) < 1e-9:
            return False
        push_undo()
        for si in sel:
            strokes[si] = translate_stroke(strokes[si], 0.0, dy)
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
        push_undo()
        for si in sel:
            strokes[si] = transform_stroke(strokes[si], cx, cy, 0.0, sx, 1.0)
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
        push_undo()
        for si in sel:
            strokes[si] = transform_stroke(strokes[si], cx, cy, 0.0, 1.0, sy)
        return True
    if field == "r":
        if abs(val) < 1e-9:
            return False
        push_undo()
        ang = math.radians(val)
        for si in sel:
            strokes[si] = rotate_stroke_around(strokes[si], cx, cy, ang)
        return True
    return False


def commit_field(ui, state, selection, document, combined_bbox,
                 push_undo, translate_stroke, transform_stroke, rotate_stroke_around):
    field = ui.xform_field_focus
    if field is None:
        return False
    buf = str(ui.xform_field_buffer).strip()
    ui.xform_field_focus = None
    ui.xform_field_buffer = ""
    state["xform_field_focus"] = None
    state["xform_field_buffer"] = ""
    if buf == "" or buf in ("-", ".", "-."):
        return False
    try:
        val = float(buf)
    except ValueError:
        return False
    return apply_field(selection, document, field, val, combined_bbox,
                       push_undo, translate_stroke, transform_stroke,
                       rotate_stroke_around, relative=False)


def cancel_field(ui, state):
    ui.xform_field_focus = None
    ui.xform_field_buffer = ""
    state["xform_field_focus"] = None
    state["xform_field_buffer"] = ""
