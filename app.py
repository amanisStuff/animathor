import math
import sys

try:
    import cairo  # pycairo (often bundles Cairo on Windows)
    CAIRO_BACKEND = "pycairo"
except Exception:
    import cairocffi as cairo  # type: ignore
    CAIRO_BACKEND = "cairocffi"

import pygame

from bezier import stroke_to_beziers, fit_single_cubic_bezier

import os
try:
    import tkinter as tk
    from tkinter import filedialog as tk_filedialog
except Exception:
    tk = None
    tk_filedialog = None

LEFT_BAR_W = 56
CANVAS_W, HEIGHT = 980, 700
PANEL_W = 280
WIDTH = LEFT_BAR_W + CANVAS_W + PANEL_W
CANVAS_X = LEFT_BAR_W
PANEL_X = LEFT_BAR_W + CANVAS_W

BG_COLOR = (1.0, 1.0, 1.0)
ACTIVE_COLOR = (0.2, 0.4, 0.9)

PANEL_BG = (245, 247, 250)
PANEL_BORDER = (210, 215, 225)
TEXT_COLOR = (30, 35, 45)
MUTED_COLOR = (90, 100, 115)
BUTTON_BG = (255, 255, 255)
BUTTON_HOVER = (232, 238, 248)
BUTTON_BORDER = (180, 190, 205)
ACCENT = (60, 120, 220)
TOOLBAR_BG = (236, 239, 244)
TOOL_ACTIVE = (220, 232, 248)

STROKE_SWATCHES = [
    (0.1, 0.1, 0.15),
    (0.9, 0.2, 0.2),
    (0.15, 0.55, 0.2),
    (0.15, 0.35, 0.9),
    (0.95, 0.6, 0.1),
]
FILL_SWATCHES = [
    None,
    (0.85, 0.92, 1.0),
    (1.0, 0.9, 0.85),
    (0.88, 1.0, 0.88),
    (0.97, 0.88, 1.0),
    (1.0, 1.0, 1.0),
]


def make_cairo_surface(width, height):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    return surface


TRACE_ALGORITHMS = [
    ("fit", "Fit"),
    ("catmull-rom", "C-R"),
    ("single", "Single"),
]


def new_stroke(segs, stroke_color=(0.1, 0.1, 0.15), stroke_width=3.0, fill_color=None, corner_anchors=None, algorithm="fit"):
    return {
        "segs": segs,
        "stroke_color": stroke_color,
        "stroke_width": float(stroke_width),
        "fill_color": fill_color,
        # Anchors where two *strokes* were joined (merge/closure). These are corners.
        # Internal joins inside one drawn stroke remain smooth (symmetric handles).
        "corner_anchors": set(corner_anchors or ()),
        "algorithm": algorithm or "fit",
        "hidden_segs": set(),
    }


def segs_of(stroke):
    return stroke["segs"] if isinstance(stroke, dict) else stroke


def _corners(stroke):
    if isinstance(stroke, dict):
        return set(stroke.get("corner_anchors", ()))
    return set()


def _set_corners(stroke, corners):
    if isinstance(stroke, dict):
        out = dict(stroke)
        out["corner_anchors"] = set(corners)
        return out
    return stroke


def _shift_corners(corners, delta):
    return {(i + delta, name) for (i, name) in corners}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def color_rgb(c, default=(0.1, 0.1, 0.15)):
    if c is None:
        c = default
    return (float(c[0]), float(c[1]), float(c[2]))


def color_alpha(c, default=1.0):
    if c is None:
        return default
    if len(c) >= 4:
        return float(c[3])
    return default


def color_rgba(c, default=(0.1, 0.1, 0.15, 1.0)):
    if c is None:
        return default
    r, g, b = c[0], c[1], c[2]
    a = c[3] if len(c) >= 4 else 1.0
    return (float(r), float(g), float(b), float(a))


def set_color_alpha(c, alpha):
    rgb = color_rgb(c)
    return (rgb[0], rgb[1], rgb[2], float(clamp(alpha, 0.0, 1.0)))


def rgb_to_hsv(r, g, b, *_):
    """r,g,b in 0..1 -> h in 0..360, s,v in 0..1"""
    mx = max(r, g, b)
    mn = min(r, g, b)
    d = mx - mn
    if d == 0:
        h = 0.0
    elif mx == r:
        h = (60 * ((g - b) / d) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / d) + 120) % 360
    else:
        h = (60 * ((r - g) / d) + 240) % 360
    s = 0.0 if mx == 0 else d / mx
    v = mx
    return h, s, v


def hsv_to_rgb(h, s, v):
    """h in 0..360, s,v in 0..1 -> r,g,b in 0..1"""
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c
    if 0 <= h < 60:
        rp, gp, bp = c, x, 0
    elif 60 <= h < 120:
        rp, gp, bp = x, c, 0
    elif 120 <= h < 180:
        rp, gp, bp = 0, c, x
    elif 180 <= h < 240:
        rp, gp, bp = 0, x, c
    elif 240 <= h < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x
    return (rp + m, gp + m, bp + m)


def rgb_to_hex(rgb):
    r, g, b = [int(clamp(x, 0, 1) * 255) for x in color_rgb(rgb)]
    return f"#{r:02X}{g:02X}{b:02X}"


def stroke_start(stroke):
    segs = segs_of(stroke)
    return segs[0][0]


def stroke_end(stroke):
    segs = segs_of(stroke)
    return segs[-1][3]


def _pt_key(pt, eps=6.0):
    return (round(pt[0] / eps), round(pt[1] / eps))


def _build_endpoint_graph(strokes, eps=6.0):
    nodes = {}
    for stroke in strokes:
        segs = segs_of(stroke)
        if not segs:
            continue
        a = stroke_start(stroke)
        b = stroke_end(stroke)
        ka = _pt_key(a, eps)
        kb = _pt_key(b, eps)
        if ka not in nodes:
            nodes[ka] = {"pt": a, "degree": 0, "adj": set()}
        if kb not in nodes:
            nodes[kb] = {"pt": b, "degree": 0, "adj": set()}
        nodes[ka]["pt"] = a
        nodes[kb]["pt"] = b
        nodes[ka]["degree"] += 1
        nodes[kb]["degree"] += 1
        if ka != kb:
            nodes[ka]["adj"].add(kb)
            nodes[kb]["adj"].add(ka)
    return nodes


def _open_node_keys(strokes, eps=6.0):
    nodes = _build_endpoint_graph(strokes, eps=eps)
    visited = set()
    open_nodes = set()
    for start in nodes:
        if start in visited:
            continue
        stack = [start]
        comp = []
        visited.add(start)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nb in nodes[cur]["adj"]:
                if nb not in visited:
                    visited.add(nb)
                    stack.append(nb)
        is_closed_component = all(nodes[n]["degree"] >= 2 for n in comp)
        if not is_closed_component:
            open_nodes.update(comp)
    return open_nodes, nodes


def stroke_endpoints(strokes, include_closed=False):
    pts = []
    if include_closed:
        for stroke in strokes:
            if segs_of(stroke):
                pts.append(stroke_start(stroke))
                pts.append(stroke_end(stroke))
        return pts
    open_nodes, nodes = _open_node_keys(strokes)
    for k in open_nodes:
        pts.append(nodes[k]["pt"])
    return pts


def nearest_endpoint(pos, strokes, radius, extra_points=None):
    best = None
    best_d = radius
    candidates = stroke_endpoints(strokes)
    if extra_points:
        candidates.extend(extra_points)
    for pt in candidates:
        d = math.hypot(pos[0] - pt[0], pos[1] - pt[1])
        if d <= best_d:
            best_d = d
            best = pt
    return best


def nearest_snap_point(pos, strokes, radius, extra_points=None):
    """Nearest endpoint or point on any existing curve/edge within radius."""
    best = nearest_endpoint(pos, strokes, radius, extra_points=extra_points)
    best_d = math.hypot(pos[0] - best[0], pos[1] - best[1]) if best is not None else radius
    curve_pt = nearest_point_on_strokes(pos, strokes, best_d)
    if curve_pt is not None:
        # Prefer endpoint for connection when the curve snap is essentially at an endpoint
        if best is not None and math.hypot(best[0] - curve_pt[0], best[1] - curve_pt[1]) <= 8.0:
            return best
        return curve_pt
    return best


def snap_kind(pos, strokes, radius, extra_points=None):
    """Classify nearest snap target: 'connect' for endpoint, 'assist' for curve/edge."""
    pt = nearest_snap_point(pos, strokes, radius, extra_points=extra_points)
    if pt is None:
        return None
    ep = nearest_endpoint(pos, strokes, radius, extra_points=extra_points)
    if ep is not None and math.hypot(ep[0] - pt[0], ep[1] - pt[1]) <= 1e-6:
        return "connect"
    if extra_points:
        for p in extra_points:
            if p is not None and math.hypot(p[0] - pt[0], p[1] - pt[1]) <= 1e-6:
                return "connect"
    return "assist"


def draw_snap_point(pos, strokes, radius, shift_held, extra_points=None):
    """Snap target while drawing: curve/edge only when Shift is held, else endpoints."""
    if shift_held:
        return nearest_snap_point(pos, strokes, radius, extra_points=extra_points)
    return nearest_endpoint(pos, strokes, radius, extra_points=extra_points)


def draw_snap_info(pos, strokes, radius, shift_held, extra_points=None):
    pt = draw_snap_point(pos, strokes, radius, shift_held, extra_points=extra_points)
    if pt is None:
        return None, None
    if shift_held:
        kind = snap_kind(pos, strokes, radius, extra_points=extra_points) or "connect"
    else:
        kind = "connect"
    return pt, kind


def _drawing_sample_pos(cpos, points, strokes, snap_radius, shift_held, straight_line, fixed_end=None):
    extras = [points[0]] if points else None
    if fixed_end is not None:
        # redraw end is fixed; follow cursor during drag, finalization enforces fixed_end
        return cpos
    end_snap = draw_snap_point(cpos, strokes, snap_radius, shift_held, extra_points=extras)
    return end_snap if end_snap is not None else cpos


def _append_drawing_point(points, sample_pos, end_snap_active=False):
    if not points:
        return [sample_pos]
    pts = list(points)
    if math.hypot(sample_pos[0] - pts[-1][0], sample_pos[1] - pts[-1][1]) >= 2.0:
        pts.append(sample_pos)
    elif end_snap_active and pts[-1] != sample_pos:
        pts[-1] = sample_pos
    return pts


def advance_drawing_points(points, cpos, strokes, snap_radius, shift_held, straight_line, fixed_end=None):
    """Shared draw/redraw motion sampling with snapping and straight-line (V) mode."""
    if not points:
        return points
    sample_pos = _drawing_sample_pos(cpos, points, strokes, snap_radius, shift_held, straight_line, fixed_end=fixed_end)
    if straight_line:
        return [points[0], sample_pos]
    extras = [points[0]]
    end_snap_active = (fixed_end is None and draw_snap_point(cpos, strokes, snap_radius, shift_held, extra_points=extras) is not None)
    return _append_drawing_point(points, sample_pos, end_snap_active=end_snap_active)


def finalize_drawing_points(points, cpos, strokes, snap_radius, shift_held, straight_line, fixed_end=None):
    """Shared draw/redraw mouse-up finalization."""
    if not points:
        return points
    pts = list(points)
    extras = [pts[0]]
    if fixed_end is not None:
        sample_pos = tuple(fixed_end)
    else:
        end_snap = draw_snap_point(cpos, strokes, snap_radius, shift_held, extra_points=extras)
        sample_pos = end_snap if end_snap is not None else cpos
    if straight_line:
        pts = [pts[0], sample_pos]
    else:
        if len(pts) >= 1:
            if sample_pos != pts[-1] and math.hypot(sample_pos[0]-pts[-1][0], sample_pos[1]-pts[-1][1]) < 2.0 and fixed_end is None:
                pts[-1] = sample_pos
            elif pts[-1] != sample_pos:
                pts.append(sample_pos)
    return pts


def _dist_point_seg(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = clamp(t, 0.0, 1.0)
    proj = (ax + t * dx, ay + t * dy)
    return math.hypot(px - proj[0], py - proj[1])


def _cubic_point(p0, c1, c2, p3, t):
    mt = 1.0 - t
    x = (mt**3) * p0[0] + 3 * (mt**2) * t * c1[0] + 3 * mt * (t**2) * c2[0] + (t**3) * p3[0]
    y = (mt**3) * p0[1] + 3 * (mt**2) * t * c1[1] + 3 * mt * (t**2) * c2[1] + (t**3) * p3[1]
    return (x, y)


def _nearest_point_on_cubic(pos, seg, samples=24):
    best_pt = None
    best_d = float("inf")
    p0, c1, c2, p3 = seg
    prev = p0
    for i in range(1, samples + 1):
        t = i / samples
        pt = _cubic_point(p0, c1, c2, p3, t)
        # closest point on linear approximation between prev and pt
        px, py = pos
        ax, ay = prev
        bx, by = pt
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            proj = (ax, ay)
        else:
            u = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
            u = clamp(u, 0.0, 1.0)
            proj = (ax + u * dx, ay + u * dy)
        d = math.hypot(px - proj[0], py - proj[1])
        if d < best_d:
            best_d = d
            best_pt = proj
        prev = pt
    return best_pt, best_d


def nearest_point_on_strokes(pos, strokes, radius):
    best = None
    best_d = radius
    for stroke in strokes:
        segs = segs_of(stroke)
        for seg in segs:
            pt, d = _nearest_point_on_cubic(pos, seg)
            if d <= best_d and pt is not None:
                best_d = d
                best = pt
    return best


def _stroke_polyline(stroke, samples=12):
    pts = []
    segs = segs_of(stroke)
    if not segs:
        return pts
    pts.append(segs[0][0])
    for p0, c1, c2, p3 in segs:
        for i in range(1, samples + 1):
            t = i / samples
            pts.append(_cubic_point(p0, c1, c2, p3, t))
    return pts


def _point_in_poly(pos, poly):
    # ray casting
    x, y = pos
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def hit_test_stroke(pos, strokes, threshold=10.0):
    """Hit test strokes by curve proximity and filled interior (topmost first)."""
    for i in range(len(strokes) - 1, -1, -1):
        stroke = strokes[i]
        segs = segs_of(stroke)
        if not segs:
            continue
        # quick bbox reject (expanded by threshold)
        bb = stroke_bbox(stroke)
        if bb:
            x1, y1, x2, y2 = bb
            if not (x1 - threshold <= pos[0] <= x2 + threshold and y1 - threshold <= pos[1] <= y2 + threshold):
                continue
        # distance to actual curve
        for seg in segs:
            _, d = _nearest_point_on_cubic(pos, seg)
            if d <= threshold:
                return i
        # closed shape interior (select by area even if unfilled)
        if _is_closed_segs(segs, 6.0):
            poly = _stroke_polyline(stroke, samples=12)
            if _point_in_poly(pos, poly):
                return i
    return None


def hit_test_segment(stroke, pos, threshold=10.0):
    """Return segment index nearest to pos, or None."""
    segs = segs_of(stroke)
    best = None
    best_d = threshold
    for i, seg in enumerate(segs):
        pt, d = _nearest_point_on_cubic(pos, seg)
        if d <= best_d:
            best_d = d
            best = i
    return best


def redraw_curve_segment(stroke, seg_index, drawn_points):
    """Replace one curve segment by refitting drawn points to a single cubic.
    Keeps the original segment endpoints to preserve connectivity and point count."""
    segs = list(segs_of(stroke))
    if not (0 <= seg_index < len(segs)) or len(drawn_points) < 2:
        return stroke
    orig = segs[seg_index]
    p0, p3 = orig[0], orig[3]
    pts = list(drawn_points)
    # ensure fit respects original segment endpoints
    pts[0] = p0
    pts[-1] = p3
    fitted = fit_single_cubic_bezier(pts)
    if not fitted:
        return stroke
    new_seg = list(fitted[0])
    new_seg[0] = p0
    new_seg[3] = p3
    segs[seg_index] = tuple(new_seg)
    out = _copy_stroke(stroke) if isinstance(stroke, dict) else new_stroke(segs)
    if isinstance(out, dict):
        out["segs"] = segs
    return out


def _component_ranges(stroke):
    comps = _stroke_components(stroke)
    ranges = []
    start = 0
    for c in comps:
        segs = c.get("segs") or []
        count = len(segs)
        ranges.append((start, start + count))
        start += count
    return ranges


def hit_test_component(stroke, pos, threshold=10.0):
    segs = segs_of(stroke)
    ranges = _component_ranges(stroke)
    best = None
    best_d = threshold
    for ci, (s0, s1) in enumerate(ranges):
        for i in range(s0, min(s1, len(segs))):
            pt, d = _nearest_point_on_cubic(pos, segs[i])
            if d <= best_d:
                best_d = d
                best = ci
    # fallback if no components/ranges matched
    if best is None and segs:
        si = hit_test_segment(stroke, pos, threshold=threshold)
        if si is not None:
            return 0
    return best


def redraw_stroke_component(stroke, comp_index, drawn_points):
    """Redraw an original stroke component with its saved settings and same segment count."""
    if not isinstance(stroke, dict):
        return stroke
    comps = _stroke_components(stroke)
    if not (0 <= comp_index < len(comps)):
        return stroke
    comp = comps[comp_index]
    raw_points = list(drawn_points) if drawn_points else list(comp.get("raw_points") or [])
    if len(raw_points) < 2:
        return stroke
    max_pts = int(comp.get("draw_max_points", 4))
    algorithm = comp.get("algorithm", stroke.get("algorithm", "fit"))
    new_segs = stroke_to_beziers(
        raw_points, simplify_epsilon=2.5, tension=0.0,
        max_points=max_pts, algorithm=algorithm,
    )
    if not new_segs:
        return stroke
    # Rebuild full stroke segs by replacing this component's range
    ranges = _component_ranges(stroke)
    if comp_index >= len(ranges):
        return stroke
    s0, s1 = ranges[comp_index]
    all_segs = list(segs_of(stroke))
    # if lengths differ, adjust (keep as close as possible)
    all_segs[s0:s1] = list(new_segs)
    out = _copy_stroke(stroke)
    out["segs"] = all_segs
    comps2 = _stroke_components(out)
    if 0 <= comp_index < len(comps2):
        comps2[comp_index] = dict(comps2[comp_index])
        comps2[comp_index]["segs"] = list(new_segs)
        comps2[comp_index]["raw_points"] = [tuple(p) for p in raw_points]
    out["components"] = comps2
    # clear hidden segs for simplicity after structural change
    out["hidden_segs"] = set()
    return out


def hit_test_point(stroke, pos, radius=8.0):
    segs = segs_of(stroke)
    best = None
    best_d = radius
    names = ("p0", "c1", "c2", "p3")
    for i, seg in enumerate(segs):
        for j, name in enumerate(names):
            if name == "p0" and i > 0:
                continue
            pt = seg[j]
            d = math.hypot(pos[0] - pt[0], pos[1] - pt[1])
            if d <= best_d:
                best_d = d
                best = (i, name)
    return best


def _is_closed_segs(segs, eps=6.0):
    if not segs:
        return False
    return _pts_close(segs[0][0], segs[-1][3], eps)


def is_corner_anchor(stroke, seg_index, point_name):
    """Return True if this anchor is a corner (join between two drawn strokes).

    Rule:
    - Points where two strokes were joined/closed are corners (independent handles).
    - Remaining anchors (smooth joins inside a stroke) are symmetric (mirrored handles).
    """
    segs = segs_of(stroke)
    if not segs:
        return False
    if point_name == "c1":
        anchor_name = "p0"
    elif point_name == "c2":
        anchor_name = "p3"
    else:
        anchor_name = point_name
    return (seg_index, anchor_name) in _corners(stroke)


def translate_stroke(stroke, dx, dy):
    segs = segs_of(stroke)
    moved = []
    for p0, c1, c2, p3 in segs:
        moved.append((
            (p0[0] + dx, p0[1] + dy),
            (c1[0] + dx, c1[1] + dy),
            (c2[0] + dx, c2[1] + dy),
            (p3[0] + dx, p3[1] + dy),
        ))
    if isinstance(stroke, dict):
        out = dict(stroke)
        out["segs"] = moved
        return out
    return moved


def _mirror_handle(anchor, handle):
    return (2 * anchor[0] - handle[0], 2 * anchor[1] - handle[1])


def apply_affine(pt, cx, cy, ca, sa, sx, sy):
    """Apply scale (sx,sy) then rotate (ca,sa) around (cx,cy)."""
    x, y = (pt[0] - cx) * sx, (pt[1] - cy) * sy
    return (cx + x * ca - y * sa, cy + x * sa + y * ca)


def stroke_bbox(stroke):
    segs = segs_of(stroke)
    if not segs:
        return None
    xs, ys = [], []
    for p0, c1, c2, p3 in segs:
        for pt in (p0, c1, c2, p3):
            xs.append(pt[0]); ys.append(pt[1])
    return (min(xs), min(ys), max(xs), max(ys))


def transform_stroke(stroke, cx, cy, angle_rad, scale_x, scale_y=None):
    """Scale and rotate stroke around (cx,cy)."""
    if scale_y is None:
        scale_y = scale_x
    ca, sa = math.cos(angle_rad), math.sin(angle_rad)
    segs = segs_of(stroke)
    moved = []
    for p0, c1, c2, p3 in segs:
        moved.append((
            apply_affine(p0, cx, cy, ca, sa, scale_x, scale_y),
            apply_affine(c1, cx, cy, ca, sa, scale_x, scale_y),
            apply_affine(c2, cx, cy, ca, sa, scale_x, scale_y),
            apply_affine(p3, cx, cy, ca, sa, scale_x, scale_y),
        ))
    if isinstance(stroke, dict):
        out = dict(stroke)
        out["segs"] = moved
        return out
    return moved


def bbox_handles(bbox, rot_offset=22):
    """Return dict of handle_name -> (x,y) for bbox (x1,y1,x2,y2)."""
    x1, y1, x2, y2 = bbox
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    return {
        "nw": (x1, y1), "n": (mx, y1), "ne": (x2, y1),
        "e": (x2, my), "se": (x2, y2), "s": (mx, y2),
        "sw": (x1, y2), "w": (x1, my),
        "rot": (mx, y1 - rot_offset),
    }


def hit_test_bbox_handle(bbox, pos, radius=8.0):
    if bbox is None:
        return None
    for name, pt in bbox_handles(bbox).items():
        if math.hypot(pos[0] - pt[0], pos[1] - pt[1]) <= radius:
            return name
    return None


def point_in_bbox(bbox, pos):
    if bbox is None:
        return False
    x1, y1, x2, y2 = bbox
    return x1 <= pos[0] <= x2 and y1 <= pos[1] <= y2


def rects_intersect(a, b):
    if a is None or b is None:
        return False
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)


def normalize_rect(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _anchor_handle_slots(seg_list, seg_index, anchor_name, closed):
    """Slots [(seg_index, 'c1'|'c2')] for handles attached to an anchor."""
    n = len(seg_list)
    slots = []
    if anchor_name == "p0":
        slots.append((seg_index, "c1"))
        if seg_index > 0:
            slots.append((seg_index - 1, "c2"))
        elif closed and n > 1:
            slots.append((n - 1, "c2"))
    elif anchor_name == "p3":
        slots.append((seg_index, "c2"))
        if seg_index < n - 1:
            slots.append((seg_index + 1, "c1"))
        elif closed and n > 1:
            slots.append((0, "c1"))
    return slots


def set_stroke_point(stroke, seg_index, point_name, new_pos):
    segs = segs_of(stroke)
    idx_map = {"p0": 0, "c1": 1, "c2": 2, "p3": 3}
    j = idx_map[point_name]
    seg_list = [list(s) for s in segs]
    old_pt = tuple(seg_list[seg_index][j])
    new_pt = (float(new_pos[0]), float(new_pos[1]))
    seg_list[seg_index][j] = new_pt

    closed = _is_closed_segs(segs)
    n = len(seg_list)

    if point_name in ("p0", "p3"):
        # Anchor moved: handles attached to this anchor follow it.
        dx = new_pt[0] - old_pt[0]
        dy = new_pt[1] - old_pt[1]
        for si, hname in _anchor_handle_slots(seg_list, seg_index, point_name, closed):
            hj = 1 if hname == "c1" else 2
            h = seg_list[si][hj]
            seg_list[si][hj] = (h[0] + dx, h[1] + dy)

        # Keep adjacent segment anchors joined
        if point_name == "p3" and seg_index + 1 < n:
            seg_list[seg_index + 1][0] = new_pt
        elif point_name == "p0" and seg_index > 0:
            seg_list[seg_index - 1][3] = new_pt
        elif point_name == "p0" and seg_index == 0 and closed and n > 1:
            seg_list[-1][3] = new_pt
        elif point_name == "p3" and seg_index == n - 1 and closed and n > 1:
            seg_list[0][0] = new_pt

        # Symmetric anchors keep their two handles mirrored across the anchor.
        # Corner anchors (joins between drawn strokes) keep independent handles.
        if not is_corner_anchor(stroke, seg_index, point_name):
            slots = _anchor_handle_slots(seg_list, seg_index, point_name, closed)
            if len(slots) >= 2:
                (s1, h1), (s2, h2) = slots[0], slots[1]
                j1 = 1 if h1 == "c1" else 2
                j2 = 1 if h2 == "c1" else 2
                seg_list[s2][j2] = _mirror_handle(new_pt, seg_list[s1][j1])

    elif point_name in ("c1", "c2"):
        # Handle moved. For symmetric anchors, mirror the opposite handle.
        anchor_name = "p0" if point_name == "c1" else "p3"
        anchor = tuple(seg_list[seg_index][0 if anchor_name == "p0" else 3])
        anchor = (float(anchor[0]), float(anchor[1]))
        if not is_corner_anchor(stroke, seg_index, anchor_name):
            slots = _anchor_handle_slots(seg_list, seg_index, anchor_name, closed)
            my = (seg_index, point_name)
            for si, hname in slots:
                if (si, hname) == my:
                    continue
                hj = 1 if hname == "c1" else 2
                seg_list[si][hj] = _mirror_handle(anchor, new_pt)
                break

    new_segs = [tuple(s) for s in seg_list]
    if isinstance(stroke, dict):
        out = dict(stroke)
        out["segs"] = new_segs
        return out
    return new_segs


def reverse_stroke(stroke):
    segs = segs_of(stroke)
    rev = []
    for p0, c1, c2, p3 in reversed(segs):
        rev.append((p3, c2, c1, p0))
    if isinstance(stroke, dict):
        out = _copy_stroke(stroke)
        out["segs"] = rev
        n = len(segs)
        out["corner_anchors"] = {
            (n - 1 - i, "p3" if name == "p0" else "p0")
            for (i, name) in _corners(stroke)
        }
        # reverse components to match segment order
        comps = out.get("components") or []
        if comps:
            rev_comps = []
            for c in reversed(comps):
                rc = dict(c)
                csegs = c.get("segs") or []
                if csegs:
                    rc["segs"] = [(p3, c2, c1, p0) for (p0, c1, c2, p3) in reversed(csegs)]
                else:
                    rc["segs"] = []  # will be inconsistent, but fallback
                rev_comps.append(rc)
            out["components"] = rev_comps
        # hidden segs mapped
        hidden = set(out.get("hidden_segs", set()))
        out["hidden_segs"] = {n - 1 - i for i in hidden}
        return out
    return rev


def _pts_close(a, b, eps=6.0):
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= eps


def _with_segs(stroke, segs):
    if isinstance(stroke, dict):
        out = dict(stroke)
        out["segs"] = segs
        return out
    return segs


def _copy_stroke(stroke):
    if not isinstance(stroke, dict):
        return list(stroke)
    out = dict(stroke)
    out["segs"] = list(segs_of(stroke))
    if "corner_anchors" in out:
        out["corner_anchors"] = set(out.get("corner_anchors", set()))
    if "hidden_segs" in out:
        out["hidden_segs"] = set(out.get("hidden_segs", set()))
    if "components" in out:
        out["components"] = [dict(c) for c in (out.get("components") or [])]
    return out


def _close_path_if_needed(stroke, eps=6.0):
    """If a path's endpoints are within eps, make them exactly identical.

    Closing a path joins the two ends, so the closure anchor is marked as a corner.
    """
    segs = segs_of(stroke)
    if not segs:
        return stroke
    start = segs[0][0]
    end = segs[-1][3]
    if not _pts_close(start, end, eps):
        return stroke
    segs2 = list(segs)
    if start != end:
        last = segs2[-1]
        segs2[-1] = (last[0], last[1], last[2], (float(start[0]), float(start[1])))
    out = _with_segs(stroke, segs2)
    n = len(segs2)
    corners = _corners(out) | {(0, "p0"), (n - 1, "p3")}
    return _set_corners(out, corners)


def _stroke_components(stroke):
    if isinstance(stroke, dict) and stroke.get("components"):
        return [dict(c) for c in (stroke.get("components") or [])]
    # fallback: treat whole stroke as one component
    if isinstance(stroke, dict):
        return [{
            "raw_points": list(stroke.get("raw_points", [])) if stroke.get("raw_points") else [],
            "draw_max_points": int(stroke.get("draw_max_points", 4)),
            "algorithm": stroke.get("algorithm", "fit"),
            "segs": list(segs_of(stroke)),
        }]
    return [{"raw_points": [], "draw_max_points": 4, "algorithm": "fit", "segs": list(segs_of(stroke))}]


def merge_connected_strokes(strokes, eps=6.0):
    paths = [s for s in strokes if segs_of(s)]
    changed = True
    while changed:
        changed = False
        n = len(paths)
        for i in range(n):
            a = paths[i]
            a_segs = segs_of(a)
            if not a_segs:
                continue
            a_start, a_end = a_segs[0][0], a_segs[-1][3]
            for j in range(i + 1, n):
                b = paths[j]
                b_segs = segs_of(b)
                if not b_segs:
                    continue
                b_start, b_end = b_segs[0][0], b_segs[-1][3]
                merged = None
                merged_comps = None
                if _pts_close(a_end, b_start, eps):
                    # A followed by B
                    b2 = list(b_segs)
                    b2[0] = (a_end, b2[0][1], b2[0][2], b2[0][3])
                    na = len(a_segs)
                    corners = _corners(a) | _shift_corners(_corners(b), na) | {(na - 1, "p3"), (na, "p0")}
                    merged = _set_corners(_with_segs(a, list(a_segs) + b2), corners)
                    merged_comps = _stroke_components(a) + _stroke_components(b)
                elif _pts_close(a_end, b_end, eps):
                    # A followed by reversed B
                    rb = reverse_stroke(b)
                    rb_segs = list(segs_of(rb))
                    rb_segs[0] = (a_end, rb_segs[0][1], rb_segs[0][2], rb_segs[0][3])
                    na = len(a_segs)
                    corners = _corners(a) | _shift_corners(_corners(rb), na) | {(na - 1, "p3"), (na, "p0")}
                    merged = _set_corners(_with_segs(a, list(a_segs) + rb_segs), corners)
                    merged_comps = _stroke_components(a) + _stroke_components(rb)
                elif _pts_close(a_start, b_end, eps):
                    # B followed by A
                    a2 = list(a_segs)
                    a2[0] = (b_end, a2[0][1], a2[0][2], a2[0][3])
                    nb = len(b_segs)
                    corners = _corners(b) | _shift_corners(_corners(a), nb) | {(nb - 1, "p3"), (nb, "p0")}
                    merged = _set_corners(_with_segs(b, list(b_segs) + a2), corners)
                    merged_comps = _stroke_components(b) + _stroke_components(a)
                elif _pts_close(a_start, b_start, eps):
                    # Reversed B followed by A
                    rb = reverse_stroke(b)
                    rb_segs = list(segs_of(rb))
                    a2 = list(a_segs)
                    a2[0] = (rb_segs[-1][3], a2[0][1], a2[0][2], a2[0][3])
                    nb = len(rb_segs)
                    corners = _corners(rb) | _shift_corners(_corners(a), nb) | {(nb - 1, "p3"), (nb, "p0")}
                    merged = _set_corners(_with_segs(rb, rb_segs + a2), corners)
                    merged_comps = _stroke_components(rb) + _stroke_components(a)
                if merged is not None:
                    if isinstance(merged, dict) and merged_comps is not None:
                        merged["components"] = merged_comps
                        # hidden segs offsets across merges are complex; reset for safety
                        merged["hidden_segs"] = set()
                    paths[i] = _close_path_if_needed(merged, eps=eps)
                    paths.pop(j)
                    changed = True
                    break
            if changed:
                break
    for i in range(len(paths)):
        paths[i] = _close_path_if_needed(paths[i], eps=eps)
    return paths


def draw_stroke_path(ctx, stroke):
    segs = segs_of(stroke)
    if not segs:
        return False
    hidden = set()
    if isinstance(stroke, dict):
        hidden = set(stroke.get("hidden_segs", set()) or set())
    visible = [i for i in range(len(segs)) if i not in hidden]
    if not visible:
        return False
    ctx.new_path()
    drew = False
    for i in range(len(segs)):
        if i in hidden:
            continue
        p0, c1, c2, p3 = segs[i]
        if not drew or not _pts_close(segs[i][0], segs[i - 1][3], 1e-3):
            ctx.move_to(p0[0], p0[1])
        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
        drew = True
    # if closed and fully visible, close path for nicer fill
    if len(visible) == len(segs) and _pts_close(segs[0][0], segs[-1][3], 6.0):
        ctx.close_path()
    return True


def _selection_set(selected_indices):
    if selected_indices is None:
        return set()
    if isinstance(selected_indices, int):
        return {selected_indices}
    return set(selected_indices)


def combined_bbox(strokes, indices):
    xs, ys = [], []
    for i in indices:
        if 0 <= i < len(strokes):
            bb = stroke_bbox(strokes[i])
            if bb:
                x1, y1, x2, y2 = bb
                xs.extend([x1, x2]); ys.extend([y1, y2])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def draw_scene(cairo_surface, strokes, active_stroke=None, snap_point=None, selected_index=None, selected_indices=None, edit_mode=False, selection_submode="transform", selected_curve=None, snap_kind="connect", redrawing_curve=None, ref_img=None):
    # Backward compat: selected_index (single) or selected_indices (collection)
    if selected_indices is None and selected_index is not None:
        selected_indices = selected_index
    sel_set = _selection_set(selected_indices)

    ctx = cairo.Context(cairo_surface)
    try:
        ctx.set_antialias(cairo.ANTIALIAS_BEST)
    except Exception:
        pass
    ctx.set_source_rgb(*BG_COLOR)
    ctx.paint()

    # Reference image, behind strokes
    if ref_img and ref_img.get("visible", True) and ref_img.get("surface") is not None:
        try:
            rsurf = ref_img["surface"]
            ctx.save()
            ctx.translate(float(ref_img.get("x", 0)), float(ref_img.get("y", 0)))
            s = float(ref_img.get("scale", 1.0))
            ctx.scale(s, s)
            ctx.set_source_surface(rsurf, 0, 0)
            ctx.paint_with_alpha(clamp(float(ref_img.get("opacity", 0.5)), 0.0, 1.0))
            ctx.restore()
        except Exception:
            pass

    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    redraw_target = None
    if redrawing_curve is not None:
        redraw_target = (redrawing_curve.get("stroke_idx"), redrawing_curve.get("comp_idx", redrawing_curve.get("seg_idx")))

    for idx, stroke in enumerate(strokes):
        segs = segs_of(stroke)
        if not segs:
            continue
        stroke_color = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if isinstance(stroke, dict) else (0.1, 0.1, 0.15)
        stroke_width = stroke.get("stroke_width", 3.0) if isinstance(stroke, dict) else 3.0
        fill_color = stroke.get("fill_color") if isinstance(stroke, dict) else None
        is_selected_stroke = (idx in sel_set and edit_mode)

        if redraw_target and redraw_target[0] == idx:
            comp_i = redraw_target[1]
            ranges = _component_ranges(stroke)
            in_redraw = set()
            if 0 <= comp_i < len(ranges):
                s0, s1 = ranges[comp_i]
                in_redraw = set(range(s0, min(s1, len(segs))))
            hidden = set(stroke.get("hidden_segs", set()) or set()) if isinstance(stroke, dict) else set()

            # draw non-redraw, non-hidden segments normally
            normal_segs = [i for i in range(len(segs)) if i not in in_redraw and i not in hidden]
            if normal_segs:
                # selection highlight for normal part
                if is_selected_stroke:
                    ctx.new_path()
                    for i in normal_segs:
                        p0, c1, c2, p3 = segs[i]
                        ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                    ctx.set_source_rgba(0.1, 0.45, 0.95, 0.35)
                    ctx.set_line_width(stroke_width + 4.0)
                    ctx.stroke()
                ctx.new_path()
                for i in normal_segs:
                    p0, c1, c2, p3 = segs[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                ctx.set_source_rgba(*color_rgba(stroke_color, (0.1, 0.1, 0.15, 1.0)))
                ctx.set_line_width(stroke_width)
                ctx.stroke()

            # draw redrawn component as bright yellow low-opacity template
            if in_redraw:
                ctx.new_path()
                for i in sorted(in_redraw):
                    p0, c1, c2, p3 = segs[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                ctx.set_source_rgba(1.0, 1.0, 0.0, 0.35)
                ctx.set_line_width(max(stroke_width, 2.0))
                ctx.stroke()
            continue

        # Selection highlight behind the stroke so the actual stroke color stays visible
        if is_selected_stroke and draw_stroke_path(ctx, stroke):
            ctx.set_source_rgba(0.1, 0.45, 0.95, 0.35)
            ctx.set_line_width(stroke_width + 4.0)
            ctx.stroke()

        if fill_color is not None:
            if draw_stroke_path(ctx, stroke):
                ctx.set_source_rgba(*color_rgba(fill_color, (0.0, 0.0, 0.0, 1.0)))
                ctx.fill_preserve()
                ctx.set_source_rgba(*color_rgba(stroke_color, (0.1, 0.1, 0.15, 1.0)))
                ctx.set_line_width(stroke_width)
                ctx.stroke()
        else:
            if draw_stroke_path(ctx, stroke):
                ctx.set_source_rgba(*color_rgba(stroke_color, (0.1, 0.1, 0.15, 1.0)))
                ctx.set_line_width(stroke_width)
                ctx.stroke()

    # Draw selection overlays (nodes for single selection, combined bbox for transform)
    if edit_mode and sel_set:
        selected_in_range = [i for i in sel_set if 0 <= i < len(strokes)]
        # Highlight selected stroke/component in curve edit mode
        if selection_submode == "curve" and selected_curve is not None:
            si, comp_i = selected_curve
            if si in selected_in_range and 0 <= si < len(strokes):
                segs = segs_of(strokes[si])
                ranges = _component_ranges(strokes[si])
                if 0 <= comp_i < len(ranges):
                    s0, s1 = ranges[comp_i]
                    for seg_i in range(s0, min(s1, len(segs))):
                        p0, c1, c2, p3 = segs[seg_i]
                        ctx.new_path()
                        ctx.move_to(p0[0], p0[1])
                        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                        ctx.set_source_rgba(1.0, 0.45, 0.1, 0.9)
                        w = strokes[si].get("stroke_width", 3.0) if isinstance(strokes[si], dict) else 3.0
                        ctx.set_line_width(max(4.0, w + 2.0))
                        ctx.stroke()
        if selection_submode == "nodes" and len(selected_in_range) == 1:
            idx = selected_in_range[0]
            segs = segs_of(strokes[idx])
            ctx.set_source_rgba(0.4, 0.5, 0.6, 0.8)
            ctx.set_line_width(1.0)
            for si, (p0, c1, c2, p3) in enumerate(segs):
                ctx.move_to(p0[0], p0[1]); ctx.line_to(c1[0], c1[1])
                ctx.move_to(p3[0], p3[1]); ctx.line_to(c2[0], c2[1])
            ctx.stroke()
            for si, (p0, c1, c2, p3) in enumerate(segs):
                if si == 0:
                    for pt in (p0,):
                        ctx.set_source_rgb(1, 1, 1); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.fill()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(2.0); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.stroke()
                for pt in (p3,):
                    ctx.set_source_rgb(1, 1, 1); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(2.0); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.stroke()
                for pt in (c1, c2):
                    ctx.set_source_rgb(1, 1, 1); ctx.rectangle(pt[0]-3.5, pt[1]-3.5, 7, 7); ctx.fill_preserve()
                    ctx.set_source_rgb(0.85, 0.35, 0.2); ctx.set_line_width(1.5); ctx.stroke()
        elif selection_submode == "transform":
            bbox = combined_bbox(strokes, selected_in_range)
            if bbox:
                x1, y1, x2, y2 = bbox
                try:
                    ctx.set_dash([6, 4])
                except Exception:
                    pass
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.5)
                ctx.rectangle(x1, y1, x2 - x1, y2 - y1)
                ctx.stroke()
                try:
                    ctx.set_dash([])
                except Exception:
                    pass
                handles = bbox_handles(bbox)
                mx = (x1 + x2) / 2
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.0)
                ctx.move_to(mx, y1); ctx.line_to(handles["rot"][0], handles["rot"][1])
                ctx.stroke()
                for name, pt in handles.items():
                    if name == "rot":
                        ctx.set_source_rgb(1, 1, 1); ctx.arc(pt[0], pt[1], 5.0, 0, 2*math.pi); ctx.fill()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(1.5); ctx.arc(pt[0], pt[1], 5.0, 0, 2*math.pi); ctx.stroke()
                    else:
                        ctx.set_source_rgb(1, 1, 1); ctx.rectangle(pt[0]-4, pt[1]-4, 8, 8); ctx.fill_preserve()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(1.5); ctx.stroke()
        elif selection_submode == "nodes" and len(selected_in_range) > 1:
            # Multi-selection: show combined bbox (node editing requires single selection)
            bbox = combined_bbox(strokes, selected_in_range)
            if bbox:
                x1, y1, x2, y2 = bbox
                try:
                    ctx.set_dash([4, 4])
                except Exception:
                    pass
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.2)
                ctx.rectangle(x1, y1, x2 - x1, y2 - y1)
                ctx.stroke()
                try:
                    ctx.set_dash([])
                except Exception:
                    pass

    if active_stroke and len(active_stroke) >= 2:
        ctx.set_source_rgb(*ACTIVE_COLOR)
        ctx.set_line_width(2.0)
        ctx.new_path()
        ctx.move_to(active_stroke[0][0], active_stroke[0][1])
        for x, y in active_stroke[1:]:
            ctx.line_to(x, y)
        ctx.stroke()

    if snap_point is not None:
        x, y = snap_point
        if snap_kind == "assist":
            r = 10.0
            ctx.new_path()
            ctx.move_to(x, y - r); ctx.line_to(x + r, y); ctx.line_to(x, y + r); ctx.line_to(x - r, y); ctx.close_path()
            ctx.set_source_rgba(0.2, 0.6, 1.0, 0.22)
            ctx.fill_preserve()
            ctx.set_source_rgb(0.15, 0.45, 0.95)
            ctx.set_line_width(2.0)
            ctx.stroke()
            ctx.new_path()
            ctx.move_to(x, y - 2.5); ctx.line_to(x + 2.5, y); ctx.line_to(x, y + 2.5); ctx.line_to(x - 2.5, y); ctx.close_path()
            ctx.fill()
        else:
            ctx.set_source_rgba(0.2, 0.6, 1.0, 0.25)
            ctx.arc(x, y, 11.0, 0, 2 * math.pi); ctx.fill()
            ctx.set_source_rgb(0.15, 0.45, 0.95)
            ctx.set_line_width(2.0)
            ctx.arc(x, y, 11.0, 0, 2 * math.pi); ctx.stroke()
            ctx.arc(x, y, 2.5, 0, 2 * math.pi); ctx.fill()

    cairo_surface.flush()


def surface_to_pygame(cairo_surface):
    width = cairo_surface.get_width()
    height = cairo_surface.get_height()
    buf = cairo_surface.get_data()
    try:
        data = buf.tobytes()
    except Exception:
        data = bytes(buf)
    return pygame.image.frombuffer(data, (width, height), "BGRA")


def load_reference_image(path):
    """Load image file into a cairo ImageSurface (ARGB32) for reference drawing."""
    if not path:
        return None
    try:
        # Prefer cairo PNG loader when possible
        if str(path).lower().endswith(".png"):
            surf = cairo.ImageSurface.create_from_png(path)
            w, h = surf.get_width(), surf.get_height()
        else:
            img = pygame.image.load(path).convert_alpha()
            w, h = img.get_width(), img.get_height()
            data = pygame.image.tostring(img, "BGRA")
            buf = bytearray(data)
            surf = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, w, h)
            # keep buffer alive
            surf._buf = buf
        return {"surface": surf, "w": w, "h": h, "x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 0.5, "visible": True, "path": path}
    except Exception:
        return None


def pick_reference_image_path():
    if tk is None or tk_filedialog is None:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        path = tk_filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp"), ("All files", "*.*")],
        )
        root.destroy()
        return path or None
    except Exception:
        return None


class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def draw(self, screen, font, mouse_pos, active=False):
        hover = self.rect.collidepoint(mouse_pos)
        if active:
            color = TOOL_ACTIVE
            border = ACCENT
            tw = 2
        else:
            color = BUTTON_HOVER if hover else BUTTON_BG
            border = BUTTON_BORDER
            tw = 1
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, border, self.rect, width=tw, border_radius=6)
        txt = font.render(self.label, True, ACCENT if active else TEXT_COLOR)
        screen.blit(txt, txt.get_rect(center=self.rect.center))

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class Slider:
    def __init__(self, x, y, w, min_v, max_v, value):
        self.track = pygame.Rect(x, y, w, 6)
        self.min_v = min_v
        self.max_v = max_v
        self.value = value
        self.dragging = False
        self.handle_r = 8

    def _value_to_x(self):
        if self.max_v == self.min_v:
            return self.track.x
        t = (self.value - self.min_v) / (self.max_v - self.min_v)
        return int(self.track.x + t * self.track.w)

    def _x_to_value(self, x):
        t = (x - self.track.x) / max(1, self.track.w)
        v = self.min_v + t * (self.max_v - self.min_v)
        return int(round(clamp(v, self.min_v, self.max_v)))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hx = self._value_to_x()
            hy = self.track.centery
            handle_rect = pygame.Rect(hx - 12, hy - 12, 24, 24)
            if handle_rect.collidepoint(event.pos) or self.track.inflate(0, 18).collidepoint(event.pos):
                self.dragging = True
                self.value = self._x_to_value(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._x_to_value(event.pos[0])
            return True
        return False

    def draw(self, screen):
        pygame.draw.rect(screen, (220, 225, 235), self.track, border_radius=3)
        hx = self._value_to_x()
        filled = pygame.Rect(self.track.x, self.track.y, max(0, hx - self.track.x), self.track.h)
        pygame.draw.rect(screen, ACCENT, filled, border_radius=3)
        pygame.draw.circle(screen, (255, 255, 255), (hx, self.track.centery), self.handle_r)
        pygame.draw.circle(screen, ACCENT, (hx, self.track.centery), self.handle_r, width=2)


def draw_icon(screen, kind, rect, active):
    cx, cy = rect.center
    color = ACCENT if active else (70, 80, 95)
    if kind == "draw":
        # pencil
        pygame.draw.line(screen, color, (cx - 8, cy + 8), (cx + 6, cy - 6), 3)
        pygame.draw.line(screen, color, (cx + 6, cy - 6), (cx + 10, cy - 10), 3)
        pygame.draw.polygon(screen, color, [(cx - 10, cy + 10), (cx - 4, cy + 9), (cx - 9, cy + 4)])
    elif kind == "selection":
        # cursor/arrow (same as former "edit")
        pts = [(cx - 7, cy - 10), (cx - 7, cy + 8), (cx - 2, cy + 3), (cx + 2, cy + 10), (cx + 5, cy + 8), (cx + 1, cy + 1), (cx + 7, cy + 1)]
        pygame.draw.polygon(screen, color, pts)


def draw_left_toolbar(screen, mouse_pos, tool_mode, btn_draw, btn_select):
    bar = pygame.Rect(0, 0, LEFT_BAR_W, HEIGHT)
    pygame.draw.rect(screen, TOOLBAR_BG, bar)
    pygame.draw.line(screen, PANEL_BORDER, (LEFT_BAR_W - 1, 0), (LEFT_BAR_W - 1, HEIGHT), 2)
    for kind, btn in (("draw", btn_draw), ("selection", btn_select)):
        active = (tool_mode == kind)
        hover = btn.rect.collidepoint(mouse_pos)
        bg = TOOL_ACTIVE if active else (BUTTON_HOVER if hover else (248, 250, 252))
        border = ACCENT if active else BUTTON_BORDER
        pygame.draw.rect(screen, bg, btn.rect, border_radius=8)
        pygame.draw.rect(screen, border, btn.rect, width=2 if active else 1, border_radius=8)
        draw_icon(screen, kind, btn.rect, active)


def draw_swatch(screen, rect, color, selected, mouse_pos):
    hover = rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=4)
    inner = rect.inflate(-6, -6)
    if color is None:
        # "none" swatch
        pygame.draw.rect(screen, (250, 250, 250), inner, border_radius=3)
        pygame.draw.line(screen, (200, 60, 60), inner.topleft, inner.bottomright, 2)
    else:
        rgb = tuple(int(c * 255) for c in color_rgb(color))
        pygame.draw.rect(screen, rgb, inner, border_radius=3)
    border = ACCENT if selected else (ACCENT if hover else BUTTON_BORDER)
    pygame.draw.rect(screen, border, rect, width=2 if selected else 1, border_radius=4)


def draw_panel(screen, fonts, mouse_pos, state):
    font, font_small, font_title = fonts
    panel_rect = pygame.Rect(PANEL_X, 0, PANEL_W, HEIGHT)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    pygame.draw.line(screen, PANEL_BORDER, (PANEL_X, 0), (PANEL_X, HEIGHT), 2)

    x = PANEL_X + 20
    y = 18
    title = font_title.render("Draw" if state["tool_mode"] == "draw" else "Selection", True, TEXT_COLOR)
    screen.blit(title, (x, y))
    y += 36

    if state["tool_mode"] == "draw":
        # Points control
        label = font.render("Points / curve", True, TEXT_COLOR)
        screen.blit(label, (x, y)); y += 24
        limit = state["BOOST_MAX_POINTS"] if state["boost_points"] else state["NORMAL_MAX_POINTS"]
        val = font_title.render(str(state["max_points"]), True, ACCENT)
        screen.blit(val, (x, y - 2))
        hint = font_small.render(f"(2 - {limit})", True, MUTED_COLOR)
        screen.blit(hint, (x + val.get_width() + 10, y + 4)); y += 32
        state["slider"].track.topleft = (x, y)
        state["slider"].track.width = PANEL_W - 40
        state["slider"].draw(screen); y += 24
        b = state["buttons"]["boost"]
        b.rect.topleft = (x, y)
        b.label = "Boost: ON" if state["boost_points"] else "Boost limit"
        b.draw(screen, font, mouse_pos, active=state["boost_points"]); y += 44

        # Tracing algorithm (per new stroke)
        screen.blit(font.render("Tracing", True, TEXT_COLOR), (x, y)); y += 22
        algo = state.get("trace_algorithm", "fit")
        rects = {}
        bw = (PANEL_W - 40 - 8) // 3
        for i, (key, label) in enumerate(TRACE_ALGORITHMS):
            r = pygame.Rect(x + i * (bw + 4), y, bw, 28)
            rects[key] = r
            active = (algo == key)
            bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r, 2 if active else 1, border_radius=6)
            t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
        state["trace_algo_rects"] = rects
        y += 36

        # Reference image
        screen.blit(font.render("Reference image", True, TEXT_COLOR), (x, y)); y += 22
        ref = state.get("reference_image")
        bw3 = (PANEL_W - 40 - 16) // 3
        load_r = pygame.Rect(x, y, bw3, 28)
        vis_r = pygame.Rect(x + bw3 + 8, y, bw3, 28)
        clear_r = pygame.Rect(x + (bw3 + 8) * 2, y, PANEL_W - 40 - (bw3 + 8) * 2, 28)
        state["ref_load_rect"] = load_r
        state["ref_vis_rect"] = vis_r
        state["ref_clear_rect"] = clear_r
        vis_label = "Hide" if (ref and ref.get("visible", True)) else "Show"
        for r, label in ((load_r, "Load"), (vis_r, vis_label), (clear_r, "Clear")):
            bg = BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, BUTTON_BORDER, r, 1, border_radius=6)
            t = font_small.render(label, True, TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
        y += 34
        if ref and ref.get("surface") is not None:
            op = int(round(clamp(ref.get("opacity", 0.5), 0.0, 1.0) * 100))
            screen.blit(font_small.render(f"Opacity {op}%  (Alt+drag to move)", True, MUTED_COLOR), (x, y)); y += 18
            bar = pygame.Rect(x, y, PANEL_W - 40, 10)
            state["ref_opacity_rect"] = bar
            pygame.draw.rect(screen, (225, 228, 235), bar, border_radius=4)
            fill_w = int(bar.w * clamp(ref.get("opacity", 0.5), 0.0, 1.0))
            if fill_w > 0:
                pygame.draw.rect(screen, ACCENT, (bar.x, bar.y, fill_w, bar.h), border_radius=4)
            pygame.draw.rect(screen, BUTTON_BORDER, bar, 1, border_radius=4)
            y += 18
        else:
            state["ref_opacity_rect"] = pygame.Rect(0, 0, 0, 0)
            screen.blit(font_small.render("No reference image", True, MUTED_COLOR), (x, y)); y += 18
        y += 4

        label2 = font.render("Actions", True, TEXT_COLOR)
        screen.blit(label2, (x, y)); y += 28
        for i, b in enumerate(state["buttons"]["actions"]):
            b.rect.topleft = (x, y + i * 42)
            b.draw(screen, font, mouse_pos)
        y += len(state["buttons"]["actions"]) * 42 + 12

        stats = font_small.render(f"Strokes: {state['stroke_count']} | Backend: {CAIRO_BACKEND}", True, MUTED_COLOR)
        screen.blit(stats, (x, y)); y += 24
        help_lines = [
            "Drag on canvas to draw.",
            "Hover endpoints to snap.",
            "Connected edges auto-merge.",
            "Close shape: snap end to start.",
            "Closed shapes can't be extended.",
            "Shortcuts: Ctrl+Z, C, Esc",
        ]
    else:
        # Selection mode: transform operations and modern color selection
        sel_strokes = state.get("selected_strokes", set())
        sel_count = len(sel_strokes)
        # Submode toggle: Transform / Edit Nodes / Curve
        submode = state.get("selection_submode", "transform")
        toggle = pygame.Rect(x, y, PANEL_W - 40, 30)
        state["nodes_toggle_rect"] = toggle
        pygame.draw.rect(screen, BUTTON_BG, toggle, border_radius=6)
        pygame.draw.rect(screen, BUTTON_BORDER, toggle, 1, border_radius=6)
        modes = (("Transform", "transform"), ("Nodes", "nodes"), ("Curve", "curve"))
        part = toggle.w // len(modes)
        for i, (label, key) in enumerate(modes):
            r = pygame.Rect(toggle.x + i * part, toggle.y, part if i < len(modes)-1 else toggle.w - i*part, toggle.h)
            active = (submode == key)
            if active:
                pygame.draw.rect(screen, TOOL_ACTIVE, r.inflate(-4, -4), border_radius=5)
            t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
        y += 38

        sel_stroke = state.get("selected_obj")
        # Curve/stroke-edit controls (single selection in curve mode)
        state.setdefault("curve_hide_rect", pygame.Rect(0,0,0,0))
        state.setdefault("curve_redraw_rect", pygame.Rect(0,0,0,0))
        if submode == "curve" and sel_count == 1 and sel_stroke is not None:
            sc = state.get("selected_curve")
            if sc and sc[0] in sel_strokes:
                comp_i = sc[1]
                comps = _stroke_components(sel_stroke)
                ranges = _component_ranges(sel_stroke)
                hidden = set(sel_stroke.get("hidden_segs", set()) or set()) if isinstance(sel_stroke, dict) else set()
                if 0 <= comp_i < len(ranges):
                    s0, s1 = ranges[comp_i]
                    comp_hidden = all(i in hidden for i in range(s0, s1)) if s1 > s0 else False
                else:
                    comp_hidden = False
                label_what = "stroke" if len(comps) > 1 else "curve"
                screen.blit(font_small.render(f"Selected {label_what}: {comp_i + 1}/{max(1,len(comps))}", True, MUTED_COLOR), (x, y)); y += 22
                if 0 <= comp_i < len(comps):
                    ci = comps[comp_i]
                    info = f"Settings: {ci.get('algorithm','fit')}, pts {ci.get('draw_max_points',4)}"
                    screen.blit(font_small.render(info, True, MUTED_COLOR), (x, y)); y += 18
                hide_rect = pygame.Rect(x, y, (PANEL_W - 48) // 2, 30)
                redraw_rect = pygame.Rect(hide_rect.right + 8, y, (PANEL_W - 48) - hide_rect.w, 30)
                state["curve_hide_rect"] = hide_rect
                state["curve_redraw_rect"] = redraw_rect
                for r, label in ((hide_rect, "Show" if comp_hidden else "Hide"), (redraw_rect, "Redraw")):
                    bg = BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG
                    pygame.draw.rect(screen, bg, r, border_radius=6)
                    pygame.draw.rect(screen, BUTTON_BORDER, r, 1, border_radius=6)
                    t = font_small.render(label, True, TEXT_COLOR)
                    screen.blit(t, t.get_rect(center=r.center))
                y += 38
            else:
                screen.blit(font_small.render("Click a stroke to edit", True, MUTED_COLOR), (x, y)); y += 24
                state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
                state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
        else:
            state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
            state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)

        if sel_count == 0:
            info = font_small.render("Select a stroke", True, MUTED_COLOR)
            screen.blit(info, (x, y)); y += 28
        else:
            stroke = sel_stroke if sel_stroke is not None else state.get("selected_obj")
            if sel_count > 1:
                screen.blit(font_small.render(f"Multiple selected ({sel_count})", True, MUTED_COLOR), (x, y)); y += 20
            # Stroke width
            screen.blit(font.render("Stroke width", True, TEXT_COLOR), (x, y)); y += 22
            wv = font_title.render(str(int(round(stroke.get("stroke_width", 3)))), True, ACCENT)
            screen.blit(wv, (x, y - 2)); y += 30
            state["width_slider"].track.topleft = (x, y)
            state["width_slider"].track.width = PANEL_W - 40
            state["width_slider"].draw(screen); y += 20
            algo_label = next((lbl for k, lbl in TRACE_ALGORITHMS if k == stroke.get("algorithm", "fit")), stroke.get("algorithm", "fit"))
            if sel_count == 1:
                screen.blit(font_small.render(f"Tracing: {algo_label}", True, MUTED_COLOR), (x, y)); y += 20
            else:
                y += 4

            # --- Modern color picker ---
            color_target = state.get("color_target", "stroke")
            screen.blit(font.render("Color", True, TEXT_COLOR), (x, y)); y += 22
            # target tabs
            tab_w = (PANEL_W - 40 - 8) // 2
            tab_stroke = pygame.Rect(x, y, tab_w, 26)
            tab_fill = pygame.Rect(x + tab_w + 8, y, tab_w, 26)
            state["tab_stroke_rect"] = tab_stroke
            state["tab_fill_rect"] = tab_fill
            for rect, label, key in ((tab_stroke, "Stroke", "stroke"), (tab_fill, "Fill", "fill")):
                active = (color_target == key)
                bg = TOOL_ACTIVE if active else (BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_BG)
                pygame.draw.rect(screen, bg, rect, border_radius=6)
                pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, rect, 2 if active else 1, border_radius=6)
                t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
                screen.blit(t, t.get_rect(center=rect.center))
            y += 32

            # current color for target
            if color_target == "stroke":
                cur_color = stroke.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
            else:
                cur_color = stroke.get("fill_color", None)
            display_color = cur_color if cur_color is not None else (1.0, 1.0, 1.0)
            h, s, vcol = rgb_to_hsv(*display_color)
            # keep picker state in sync if not dragging
            if not state.get("picker_drag_sv") and not state.get("picker_drag_hue"):
                state["picker_h"] = h
                state["picker_s"] = s
                state["picker_v"] = vcol
            ph = state.get("picker_h", h)
            ps = state.get("picker_s", s)
            pv = state.get("picker_v", vcol)

            # preview + hex + no-fill
            preview = pygame.Rect(x, y, 34, 34)
            pygame.draw.rect(screen, (255, 255, 255), preview, border_radius=6)
            inner = preview.inflate(-6, -6)
            if color_target == "fill" and cur_color is None:
                pygame.draw.rect(screen, (250, 250, 250), inner, border_radius=4)
                pygame.draw.line(screen, (200, 60, 60), inner.topleft, inner.bottomright, 2)
                hex_txt = "None"
            else:
                rgb_show = tuple(int(c * 255) for c in display_color)
                pygame.draw.rect(screen, rgb_show, inner, border_radius=4)
                hex_txt = rgb_to_hex(display_color)
            pygame.draw.rect(screen, BUTTON_BORDER, preview, 1, border_radius=6)
            screen.blit(font_small.render(hex_txt, True, TEXT_COLOR), (x + 42, y + 9))
            # No fill button
            if color_target == "fill":
                nofill = pygame.Rect(x + 150, y + 4, 70, 26)
                state["nofill_rect"] = nofill
                nf_active = (cur_color is None)
                pygame.draw.rect(screen, TOOL_ACTIVE if nf_active else BUTTON_BG, nofill, border_radius=6)
                pygame.draw.rect(screen, ACCENT if nf_active else BUTTON_BORDER, nofill, 1, border_radius=6)
                nt = font_small.render("No fill", True, ACCENT if nf_active else TEXT_COLOR)
                screen.blit(nt, nt.get_rect(center=nofill.center))
            else:
                state["nofill_rect"] = pygame.Rect(0, 0, 0, 0)
            y += 40

            # SV square
            sv_w = PANEL_W - 40
            sv_h = 110
            sv_rect = pygame.Rect(x, y, sv_w, sv_h)
            state["sv_rect"] = sv_rect
            # draw SV gradient for current hue
            sv_surf = pygame.Surface((sv_w, sv_h))
            for ix in range(sv_w):
                s_val = ix / max(1, sv_w - 1)
                for iy in range(sv_h):
                    v_val = 1.0 - iy / max(1, sv_h - 1)
                    col = hsv_to_rgb(ph, s_val, v_val)
                    sv_surf.set_at((ix, iy), tuple(int(c * 255) for c in col))
            screen.blit(sv_surf, sv_rect.topleft)
            pygame.draw.rect(screen, BUTTON_BORDER, sv_rect, 1, border_radius=4)
            # SV cursor
            cxp = sv_rect.x + int(ps * (sv_w - 1))
            cyp = sv_rect.y + int((1.0 - pv) * (sv_h - 1))
            pygame.draw.circle(screen, (255, 255, 255), (cxp, cyp), 6, 2)
            pygame.draw.circle(screen, (0, 0, 0), (cxp, cyp), 6, 1)
            y += sv_h + 8

            # Hue bar
            hue_h = 14
            hue_rect = pygame.Rect(x, y, sv_w, hue_h)
            state["hue_rect"] = hue_rect
            for ix in range(sv_w):
                hh = (ix / max(1, sv_w - 1)) * 360.0
                col = hsv_to_rgb(hh, 1.0, 1.0)
                pygame.draw.line(screen, tuple(int(c * 255) for c in col), (hue_rect.x + ix, hue_rect.y), (hue_rect.x + ix, hue_rect.y + hue_h - 1))
            pygame.draw.rect(screen, BUTTON_BORDER, hue_rect, 1, border_radius=4)
            hx = hue_rect.x + int((ph / 360.0) * (sv_w - 1))
            pygame.draw.rect(screen, (255, 255, 255), (hx - 3, hue_rect.y - 2, 6, hue_h + 4), 2, border_radius=2)
            pygame.draw.rect(screen, (0, 0, 0), (hx - 3, hue_rect.y - 2, 6, hue_h + 4), 1, border_radius=2)
            y += hue_h + 8

            # Alpha / opacity slider (stroke always; fill only when a fill color exists)
            show_alpha = (color_target == "stroke") or (cur_color is not None)
            state["alpha_rect"] = pygame.Rect(0, 0, 0, 0)
            if show_alpha:
                cur_alpha = color_alpha(cur_color, 1.0)
                screen.blit(font_small.render(f"Opacity {int(round(cur_alpha * 100))}%", True, TEXT_COLOR), (x, y))
                y += 16
                alpha_h = 12
                alpha_rect = pygame.Rect(x, y, sv_w, alpha_h)
                state["alpha_rect"] = alpha_rect
                # simple gradient bar from transparent to current rgb
                base_rgb = color_rgb(display_color, (1.0, 1.0, 1.0))
                for ix in range(sv_w):
                    a = ix / max(1, sv_w - 1)
                    # blend over a light checker-like background approximation
                    bgv = 235 if (ix // 6) % 2 == 0 else 210
                    r = int((base_rgb[0] * a + (bgv / 255.0) * (1 - a)) * 255)
                    g = int((base_rgb[1] * a + (bgv / 255.0) * (1 - a)) * 255)
                    b = int((base_rgb[2] * a + (bgv / 255.0) * (1 - a)) * 255)
                    pygame.draw.line(screen, (r, g, b), (alpha_rect.x + ix, alpha_rect.y), (alpha_rect.x + ix, alpha_rect.y + alpha_h - 1))
                pygame.draw.rect(screen, BUTTON_BORDER, alpha_rect, 1, border_radius=4)
                ax = alpha_rect.x + int(clamp(cur_alpha, 0.0, 1.0) * (sv_w - 1))
                pygame.draw.rect(screen, (255, 255, 255), (ax - 3, alpha_rect.y - 2, 6, alpha_h + 4), 2, border_radius=2)
                pygame.draw.rect(screen, (0, 0, 0), (ax - 3, alpha_rect.y - 2, 6, alpha_h + 4), 1, border_radius=2)
                y += alpha_h + 8
            else:
                y += 2

            # Preset swatches
            presets = STROKE_SWATCHES
            sw = 26
            state["stroke_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in presets]
            state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in presets]
            for i, col in enumerate(presets):
                r = pygame.Rect(x + i * (sw + 6), y, sw, sw)
                if color_target == "stroke":
                    state["stroke_swatch_rects"][i] = r
                else:
                    state["fill_swatch_rects"][i] = r
                sel_match = (cur_color == col) if cur_color is not None else False
                draw_swatch(screen, r, col, sel_match, mouse_pos)
            y += sw + 10

        sel_label = "-" if sel_count == 0 else (str(next(iter(sel_strokes)) + 1) if sel_count == 1 else f"{sel_count}")
        stats = font_small.render(f"Strokes: {state['stroke_count']} | Selected: {sel_label}", True, MUTED_COLOR)
        screen.blit(stats, (x, y)); y += 20
        submode = state.get("selection_submode", "transform")
        if state.get("redrawing_curve"):
            help_lines = [
                "Draw to redraw selected stroke.",
                "Start/end stay fixed.",
                "Release mouse to apply.",
            ]
        elif sel_count == 0:
            help_lines = [
                "Click stroke to select.",
                "Shift+click: multi-select.",
                "N: cycle Transform/Nodes/Curve.",
                "Shortcuts: Ctrl+Z, C, Esc",
            ]
        elif sel_count > 1:
            help_lines = [
                f"{sel_count} shapes selected.",
                "Shift+click: toggle selection.",
                "Drag/handles: move or transform.",
                "N: cycle Transform/Nodes/Curve.",
                "Delete: remove selected.",
            ]
        elif submode == "transform":
            help_lines = [
                "Drag inside box to move.",
                "Drag handles to scale/rotate.",
                "N: cycle Transform/Nodes/Curve.",
                "Delete: remove selected.",
            ]
        elif submode == "nodes":
            help_lines = [
                "Drag anchors/handles to edit.",
                "Smooth joins mirror handles.",
                "N: cycle Transform/Nodes/Curve.",
                "Delete: remove selected.",
            ]
        else:
            help_lines = [
                "Click a curve segment to select.",
                "Hide/Show or Redraw selected curve.",
                "Redraw keeps same point count.",
                "N: cycle Transform/Nodes/Curve.",
            ]

    for line in help_lines:
        txt = font_small.render(line, True, MUTED_COLOR)
        screen.blit(txt, (x, y)); y += 18


def to_canvas(pos):
    return (pos[0] - CANVAS_X, pos[1])


def in_canvas(pos):
    return CANVAS_X <= pos[0] < CANVAS_X + CANVAS_W and 0 <= pos[1] < HEIGHT


def clamp_to_canvas(pos):
    """Map any window position to the nearest point inside the canvas."""
    cx = clamp(pos[0] - CANVAS_X, 0, CANVAS_W - 1)
    cy = clamp(pos[1], 0, HEIGHT - 1)
    return (cx, cy)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Cairo Vector Draw - strokes to Bezier curves")
    clock = pygame.time.Clock()

    cairo_surface = make_cairo_surface(CANVAS_W, HEIGHT)
    strokes = []
    current_points = []
    drawing = False
    tool_mode = "draw"
    selected_strokes = set()
    selected_point = None
    selected_curve = None  # (stroke_idx, comp_idx) in curve edit mode
    redrawing_curve = None  # {"stroke_idx", "comp_idx", "points", "started", "fixed_start", "fixed_end"}
    drag_last = None
    selection_submode = "transform"  # "transform", "nodes", or "curve"
    transform_drag = None  # {"handle": name, "start_mouse": (x,y), "start_strokes": {i: copy}, "center": (cx,cy), "start_bbox": bbox}
    marquee_select = None  # {"start": (x,y), "current": (x,y), "add": bool}
    max_points_per_curve = 4
    boost_points = False
    NORMAL_MAX_POINTS = 5
    BOOST_MAX_POINTS = 100
    trace_algorithm = "fit"  # "fit", "catmull-rom", "single" (per new stroke)

    font = pygame.font.SysFont(None, 24)
    font_small = pygame.font.SysFont(None, 20)
    font_title = pygame.font.SysFont(None, 30)
    fonts = (font, font_small, font_title)

    btn_draw = Button((8, 12, 40, 40), "")
    btn_select = Button((8, 60, 40, 40), "")
    btn_boost = Button((0, 0, PANEL_W - 40, 34), "Boost limit")
    btn_undo = Button((0, 0, PANEL_W - 40, 36), "Undo")
    btn_clear = Button((0, 0, PANEL_W - 40, 36), "Clear")
    buttons = {"boost": btn_boost, "actions": [btn_undo, btn_clear]}
    slider = Slider(PANEL_X + 20, 0, PANEL_W - 40, 2, NORMAL_MAX_POINTS, max_points_per_curve)
    width_slider = Slider(PANEL_X + 20, 0, PANEL_W - 40, 1, 20, 3)

    color_target = "stroke"  # "stroke" or "fill"
    picker_h, picker_s, picker_v = 0.0, 0.0, 0.1
    picker_drag_sv = False
    picker_drag_hue = False
    picker_drag_alpha = False
    ref_opacity_drag = False
    picker_rects = {"sv": pygame.Rect(0,0,0,0), "hue": pygame.Rect(0,0,0,0),
                    "tab_stroke": pygame.Rect(0,0,0,0), "tab_fill": pygame.Rect(0,0,0,0),
                    "nofill": pygame.Rect(0,0,0,0), "alpha": pygame.Rect(0,0,0,0)}
    trace_algo_rects_cache = {}
    nodes_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_hide_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_redraw_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_load_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_vis_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_clear_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_opacity_rect_cache = pygame.Rect(0, 0, 0, 0)
    reference_image = None  # {"surface": cairo.ImageSurface, "w","h","x","y","opacity","visible","path"}
    ref_drag = None
    swatch_rects_cache = {
        "stroke": [pygame.Rect(0, 0, 0, 0) for _ in STROKE_SWATCHES],
        "fill": [pygame.Rect(0, 0, 0, 0) for _ in STROKE_SWATCHES],  # presets sized to STROKE_SWATCHES in picker
    }

    SNAP_RADIUS = 22
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        hover_snap = None
        hover_snap_kind = "connect"
        if in_canvas(mouse_pos) and (tool_mode == "draw" or redrawing_curve is not None):
            cpos = to_canvas(mouse_pos)
            if redrawing_curve is not None:
                rpts = redrawing_curve.get("points", [])
                fixed_start = redrawing_curve.get("fixed_start")
                fixed_end = redrawing_curve.get("fixed_end")
                if not redrawing_curve.get("started") and fixed_start is not None:
                    # show fixed start as connect snap
                    hover_snap = tuple(fixed_start)
                    hover_snap_kind = "connect"
                elif redrawing_curve.get("started") and fixed_end is not None:
                    # show fixed end as target snap while drawing
                    hover_snap = tuple(fixed_end)
                    hover_snap_kind = "connect"
                else:
                    extras = [rpts[0]] if rpts else None
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    hover_snap, hover_snap_kind = draw_snap_info(cpos, strokes, SNAP_RADIUS, shift_held, extra_points=extras)
            elif tool_mode == "draw":
                extras = [current_points[0]] if (drawing and current_points) else None
                if drawing:
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    hover_snap, hover_snap_kind = draw_snap_info(cpos, strokes, SNAP_RADIUS, shift_held, extra_points=extras)
                else:
                    hover_snap = nearest_endpoint(cpos, strokes, SNAP_RADIUS, extra_points=extras)
                    hover_snap_kind = "connect" if hover_snap is not None else "connect"

        stroke_swatch_rects = list(swatch_rects_cache["stroke"])
        fill_swatch_rects = list(swatch_rects_cache["fill"])
        # sanitize selection indices
        selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
        sel_list = sorted(selected_strokes)
        primary = sel_list[0] if len(sel_list) == 1 else (sel_list[0] if sel_list else None)
        sel_obj = strokes[primary] if primary is not None else None
        if selected_curve is not None:
            si, comp_i = selected_curve
            comps = _stroke_components(strokes[si]) if 0 <= si < len(strokes) else []
            if si not in selected_strokes or not (0 <= si < len(strokes)) or not (0 <= comp_i < len(comps)):
                selected_curve = None
                redrawing_curve = None
        if redrawing_curve is not None:
            rsi = redrawing_curve.get("stroke_idx")
            rcomp = redrawing_curve.get("comp_idx", redrawing_curve.get("seg_idx"))
            comps = _stroke_components(strokes[rsi]) if 0 <= rsi < len(strokes) else []
            if rsi not in selected_strokes or not (0 <= rsi < len(strokes)) or not (0 <= rcomp < len(comps)):
                redrawing_curve = None
        state_selected_curve = selected_curve
        state_redrawing_curve = redrawing_curve
        state = {
            "tool_mode": tool_mode, "max_points": max_points_per_curve, "boost_points": boost_points,
            "NORMAL_MAX_POINTS": NORMAL_MAX_POINTS, "BOOST_MAX_POINTS": BOOST_MAX_POINTS,
            "slider": slider, "width_slider": width_slider, "buttons": buttons,
            "stroke_count": len(strokes), "selected_strokes": set(selected_strokes), "selected_obj": sel_obj,
            "stroke_swatch_rects": stroke_swatch_rects, "fill_swatch_rects": fill_swatch_rects,
            "color_target": color_target, "picker_h": picker_h, "picker_s": picker_s, "picker_v": picker_v,
            "picker_drag_sv": picker_drag_sv, "picker_drag_hue": picker_drag_hue, "picker_drag_alpha": picker_drag_alpha,
            "sv_rect": picker_rects["sv"], "hue_rect": picker_rects["hue"],
            "tab_stroke_rect": picker_rects["tab_stroke"], "tab_fill_rect": picker_rects["tab_fill"],
            "nofill_rect": picker_rects["nofill"], "alpha_rect": picker_rects["alpha"],
            "selection_submode": selection_submode,
            "nodes_toggle_rect": nodes_toggle_rect_cache,
            "trace_algorithm": trace_algorithm,
            "trace_algo_rects": trace_algo_rects_cache,
            "selected_curve": state_selected_curve,
            "redrawing_curve": state_redrawing_curve,
            "curve_hide_rect": curve_hide_rect_cache,
            "curve_redraw_rect": curve_redraw_rect_cache,
            "reference_image": reference_image,
            "ref_load_rect": ref_load_rect_cache,
            "ref_vis_rect": ref_vis_rect_cache,
            "ref_clear_rect": ref_clear_rect_cache,
            "ref_opacity_rect": ref_opacity_rect_cache,
        }

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            if slider.handle_event(event):
                max_points_per_curve = slider.value
            if tool_mode == "selection" and selected_strokes and width_slider.handle_event(event):
                for si in selected_strokes:
                    if 0 <= si < len(strokes):
                        strokes[si]["stroke_width"] = float(width_slider.value)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if redrawing_curve is not None:
                        redrawing_curve = None
                    else:
                        running = False
                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    if drawing and tool_mode == "draw" and current_points:
                        snap = nearest_snap_point(current_points[0], strokes, SNAP_RADIUS)
                        if snap is not None:
                            current_points[0] = snap
                    elif redrawing_curve is not None and redrawing_curve.get("started") and redrawing_curve.get("points"):
                        # keep start fixed for redraw; shift has no effect on fixed endpoints
                        if redrawing_curve.get("fixed_start") is None:
                            snap = nearest_snap_point(redrawing_curve["points"][0], strokes, SNAP_RADIUS)
                            if snap is not None:
                                redrawing_curve["points"][0] = snap
                elif event.key == pygame.K_c:
                    strokes.clear(); selected_strokes.clear(); selected_point = None; transform_drag = None
                elif event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if strokes:
                        strokes.pop()
                    selected_strokes.clear(); selected_point = None; transform_drag = None
                elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and tool_mode == "selection":
                    if selected_strokes:
                        for i in sorted(selected_strokes, reverse=True):
                            if 0 <= i < len(strokes):
                                strokes.pop(i)
                        selected_strokes.clear(); selected_point = None; transform_drag = None
                elif event.key == pygame.K_n and tool_mode == "selection":
                    modes = ["transform", "nodes", "curve"]
                    selection_submode = modes[(modes.index(selection_submode) + 1) % len(modes)] if selection_submode in modes else "transform"
                    selected_point = None; selected_curve = None; transform_drag = None; drag_last = None; redrawing_curve = None
                elif event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS):
                    max_points_per_curve = max(2, max_points_per_curve - 1); slider.value = max_points_per_curve
                elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    limit = BOOST_MAX_POINTS if boost_points else NORMAL_MAX_POINTS
                    max_points_per_curve = min(limit, max_points_per_curve + 1); slider.value = max_points_per_curve
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    if drawing and tool_mode == "draw" and current_points:
                        snap = nearest_snap_point(current_points[-1], strokes, SNAP_RADIUS)
                        if snap is not None:
                            current_points[-1] = snap
                    elif redrawing_curve is not None and redrawing_curve.get("started") and redrawing_curve.get("points"):
                        # keep end fixed for redraw
                        if redrawing_curve.get("fixed_end") is None:
                            snap = nearest_snap_point(redrawing_curve["points"][-1], strokes, SNAP_RADIUS)
                            if snap is not None:
                                redrawing_curve["points"][-1] = snap

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_draw.hit(event.pos):
                    tool_mode = "draw"; drawing = False; current_points = []; selected_strokes.clear(); selected_point = None; transform_drag = None
                elif btn_select.hit(event.pos):
                    tool_mode = "selection"; drawing = False; current_points = []; selected_point = None; drag_last = None; transform_drag = None; selection_submode = "transform"
                elif event.pos[0] >= PANEL_X:
                    # Right panel interactions
                    if btn_boost.hit(event.pos) and tool_mode == "draw":
                        boost_points = not boost_points
                        slider.max_v = BOOST_MAX_POINTS if boost_points else NORMAL_MAX_POINTS
                        if not boost_points:
                            max_points_per_curve = min(max_points_per_curve, NORMAL_MAX_POINTS)
                        slider.value = max_points_per_curve
                    elif tool_mode == "draw" and btn_undo.hit(event.pos):
                        if strokes: strokes.pop()
                        selected_strokes.clear(); selected_point = None
                    elif tool_mode == "draw" and btn_clear.hit(event.pos):
                        strokes.clear(); selected_strokes.clear(); selected_point = None
                    elif tool_mode == "draw":
                        handled_draw_panel = False
                        if state.get("ref_load_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            path = pick_reference_image_path()
                            if path:
                                ref = load_reference_image(path)
                                if ref is not None:
                                    reference_image = ref
                            handled_draw_panel = True
                        elif state.get("ref_vis_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            if reference_image:
                                reference_image["visible"] = not reference_image.get("visible", True)
                            handled_draw_panel = True
                        elif state.get("ref_clear_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            reference_image = None
                            handled_draw_panel = True
                        elif reference_image and state.get("ref_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            bar = state["ref_opacity_rect"]
                            reference_image["opacity"] = clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
                            ref_opacity_drag = True
                            handled_draw_panel = True
                        if not handled_draw_panel:
                            for key, r in state.get("trace_algo_rects", {}).items():
                                if r.collidepoint(event.pos):
                                    trace_algorithm = key
                                    break
                    elif tool_mode == "selection" and state.get("nodes_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        r = state["nodes_toggle_rect"]
                        rel = (event.pos[0] - r.x) / max(1, r.w)
                        if rel < 1/3:
                            selection_submode = "transform"
                        elif rel < 2/3:
                            selection_submode = "nodes"
                        else:
                            selection_submode = "curve"
                        selected_point = None; selected_curve = None; transform_drag = None; drag_last = None; redrawing_curve = None
                    elif tool_mode == "selection" and selection_submode == "curve" and state.get("curve_hide_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        if selected_curve and selected_curve[0] in selected_strokes:
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes) and isinstance(strokes[si], dict):
                                ranges = _component_ranges(strokes[si])
                                if 0 <= comp_i < len(ranges):
                                    s0, s1 = ranges[comp_i]
                                    hidden = set(strokes[si].get("hidden_segs", set()) or set())
                                    comp_hidden = all(i in hidden for i in range(s0, s1)) if s1 > s0 else False
                                    if comp_hidden:
                                        for i in range(s0, s1): hidden.discard(i)
                                    else:
                                        for i in range(s0, s1): hidden.add(i)
                                    strokes[si]["hidden_segs"] = hidden
                    elif tool_mode == "selection" and selection_submode == "curve" and state.get("curve_redraw_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        if selected_curve and selected_curve[0] in selected_strokes:
                            si, comp_i = selected_curve
                            fixed_start = fixed_end = None
                            if 0 <= si < len(strokes):
                                segs = segs_of(strokes[si])
                                ranges = _component_ranges(strokes[si])
                                if 0 <= comp_i < len(ranges):
                                    s0, s1 = ranges[comp_i]
                                    if s1 > s0 and s1 <= len(segs):
                                        fixed_start = tuple(segs[s0][0])
                                        fixed_end = tuple(segs[s1 - 1][3])
                            redrawing_curve = {
                                "stroke_idx": si, "comp_idx": comp_i, "points": [],
                                "started": False, "fixed_start": fixed_start, "fixed_end": fixed_end,
                            }
                            selected_point = None; transform_drag = None; drag_last = None
                    elif tool_mode == "selection" and selected_strokes:
                        # Modern color picker interactions (apply to all selected strokes)
                        sel_list = sorted(selected_strokes)
                        primary_i = sel_list[0]
                        primary_obj = strokes[primary_i] if 0 <= primary_i < len(strokes) else None
                        if primary_obj is None:
                            pass
                        elif state["tab_stroke_rect"].collidepoint(event.pos):
                            color_target = "stroke"
                            sc = primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
                            picker_h, picker_s, picker_v = rgb_to_hsv(*sc)
                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                        elif state["tab_fill_rect"].collidepoint(event.pos):
                            color_target = "fill"
                            fc = primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
                            picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                        elif state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and color_target == "fill":
                            for si in sel_list:
                                if 0 <= si < len(strokes):
                                    strokes[si]["fill_color"] = None
                        elif state["sv_rect"].collidepoint(event.pos):
                            picker_drag_sv = True
                            sv = state["sv_rect"]
                            picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                            picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                            col = hsv_to_rgb(picker_h, picker_s, picker_v)
                            for si in sel_list:
                                if 0 <= si < len(strokes):
                                    if color_target == "stroke":
                                        alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                        strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                    else:
                                        alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                        strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                            state["picker_drag_sv"] = True
                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                        elif state["hue_rect"].collidepoint(event.pos):
                            picker_drag_hue = True
                            hr = state["hue_rect"]
                            picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                            col = hsv_to_rgb(picker_h, picker_s, picker_v)
                            for si in sel_list:
                                if 0 <= si < len(strokes):
                                    if color_target == "stroke":
                                        alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                        strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                    else:
                                        alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                        strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                            state["picker_drag_hue"] = True
                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                        elif state.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            ar = state["alpha_rect"]
                            new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                            for si in sel_list:
                                if 0 <= si < len(strokes):
                                    if color_target == "stroke":
                                        strokes[si]["stroke_color"] = set_color_alpha(strokes[si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                                    elif strokes[si].get("fill_color") is not None:
                                        strokes[si]["fill_color"] = set_color_alpha(strokes[si].get("fill_color"), new_alpha)
                            picker_drag_alpha = True
                            state["picker_drag_alpha"] = True
                        else:
                            # preset swatches (draw_panel populates rects matching active target)
                            rects = state["stroke_swatch_rects"] if color_target == "stroke" else state["fill_swatch_rects"]
                            for i, r in enumerate(rects):
                                if r.w > 0 and r.collidepoint(event.pos) and i < len(STROKE_SWATCHES):
                                    col = STROKE_SWATCHES[i]
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            if color_target == "stroke":
                                                alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                                strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                            else:
                                                alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                    picker_h, picker_s, picker_v = rgb_to_hsv(*col)
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                    break
                elif in_canvas(event.pos):
                    cpos = to_canvas(event.pos)
                    if tool_mode == "draw":
                        mods = pygame.key.get_mods()
                        if (mods & pygame.KMOD_ALT) and reference_image and reference_image.get("visible", True):
                            ref_drag = {"offset": (cpos[0] - reference_image.get("x", 0), cpos[1] - reference_image.get("y", 0))}
                            drawing = False
                        else:
                            drawing = True
                            shift_held = bool(mods & pygame.KMOD_SHIFT)
                            start_pos = draw_snap_point(cpos, strokes, SNAP_RADIUS, shift_held) or cpos
                            current_points = [start_pos]
                    elif redrawing_curve is not None:
                        # Redraw selected stroke/component: focused draw with snap features
                        fixed_start = redrawing_curve.get("fixed_start")
                        if fixed_start is not None:
                            start_pos = tuple(fixed_start)
                        else:
                            shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                            start_pos = draw_snap_point(cpos, strokes, SNAP_RADIUS, shift_held) or cpos
                        redrawing_curve["points"] = [start_pos]
                        redrawing_curve["started"] = True
                    else:
                        # Selection mode
                        selected_point = None
                        transform_drag = None
                        mods = pygame.key.get_mods()
                        shift = bool(mods & pygame.KMOD_SHIFT)
                        if selection_submode == "curve":
                            if len(selected_strokes) == 1:
                                si = next(iter(selected_strokes))
                                if 0 <= si < len(strokes):
                                    comp_i = hit_test_component(strokes[si], cpos)
                                    if comp_i is not None:
                                        selected_curve = (si, comp_i)
                            # allow selecting a different stroke
                            hit = hit_test_stroke(cpos, strokes)
                            if hit is not None and (len(selected_strokes) != 1 or hit != next(iter(selected_strokes))):
                                selected_strokes = {hit}
                                comp_i = hit_test_component(strokes[hit], cpos) if 0 <= hit < len(strokes) else None
                                selected_curve = (hit, comp_i) if comp_i is not None else None
                            elif hit is None and not shift:
                                selected_strokes.clear(); selected_curve = None
                            if len(selected_strokes) != 1 or (selected_curve and selected_curve[0] not in selected_strokes):
                                selected_curve = None
                        elif selection_submode == "transform":
                            handled = False
                            if selected_strokes:
                                bb = combined_bbox(strokes, selected_strokes)
                                h = hit_test_bbox_handle(bb, cpos)
                                if h is not None:
                                    cx, cy = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
                                    import copy as _copy
                                    start_strokes = {i: _copy.deepcopy(strokes[i]) for i in sorted(selected_strokes) if 0 <= i < len(strokes)}
                                    transform_drag = {
                                        "handle": h,
                                        "start_mouse": cpos,
                                        "start_strokes": start_strokes,
                                        "center": (cx, cy),
                                        "start_bbox": bb,
                                    }
                                    handled = True
                                elif bb and point_in_bbox(bb, cpos):
                                    # move all selected (keep multi-selection)
                                    drag_last = cpos
                                    handled = True
                                elif hit_test_stroke(cpos, strokes) in selected_strokes:
                                    drag_last = cpos
                                    handled = True
                            if not handled:
                                hit = hit_test_stroke(cpos, strokes)
                                if hit is not None:
                                    if shift:
                                        if hit in selected_strokes:
                                            selected_strokes.discard(hit)
                                        else:
                                            selected_strokes.add(hit)
                                    else:
                                        selected_strokes = {hit}
                                    if selected_strokes:
                                        primary_i = sorted(selected_strokes)[0]
                                        if 0 <= primary_i < len(strokes):
                                            width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))
                                        drag_last = cpos
                                    else:
                                        drag_last = None
                                else:
                                    # start marquee selection on empty area
                                    marquee_select = {"start": cpos, "current": cpos, "add": shift}
                                    drag_last = None
                        else:
                            # Nodes mode: point editing only for single selection
                            if len(selected_strokes) == 1:
                                only = next(iter(selected_strokes))
                                if 0 <= only < len(strokes):
                                    pt_hit = hit_test_point(strokes[only], cpos)
                                    if pt_hit is not None:
                                        selected_point = pt_hit; drag_last = cpos
                                    else:
                                        hit = hit_test_stroke(cpos, strokes)
                                        if hit == only:
                                            drag_last = cpos
                                        elif hit is not None:
                                            if shift:
                                                if hit in selected_strokes:
                                                    selected_strokes.discard(hit)
                                                else:
                                                    selected_strokes.add(hit)
                                            else:
                                                selected_strokes = {hit}
                                            if selected_strokes:
                                                primary_i = sorted(selected_strokes)[0]
                                                if 0 <= primary_i < len(strokes):
                                                    width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))
                                            drag_last = cpos if hit is not None else None
                                        else:
                                            if not shift:
                                                selected_strokes.clear()
                                            drag_last = None
                                else:
                                    selected_strokes.clear(); drag_last = None
                            else:
                                # multi or none: selection changes only
                                hit = hit_test_stroke(cpos, strokes)
                                if hit is not None:
                                    if shift:
                                        if hit in selected_strokes:
                                            selected_strokes.discard(hit)
                                        else:
                                            selected_strokes.add(hit)
                                    else:
                                        selected_strokes = {hit}
                                    if selected_strokes:
                                        primary_i = sorted(selected_strokes)[0]
                                        if 0 <= primary_i < len(strokes):
                                            width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))
                                    drag_last = cpos
                                else:
                                    if not shift:
                                        selected_strokes.clear()
                                    drag_last = None
                else:
                    # left bar area (not buttons) - ignore
                    pass

            elif event.type == pygame.MOUSEMOTION:
                if ref_opacity_drag and reference_image is not None:
                    bar = state.get("ref_opacity_rect", pygame.Rect(0,0,0,0))
                    if bar.w > 0:
                        reference_image["opacity"] = clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
                elif ref_drag is not None and reference_image is not None and (pygame.mouse.get_pressed()[0]):
                    cpos = clamp_to_canvas(event.pos)
                    off = ref_drag.get("offset", (0, 0))
                    reference_image["x"] = cpos[0] - off[0]
                    reference_image["y"] = cpos[1] - off[1]
                elif (picker_drag_sv or picker_drag_hue or picker_drag_alpha) and selected_strokes:
                    sel_list = sorted(selected_strokes)
                    if picker_drag_sv:
                        sv = state["sv_rect"]
                        picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                        picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                        col = hsv_to_rgb(picker_h, picker_s, picker_v)
                        for si in sel_list:
                            if 0 <= si < len(strokes):
                                if color_target == "stroke":
                                    alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                    strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                else:
                                    alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                    strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                    elif picker_drag_hue:
                        hr = state["hue_rect"]
                        picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                        col = hsv_to_rgb(picker_h, picker_s, picker_v)
                        for si in sel_list:
                            if 0 <= si < len(strokes):
                                if color_target == "stroke":
                                    alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                    strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                else:
                                    alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                    strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                    elif picker_drag_alpha:
                        ar = state.get("alpha_rect", pygame.Rect(0,0,0,0))
                        new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                        for si in sel_list:
                            if 0 <= si < len(strokes):
                                if color_target == "stroke":
                                    strokes[si]["stroke_color"] = set_color_alpha(strokes[si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                                elif strokes[si].get("fill_color") is not None:
                                    strokes[si]["fill_color"] = set_color_alpha(strokes[si].get("fill_color"), new_alpha)
                elif redrawing_curve is not None and redrawing_curve.get("started") and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    pts = redrawing_curve.get("points", [])
                    fixed_start = redrawing_curve.get("fixed_start")
                    fixed_end = redrawing_curve.get("fixed_end")
                    if fixed_start is not None and pts:
                        pts[0] = tuple(fixed_start)
                    keys = pygame.key.get_pressed()
                    straight_line = bool(keys[pygame.K_v]) if keys else False
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    pts = advance_drawing_points(pts, cpos, strokes, SNAP_RADIUS, shift_held, straight_line, fixed_end=fixed_end)
                    redrawing_curve["points"] = pts
                elif marquee_select is not None and tool_mode == "selection" and pygame.mouse.get_pressed()[0]:
                    marquee_select["current"] = clamp_to_canvas(event.pos)
                elif drawing and tool_mode == "draw":
                    cpos = clamp_to_canvas(event.pos)
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    keys = pygame.key.get_pressed()
                    straight_line = bool(keys[pygame.K_v]) if keys else False
                    current_points = advance_drawing_points(current_points, cpos, strokes, SNAP_RADIUS, shift_held, straight_line)
                elif tool_mode == "selection" and transform_drag is not None and selected_strokes and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    td = transform_drag
                    cx, cy = td["center"]
                    sx0, sy0 = td["start_mouse"]
                    h = td["handle"]
                    start_strokes = td.get("start_strokes", {})
                    if h == "rot":
                        a0 = math.atan2(sy0 - cy, sx0 - cx)
                        a1 = math.atan2(cpos[1] - cy, cpos[0] - cx)
                        for i, st0 in start_strokes.items():
                            if 0 <= i < len(strokes):
                                strokes[i] = transform_stroke(st0, cx, cy, a1 - a0, 1.0)
                    else:
                        def _safe_ratio(cur_d, start_d):
                            if abs(start_d) < 1e-6:
                                return 1.0
                            return cur_d / start_d
                        sx = sy = 1.0
                        if h in ("e", "w"):
                            sx = _safe_ratio(cpos[0] - cx, sx0 - cx)
                        elif h in ("n", "s"):
                            sy = _safe_ratio(cpos[1] - cy, sy0 - cy)
                        else:
                            d0 = math.hypot(sx0 - cx, sy0 - cy)
                            d1 = math.hypot(cpos[0] - cx, cpos[1] - cy)
                            s = _safe_ratio(d1, d0)
                            sx = sy = s
                        sx = clamp(sx, 0.05, 20.0)
                        sy = clamp(sy, 0.05, 20.0)
                        for i, st0 in start_strokes.items():
                            if 0 <= i < len(strokes):
                                strokes[i] = transform_stroke(st0, cx, cy, 0.0, sx, sy)
                elif tool_mode == "selection" and drag_last is not None and selected_strokes and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    if selected_point is not None and len(selected_strokes) == 1:
                        only = next(iter(selected_strokes))
                        seg_i, pname = selected_point
                        if 0 <= only < len(strokes):
                            strokes[only] = set_stroke_point(strokes[only], seg_i, pname, cpos)
                        drag_last = cpos
                    else:
                        dx = cpos[0] - drag_last[0]; dy = cpos[1] - drag_last[1]
                        if dx != 0 or dy != 0:
                            for si in list(selected_strokes):
                                if 0 <= si < len(strokes):
                                    strokes[si] = translate_stroke(strokes[si], dx, dy)
                            drag_last = cpos
                # (translation handled above when drag_last is set)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if marquee_select is not None and tool_mode == "selection":
                    r = normalize_rect(marquee_select["start"], marquee_select.get("current", marquee_select["start"]))
                    if abs(r[2]-r[0]) >= 3 or abs(r[3]-r[1]) >= 3:
                        picked = {i for i, st in enumerate(strokes) if rects_intersect(r, stroke_bbox(st))}
                        if marquee_select.get("add"):
                            selected_strokes |= picked
                        else:
                            selected_strokes = picked
                    elif not marquee_select.get("add"):
                        selected_strokes.clear()
                    marquee_select = None
                elif redrawing_curve is not None:
                    if redrawing_curve.get("started"):
                        si = redrawing_curve.get("stroke_idx")
                        comp_i = redrawing_curve.get("comp_idx", redrawing_curve.get("seg_idx"))
                        pts = list(redrawing_curve.get("points", []))
                        fixed_start = redrawing_curve.get("fixed_start")
                        fixed_end = redrawing_curve.get("fixed_end")
                        if fixed_start is not None and pts:
                            pts[0] = tuple(fixed_start)
                        cpos = clamp_to_canvas(event.pos)
                        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                        keys = pygame.key.get_pressed()
                        straight_line = bool(keys[pygame.K_v]) if keys else False
                        pts = finalize_drawing_points(pts, cpos, strokes, SNAP_RADIUS, shift_held, straight_line, fixed_end=fixed_end)
                        if fixed_start is not None:
                            if pts:
                                pts[0] = tuple(fixed_start)
                            else:
                                pts = [tuple(fixed_start)]
                        if fixed_end is not None:
                            if len(pts) == 1:
                                pts.append(tuple(fixed_end))
                            elif pts:
                                pts[-1] = tuple(fixed_end)
                        if si is not None and comp_i is not None and 0 <= si < len(strokes) and len(pts) >= 2:
                            strokes[si] = redraw_stroke_component(strokes[si], comp_i, pts)
                        redrawing_curve = None
                    else:
                        # Redraw mode armed but drawing not started yet (e.g. released on button); wait for canvas drag
                        pass
                elif drawing and tool_mode == "draw":
                    drawing = False
                    cpos = clamp_to_canvas(event.pos)
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    keys = pygame.key.get_pressed()
                    straight_line = bool(keys[pygame.K_v]) if keys else False
                    current_points = finalize_drawing_points(current_points, cpos, strokes, SNAP_RADIUS, shift_held, straight_line)
                    if len(current_points) >= 2:
                        raw = list(current_points)
                        if straight_line:
                            p0 = tuple(current_points[0])
                            p3 = tuple(current_points[-1])
                            c1 = (p0[0] + (p3[0] - p0[0]) / 3.0, p0[1] + (p3[1] - p0[1]) / 3.0)
                            c2 = (p0[0] + 2.0 * (p3[0] - p0[0]) / 3.0, p0[1] + 2.0 * (p3[1] - p0[1]) / 3.0)
                            beziers = [(p0, c1, c2, p3)]
                            raw = [p0, p3]
                        else:
                            beziers = stroke_to_beziers(
                                current_points, simplify_epsilon=2.5, tension=0.0,
                                max_points=max_points_per_curve, algorithm=trace_algorithm,
                            )
                        if beziers:
                            st = new_stroke(beziers, algorithm=trace_algorithm)
                            comp = {
                                "raw_points": [tuple(p) for p in raw],
                                "draw_max_points": int(max_points_per_curve),
                                "algorithm": trace_algorithm,
                                "segs": list(beziers),
                            }
                            st["components"] = [comp]
                            st = _close_path_if_needed(st)
                            strokes.append(st)
                            strokes = merge_connected_strokes(strokes)
                            selected_strokes.clear(); selected_point = None; selected_curve = None; redrawing_curve = None
                    current_points = []
                drag_last = None; selected_point = None; transform_drag = None
                picker_drag_sv = False; picker_drag_hue = False; picker_drag_alpha = False; ref_opacity_drag = False
                state["picker_drag_sv"] = False; state["picker_drag_hue"] = False; state["picker_drag_alpha"] = False
                ref_drag = None
                max_points_per_curve = slider.value

        # Draw scene (Cairo) and blit at canvas offset
        active = current_points if (drawing and tool_mode == "draw") else (redrawing_curve.get("points") if redrawing_curve else None)
        draw_scene(
            cairo_surface, strokes, active, snap_point=hover_snap,
            selected_indices=selected_strokes, edit_mode=(tool_mode == "selection"),
            selection_submode=selection_submode, selected_curve=selected_curve,
            snap_kind=hover_snap_kind, redrawing_curve=redrawing_curve,
            ref_img=reference_image,
        )
        frame = surface_to_pygame(cairo_surface)
        screen.fill((230, 233, 238))
        screen.blit(frame, (CANVAS_X, 0))

        # marquee selection overlay
        if marquee_select is not None and tool_mode == "selection":
            r = normalize_rect(marquee_select["start"], marquee_select.get("current", marquee_select["start"]))
            rx1, ry1, rx2, ry2 = r
            rect = pygame.Rect(int(rx1 + CANVAS_X), int(ry1), int(rx2 - rx1), int(ry2 - ry1))
            if rect.w > 0 or rect.h > 0:
                surf = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
                surf.fill((60, 120, 220, 40))
                screen.blit(surf, rect.topleft)
                pygame.draw.rect(screen, (60, 120, 220), rect, 1)

        # Need swatch rects for this frame's layout - draw panel and capture by recomputing? we passed refs in state but draw_panel fills them during draw
        draw_left_toolbar(screen, mouse_pos, tool_mode, btn_draw, btn_select)
        draw_panel(screen, fonts, mouse_pos, state)

        # sync picker state/rects from panel for next frame's event handling
        picker_h = state.get("picker_h", picker_h)
        picker_s = state.get("picker_s", picker_s)
        picker_v = state.get("picker_v", picker_v)
        picker_rects["sv"] = state.get("sv_rect", picker_rects["sv"])
        picker_rects["hue"] = state.get("hue_rect", picker_rects["hue"])
        picker_rects["tab_stroke"] = state.get("tab_stroke_rect", picker_rects["tab_stroke"])
        picker_rects["tab_fill"] = state.get("tab_fill_rect", picker_rects["tab_fill"])
        picker_rects["nofill"] = state.get("nofill_rect", picker_rects["nofill"])
        picker_rects["alpha"] = state.get("alpha_rect", picker_rects["alpha"])
        trace_algo_rects_cache = state.get("trace_algo_rects", trace_algo_rects_cache)
        nodes_toggle_rect_cache = state.get("nodes_toggle_rect", nodes_toggle_rect_cache)
        curve_hide_rect_cache = state.get("curve_hide_rect", curve_hide_rect_cache)
        curve_redraw_rect_cache = state.get("curve_redraw_rect", curve_redraw_rect_cache)
        ref_load_rect_cache = state.get("ref_load_rect", ref_load_rect_cache)
        ref_vis_rect_cache = state.get("ref_vis_rect", ref_vis_rect_cache)
        ref_clear_rect_cache = state.get("ref_clear_rect", ref_clear_rect_cache)
        ref_opacity_rect_cache = state.get("ref_opacity_rect", ref_opacity_rect_cache)
        swatch_rects_cache["stroke"] = list(state.get("stroke_swatch_rects", swatch_rects_cache["stroke"]))
        swatch_rects_cache["fill"] = list(state.get("fill_swatch_rects", swatch_rects_cache["fill"]))

        # sync width slider to selected on selection changes shown next frame (simple keep)
        if tool_mode == "selection" and selected_strokes and not width_slider.dragging:
            primary_i = sorted(selected_strokes)[0]
            if 0 <= primary_i < len(strokes):
                width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))

        pygame.display.flip()
        clock.tick(120)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
