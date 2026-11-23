"""Controller: snapping helpers (extracted from app_controller for SRP)."""
import math


def snap_radius(snap_enabled, snap_radius_value):
    return snap_radius_value if snap_enabled else 0


def alignment_guides_for_point(pt, other_strokes, sr, stroke_bbox):
    if sr <= 0 or not other_strokes:
        return []
    px, py = pt
    target_bbs = [stroke_bbox(s) for s in other_strokes]
    target_bbs = [b for b in target_bbs if b]
    best_x = None
    best_y = None
    for (tx0, ty0, tx1, ty1) in target_bbs:
        tcx = (tx0 + tx1) * 0.5
        tcy = (ty0 + ty1) * 0.5
        for tval in (tx0, tcx, tx1):
            d = abs(tval - px)
            if d <= sr and (best_x is None or d < best_x[0]):
                best_x = (d, tval, (tx0, ty0, tx1, ty1))
        for tval in (ty0, tcy, ty1):
            d = abs(tval - py)
            if d <= sr and (best_y is None or d < best_y[0]):
                best_y = (d, tval, (tx0, ty0, tx1, ty1))
    guides = []
    if best_x is not None:
        tbb = best_x[2]
        guides.append({"axis": "x", "pos": best_x[1], "y0": min(py, tbb[1]), "y1": max(py, tbb[3])})
    if best_y is not None:
        tbb = best_y[2]
        guides.append({"axis": "y", "pos": best_y[1], "x0": min(px, tbb[0]), "x1": max(px, tbb[2])})
    return guides


def snap_move_delta(strokes, sel_indices, dx, dy, sr, stroke_bbox, nearest_snap_point):
    if sr <= 0 or not sel_indices or (dx == 0 and dy == 0):
        return dx, dy, []
    sel_set = set(sel_indices)
    other = [(i, s) for i, s in enumerate(strokes) if i not in sel_set]
    if not other:
        return dx, dy, []
    xs, ys = [], []
    for si in sel_set:
        if 0 <= si < len(strokes):
            bb = stroke_bbox(strokes[si])
            if bb:
                x1, y1, x2, y2 = bb
                xs.extend([x1, x2]); ys.extend([y1, y2])
    if not xs:
        return dx, dy, []
    sx0, sx1 = min(xs), max(xs)
    sy0, sy1 = min(ys), max(ys)
    scx, scy = (sx0 + sx1) * 0.5, (sy0 + sy1) * 0.5
    mx0, mx1, mcx = sx0 + dx, sx1 + dx, scx + dx
    my0, my1, mcy = sy0 + dy, sy1 + dy, scy + dy

    target_bbs = []
    for _, st in other:
        tbb = stroke_bbox(st)
        if tbb:
            target_bbs.append(tbb)
    best_x = None
    best_y = None
    for (tx0, ty0, tx1, ty1) in target_bbs:
        tcx = (tx0 + tx1) * 0.5
        tcy = (ty0 + ty1) * 0.5
        for sval in (mx0, mcx, mx1):
            for tval in (tx0, tcx, tx1):
                d = abs(tval - sval)
                if d <= sr and (best_x is None or d < best_x[0]):
                    best_x = (d, tval - sval, tval, (tx0, ty0, tx1, ty1))
        for sval in (my0, mcy, my1):
            for tval in (ty0, tcy, ty1):
                d = abs(tval - sval)
                if d <= sr and (best_y is None or d < best_y[0]):
                    best_y = (d, tval - sval, tval, (tx0, ty0, tx1, ty1))

    guides = []
    ndx, ndy = dx, dy
    if best_x is not None:
        ndx += best_x[1]
        tbb = best_x[3]
        gy0 = min(my0, tbb[1])
        gy1 = max(my1, tbb[3])
        guides.append({"axis": "x", "pos": best_x[2], "y0": gy0, "y1": gy1})
    if best_y is not None:
        ndy += best_y[1]
        tbb = best_y[3]
        gx0 = min(mx0 + (best_x[1] if best_x else 0.0), tbb[0])
        gx1 = max(mx1 + (best_x[1] if best_x else 0.0), tbb[2])
        guides.append({"axis": "y", "pos": best_y[2], "x0": gx0, "x1": gx1})
    if best_x is not None or best_y is not None:
        return ndx, ndy, guides

    anchors = [
        (sx0, sy0), (scx, sy0), (sx1, sy0),
        (sx0, scy), (scx, scy), (sx1, scy),
        (sx0, sy1), (scx, sy1), (sx1, sy1),
    ]
    other_strokes = [s for _, s in other]
    best_adj = None
    best_d = sr + 1.0
    for ax, ay in anchors:
        tx, ty = ax + dx, ay + dy
        sp = nearest_snap_point((tx, ty), other_strokes, sr)
        if sp is not None:
            d = math.hypot(sp[0] - tx, sp[1] - ty)
            if d < best_d:
                best_d = d
                best_adj = (sp[0] - tx, sp[1] - ty)
    if best_adj is not None:
        return dx + best_adj[0], dy + best_adj[1], []
    return dx, dy, []


def snap_world(pos, guides, cfg, threshold_px=8.0):
    z = float(getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0)
    use_grid = bool(getattr(cfg, "SNAP_TO_GRID", False))
    if not use_grid and not guides:
        return pos
    # local import to avoid cycles
    from models import snap_point
    snapped, _kind = snap_point(
        pos, grid_size=float(getattr(cfg, "GRID_SIZE", 20.0) or 20.0),
        guides=guides, threshold=float(threshold_px) / z, use_grid=use_grid)
    return snapped
