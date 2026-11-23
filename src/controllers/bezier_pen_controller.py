"""Controller: Bezier pen tool (extracted from app_controller for SRP)."""
import math


def cancel(ctx):
    ctx.bezier_pen = None


def finish(ctx, close_path=False):
    """Finalize active Bezier pen path into a stroke. Returns True if created."""
    bp = ctx.bezier_pen
    ctx.bezier_pen = None
    if not bp:
        return False
    anchors = list(bp.get("anchors") or [])
    if len(anchors) < 2:
        return False
    segs = []
    n = len(anchors)
    last = n if close_path and n >= 3 else n - 1
    for i in range(last):
        a = anchors[i]
        b = anchors[(i + 1) % n]
        p0 = tuple(a["pt"]); p3 = tuple(b["pt"])
        c1 = tuple(a.get("h_out") or a["pt"])
        c2 = tuple(b.get("h_in") or b["pt"])
        segs.append((p0, c1, c2, p3))
    if not segs:
        return False
    ctx.push_undo()
    algo_name = "pen"
    st = ctx.new_stroke(segs, algorithm=algo_name)
    st["components"] = [{
        "raw_points": [tuple(a["pt"]) for a in anchors],
        "draw_max_points": len(anchors),
        "algorithm": algo_name,
        "segs": list(segs),
    }]
    if close_path and n >= 3:
        st = ctx._close_path_if_needed(st)
    ctx.strokes.append(st)
    ctx.strokes = ctx.merge_connected_strokes(ctx.strokes)
    ctx.selected_strokes.clear()
    ctx.selected_point = None
    ctx.selected_curve = None
    ctx.selected_curves.clear()
    return True


def add_anchor(ctx, pos):
    """Add a new anchor at pos and start dragging its handles."""
    pt = tuple(pos)
    if ctx.bezier_pen is None:
        ctx.bezier_pen = {"anchors": [], "dragging": False, "mouse_down": True,
                          "down_pos": pt, "preview_pt": pt, "dragging_first": False}
    ctx.bezier_pen.setdefault("anchors", [])
    ctx.bezier_pen["anchors"].append({"pt": pt, "h_in": pt, "h_out": pt, "smooth": False})
    ctx.bezier_pen["dragging"] = True
    ctx.bezier_pen["mouse_down"] = True
    ctx.bezier_pen["down_pos"] = pt
    ctx.bezier_pen["preview_pt"] = pt
    ctx.bezier_pen["dragging_first"] = False


def update_drag(ctx, pos):
    """Update handles while dragging: last anchor's h_out, or first anchor's h_in for close."""
    if not ctx.bezier_pen or not ctx.bezier_pen.get("anchors"):
        return
    anchors = ctx.bezier_pen["anchors"]
    if ctx.bezier_pen.get("dragging_first"):
        a = anchors[0]
        pt = a["pt"]
        if math.hypot(pos[0] - pt[0], pos[1] - pt[1]) > 2.0:
            h_in = tuple(pos)
            h_out = (2.0 * pt[0] - h_in[0], 2.0 * pt[1] - h_in[1])
            a["h_in"] = h_in
            a["h_out"] = h_out
            a["smooth"] = True
        else:
            a["h_in"] = pt
            a["h_out"] = pt
            a["smooth"] = False
    else:
        a = anchors[-1]
        pt = a["pt"]
        if math.hypot(pos[0] - pt[0], pos[1] - pt[1]) > 2.0:
            h_out = tuple(pos)
            h_in = (2.0 * pt[0] - h_out[0], 2.0 * pt[1] - h_out[1])
            a["h_out"] = h_out
            a["h_in"] = h_in
            a["smooth"] = True
        else:
            a["h_out"] = pt
            a["h_in"] = pt
            a["smooth"] = False
    ctx.bezier_pen["preview_pt"] = tuple(pos)


def near_first(ctx, pos, radius=10.0):
    if not ctx.bezier_pen or not ctx.bezier_pen.get("anchors"):
        return False
    first = ctx.bezier_pen["anchors"][0]["pt"]
    return math.hypot(pos[0] - first[0], pos[1] - first[1]) <= radius


def commit_or_cancel(ctx):
    """Finish open bezier pen path if drawable, else cancel. Safe to call anytime."""
    if ctx.bezier_pen is None:
        return False
    if len((ctx.bezier_pen or {}).get("anchors") or []) >= 2:
        return finish(ctx, close_path=False)
    cancel(ctx)
    return False
