"""Model: pure geometry, curve construction and color math."""

import math

from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative


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

def points_bbox(points):
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))

def _line_bezier(p0, p3):
    c1 = (p0[0] + (p3[0] - p0[0]) / 3.0, p0[1] + (p3[1] - p0[1]) / 3.0)
    c2 = (p0[0] + 2.0 * (p3[0] - p0[0]) / 3.0, p0[1] + 2.0 * (p3[1] - p0[1]) / 3.0)
    return (tuple(p0), c1, c2, tuple(p3))

def _rect_beziers(x1, y1, x2, y2):
    p1, p2, p3, p4 = (x1, y1), (x2, y1), (x2, y2), (x1, y2)
    return [_line_bezier(p1, p2), _line_bezier(p2, p3), _line_bezier(p3, p4), _line_bezier(p4, p1)]

def _ellipse_beziers(cx, cy, rx, ry):
    if rx < 1e-3: rx = 1e-3
    if ry < 1e-3: ry = 1e-3
    k = 0.5522847498307936
    ox, oy = rx * k, ry * k
    # start at rightmost point, clockwise
    p0 = (cx + rx, cy)
    p1 = (cx, cy + ry)
    p2 = (cx - rx, cy)
    p3 = (cx, cy - ry)
    return [
        (p0, (cx + rx, cy + oy), (cx + ox, cy + ry), p1),
        (p1, (cx - ox, cy + ry), (cx - rx, cy + oy), p2),
        (p2, (cx - rx, cy - oy), (cx - ox, cy - ry), p3),
        (p3, (cx + ox, cy - ry), (cx + rx, cy - oy), p0),
    ]

def _triangle_beziers(x1, y1, x2, y2):
    # upward-pointing triangle inscribed in bbox
    top = ((x1 + x2) / 2.0, y1)
    br = (x2, y2)
    bl = (x1, y2)
    return [_line_bezier(top, br), _line_bezier(br, bl), _line_bezier(bl, top)]

def shape_from_doodle(points, shape_kind):
    """Generate standard shape as a list of bezier segments from doodled points.
    Returns (segments, canonical_points). Each segment is intended as a separate stroke when possible."""
    if not points or len(points) < 2:
        return None, None
    bb = points_bbox(points)
    if bb is None:
        return None, None
    x1, y1, x2, y2 = bb
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    if shape_kind == "line":
        p0 = tuple(points[0])
        p3 = tuple(points[-1])
        # if doodle ended very close to start, use bbox diagonal-ish fallback
        if math.hypot(p3[0] - p0[0], p3[1] - p0[1]) < 2.0:
            p0, p3 = (x1, y1), (x2, y2)
        return [_line_bezier(p0, p3)], [p0, p3]
    if shape_kind == "rect":
        segs = _rect_beziers(x1, y1, x2, y2)
        return segs, [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    if shape_kind == "square":
        s = min(w, h)
        sx1, sy1 = cx - s / 2.0, cy - s / 2.0
        sx2, sy2 = cx + s / 2.0, cy + s / 2.0
        segs = _rect_beziers(sx1, sy1, sx2, sy2)
        return segs, [(sx1, sy1), (sx2, sy1), (sx2, sy2), (sx1, sy2), (sx1, sy1)]
    if shape_kind == "ellipse":
        return _ellipse_beziers(cx, cy, w / 2.0, h / 2.0), None
    if shape_kind == "circle":
        r = min(w, h) / 2.0
        return _ellipse_beziers(cx, cy, r, r), None
    if shape_kind == "triangle":
        return _triangle_beziers(x1, y1, x2, y2), None
    return None, None

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

def _sample_cubic(p0, c1, c2, p3, n=24):
    return [_cubic_point(p0, c1, c2, p3, i / n) for i in range(n + 1)]

def _stroke_outline_points(stroke, samples_per_seg=24):
    """Points on the visible curve/lines (anchors + sampled curve). Excludes control handles."""
    segs = segs_of(stroke)
    pts = []
    for i, (p0, c1, c2, p3) in enumerate(segs):
        samp = _sample_cubic(p0, c1, c2, p3, samples_per_seg)
        if i > 0 and samp:
            samp = samp[1:]
        pts.extend(samp)
    for p0, c1, c2, p3 in segs:
        pts.append(p0); pts.append(p3)
    return pts

def _mirror_handle(anchor, handle):
    return (2 * anchor[0] - handle[0], 2 * anchor[1] - handle[1])

def apply_affine(pt, cx, cy, ca, sa, sx, sy):
    """Apply scale (sx,sy) then rotate (ca,sa) around (cx,cy)."""
    x, y = (pt[0] - cx) * sx, (pt[1] - cy) * sy
    return (cx + x * ca - y * sa, cy + x * sa + y * ca)

# ---- Bounding boxes ----

def _aabb_of_points(pts):
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))

def stroke_bbox(stroke):
    """Axis-aligned bbox of the visible curve/lines (excludes Bezier control handles)."""
    return _aabb_of_points(_stroke_outline_points(stroke))

def _convex_hull(points):
    pts = sorted(set((float(x), float(y)) for x, y in points))
    if len(pts) <= 1:
        return pts
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]

def _min_area_obb(points):
    """Minimum-area oriented bounding box of points.
    Returns dict {cx,cy,hw,hh,angle,corners} or None."""
    if not points:
        return None
    if len(points) == 1:
        x, y = float(points[0][0]), float(points[0][1])
        c = [(x,y),(x,y),(x,y),(x,y)]
        return {"cx": x, "cy": y, "hw": 0.0, "hh": 0.0, "angle": 0.0, "corners": c}
    hull = _convex_hull(points)
    if len(hull) < 2:
        x, y = float(points[0][0]), float(points[0][1])
        c = [(x,y),(x,y),(x,y),(x,y)]
        return {"cx": x, "cy": y, "hw": 0.0, "hh": 0.0, "angle": 0.0, "corners": c}
    best = None
    for i in range(len(hull)):
        x0, y0 = hull[i]
        x1, y1 = hull[(i + 1) % len(hull)]
        ex, ey = x1 - x0, y1 - y0
        el = math.hypot(ex, ey)
        if el < 1e-9:
            continue
        ux, uy = ex / el, ey / el
        vx, vy = -uy, ux
        min_u = min_v = 1e18
        max_u = max_v = -1e18
        for px, py in hull:
            pu = px * ux + py * uy
            pv = px * vx + py * vy
            if pu < min_u: min_u = pu
            if pu > max_u: max_u = pu
            if pv < min_v: min_v = pv
            if pv > max_v: max_v = pv
        wu, wv = max_u - min_u, max_v - min_v
        area = wu * wv
        if best is None or area < best[0]:
            cu = (min_u + max_u) / 2.0
            cv = (min_v + max_v) / 2.0
            cx = cu * ux + cv * vx
            cy = cu * uy + cv * vy
            angle = math.atan2(uy, ux)
            best = (area, cx, cy, wu / 2.0, wv / 2.0, angle, ux, uy, vx, vy)
    if best is None:
        bb = _aabb_of_points(points)
        if not bb:
            return None
        x1,y1,x2,y2 = bb
        cx,cy = (x1+x2)/2,(y1+y2)/2
        hw,hh = (x2-x1)/2,(y2-y1)/2
        c = [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
        return {"cx":cx,"cy":cy,"hw":hw,"hh":hh,"angle":0.0,"corners":c}
    _, cx, cy, hw, hh, angle, ux, uy, vx, vy = best
    corners = []
    for su, sv in [(-hw,-hh),(hw,-hh),(hw,hh),(-hw,hh)]:
        corners.append((cx + su*ux + sv*vx, cy + su*uy + sv*vy))
    return {"cx": cx, "cy": cy, "hw": hw, "hh": hh, "angle": angle, "corners": corners}

def _obb_to_aabb(obb):
    if obb is None:
        return None
    if isinstance(obb, (tuple, list)):
        return tuple(obb)
    corners = obb.get("corners") or []
    if not corners:
        cx,cy,hw,hh,ang = obb["cx"],obb["cy"],obb["hw"],obb["hh"],obb.get("angle",0.0)
        ca,sa = math.cos(ang), math.sin(ang)
        corners = [(cx + dx*ca - dy*sa, cy + dx*sa + dy*ca)
                   for dx,dy in [(-hw,-hh),(hw,-hh),(hw,hh),(-hw,hh)]]
    xs = [p[0] for p in corners]; ys = [p[1] for p in corners]
    return (min(xs), min(ys), max(xs), max(ys))

def stroke_obb(stroke):
    """Oriented bounding box of visible curve/lines (excludes control handles)."""
    return _min_area_obb(_stroke_outline_points(stroke))

def _obb_axes(obb):
    ang = obb.get("angle", 0.0)
    ca, sa = math.cos(ang), math.sin(ang)
    return (ca, sa), (-sa, ca)

def bbox_handles(bbox, rot_offset=22):
    """Handle positions for AABB tuple or OBB dict. OBB rotates with the shape."""
    if bbox is None:
        return {}
    if isinstance(bbox, dict) and "angle" in bbox:
        cx, cy = bbox["cx"], bbox["cy"]
        hw, hh = bbox["hw"], bbox["hh"]
        ang = bbox.get("angle", 0.0)
        ca, sa = math.cos(ang), math.sin(ang)
        def P(lx, ly):
            return (cx + lx*ca - ly*sa, cy + lx*sa + ly*ca)
        return {
            "nw": P(-hw, -hh), "n": P(0, -hh), "ne": P(hw, -hh),
            "e": P(hw, 0), "se": P(hw, hh), "s": P(0, hh),
            "sw": P(-hw, hh), "w": P(-hw, 0),
            "rot": P(0, -hh - rot_offset),
        }
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
    handles = bbox_handles(bbox)
    for name in ["rot", "nw", "ne", "se", "sw", "n", "e", "s", "w"]:
        pt = handles.get(name)
        if pt and math.hypot(pos[0] - pt[0], pos[1] - pt[1]) <= radius:
            return name
    return None

def point_in_bbox(bbox, pos):
    if bbox is None:
        return False
    if isinstance(bbox, dict) and "angle" in bbox:
        cx, cy = bbox["cx"], bbox["cy"]
        hw, hh = bbox["hw"], bbox["hh"]
        ang = bbox.get("angle", 0.0)
        dx, dy = pos[0] - cx, pos[1] - cy
        ca, sa = math.cos(ang), math.sin(ang)
        lx = dx*ca + dy*sa
        ly = -dx*sa + dy*ca
        return -hw <= lx <= hw and -hh <= ly <= hh
    x1, y1, x2, y2 = bbox
    return x1 <= pos[0] <= x2 and y1 <= pos[1] <= y2

def rects_intersect(a, b):
    """AABB intersection (tuples). OBB dicts are converted to their AABB."""
    if a is None or b is None:
        return False
    if isinstance(a, dict): a = _obb_to_aabb(a)
    if isinstance(b, dict): b = _obb_to_aabb(b)
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)

def normalize_rect(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
