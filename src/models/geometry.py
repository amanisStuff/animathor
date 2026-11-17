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

def _rect_beziers(x1, y1, x2, y2, radius=0.0):
    w = max(1e-6, x2 - x1)
    h = max(1e-6, y2 - y1)
    r = max(0.0, min(float(radius or 0.0), min(w, h) / 2.0))
    if r <= 1e-6:
        p1, p2, p3, p4 = (x1, y1), (x2, y1), (x2, y2), (x1, y2)
        return [_line_bezier(p1, p2), _line_bezier(p2, p3), _line_bezier(p3, p4), _line_bezier(p4, p1)]
    k = 0.5522847498307936
    kr = r * k
    segs = [
        _line_bezier((x1 + r, y1), (x2 - r, y1)),
        ((x2 - r, y1), (x2 - r + kr, y1), (x2, y1 + r - kr), (x2, y1 + r)),
        _line_bezier((x2, y1 + r), (x2, y2 - r)),
        ((x2, y2 - r), (x2, y2 - r + kr), (x2 - r + kr, y2), (x2 - r, y2)),
        _line_bezier((x2 - r, y2), (x1 + r, y2)),
        ((x1 + r, y2), (x1 + r - kr, y2), (x1, y2 - r + kr), (x1, y2 - r)),
        _line_bezier((x1, y2 - r), (x1, y1 + r)),
        ((x1, y1 + r), (x1, y1 + r - kr), (x1 + r - kr, y1), (x1 + r, y1)),
    ]
    return segs

def _ellipse_beziers(cx, cy, rx, ry, segments=4):
    if rx < 1e-3: rx = 1e-3
    if ry < 1e-3: ry = 1e-3
    n = max(4, int(segments or 4))
    d = (4.0 / 3.0) * math.tan(math.pi / (2.0 * n))
    segs = []
    for i in range(n):
        t1 = 2.0 * math.pi * i / n
        t2 = 2.0 * math.pi * (i + 1) / n
        c1, s1 = math.cos(t1), math.sin(t1)
        c2, s2 = math.cos(t2), math.sin(t2)
        p0 = (cx + rx * c1, cy + ry * s1)
        p3 = (cx + rx * c2, cy + ry * s2)
        cp1 = (cx + rx * (c1 - d * s1), cy + ry * (s1 + d * c1))
        cp2 = (cx + rx * (c2 + d * s2), cy + ry * (s2 - d * c2))
        segs.append((p0, cp1, cp2, p3))
    return segs

def _triangle_beziers(x1, y1, x2, y2, variant="isosceles"):
    """Triangle inscribed in the bbox. Variants: isosceles (apex top-centre),
    right (right angle at the bottom-left) or equilateral (fits the bbox)."""
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    if variant == "right":
        top = (x1, y1)
        br = (x2, y2)
        bl = (x1, y2)
    elif variant == "equilateral":
        side = min(w, 2.0 * h / math.sqrt(3.0))
        cx = (x1 + x2) / 2.0
        top = (cx, y2 - side * math.sqrt(3.0) / 2.0)
        bl = (cx - side / 2.0, y2)
        br = (cx + side / 2.0, y2)
    else:  # isosceles
        top = ((x1 + x2) / 2.0, y1)
        br = (x2, y2)
        bl = (x1, y2)
    return [_line_bezier(top, br), _line_bezier(br, bl), _line_bezier(bl, top)]


# --- Oriented shape fitting -------------------------------------------------
# Shapes are drawn by sketching their outline, so the doodle's orientation is
# kept: the fitted shape is a *perfect* rect/square/triangle that follows the
# sketch's tilt and size instead of being snapped to an axis-aligned box.

_AXIS_SNAP_DEG = 3.0  # sketches within this angle of an axis stay axis-aligned


def _snap_axis_delta(angle):
    """Return the rotation that would put ``angle`` on the nearest axis, or
    None when it is not close enough to count as axis-aligned."""
    target = round(angle / (math.pi / 2.0)) * (math.pi / 2.0)
    d = angle - target
    if abs(d) <= math.radians(_AXIS_SNAP_DEG):
        return -d
    return None


def _doodle_obb(points):
    """Oriented frame fitted to a doodle (min-area box), or None when the
    sketch is essentially a straight line or already axis-aligned."""
    obb = _min_area_obb(points)
    if obb is None:
        return None
    hw, hh = float(obb["hw"]), float(obb["hh"])
    if min(hw, hh) < 1.5:  # straight-ish drag: no reliable orientation
        return None
    ang = float(obb.get("angle", 0.0))
    if _snap_axis_delta(ang) is not None:
        return None
    ca, sa = math.cos(ang), math.sin(ang)
    return {"cx": obb["cx"], "cy": obb["cy"],
            "ux": ca, "uy": sa, "vx": -sa, "vy": ca,
            "hw": hw, "hh": hh, "angle": ang}


def _frame_point(lx, ly, fr):
    return (fr["cx"] + lx * fr["ux"] + ly * fr["vx"],
            fr["cy"] + lx * fr["uy"] + ly * fr["vy"])


def _frame_segs(segs, fr):
    return [tuple(_frame_point(p[0], p[1], fr) for p in seg) for seg in segs]


def _triangle_corners(points):
    """Rough three corners of a sketched triangle (max-area hull triangle)."""
    hull = _convex_hull(points)
    if len(hull) < 3:
        return None
    best = None
    n = len(hull)
    for i in range(n - 2):
        ax, ay = hull[i]
        for j in range(i + 1, n - 1):
            bx, by = hull[j]
            for k in range(j + 1, n):
                cx, cy = hull[k]
                area = abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay))
                if best is None or area > best[0]:
                    best = (area, (ax, ay), (bx, by), (cx, cy))
    if best is None or best[0] < 2.0:
        return None
    return [best[1], best[2], best[3]]


def _perfect_triangle(corners, variant):
    """Fit a perfect isosceles/right/equilateral triangle to three rough
    corners, keeping the sketched orientation, base length and height."""
    a, b, c = [(float(p[0]), float(p[1])) for p in corners]

    def sub(p, q):
        return (p[0] - q[0], p[1] - q[1])

    def dist(p, q):
        return math.hypot(q[0] - p[0], q[1] - p[1])

    def norm(v):
        l = math.hypot(v[0], v[1])
        return (v[0] / l, v[1] / l) if l > 1e-9 else (0.0, 0.0)

    def mid(p, q):
        return ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)

    ref_dir = None
    if variant == "right":
        # The right-angle corner is the sketched corner closest to 90 degrees.
        best = None
        for v, p, q in ((a, b, c), (b, c, a), (c, a, b)):
            u1, u2 = norm(sub(p, v)), norm(sub(q, v))
            cosang = abs(u1[0] * u2[0] + u1[1] * u2[1])
            if best is None or cosang < best[0]:
                best = (cosang, v, p, q)
        _, v, p, q = best
        u1, u2 = sub(p, v), sub(q, v)
        l1, l2 = math.hypot(*u1), math.hypot(*u2)
        if l1 < 1e-6 or l2 < 1e-6:
            return None
        long_v = u1 if l1 >= l2 else u2
        short_v = u2 if l1 >= l2 else u1
        lu = norm(long_v)
        ref_dir = lu
        perp = (-lu[1], lu[0])
        # Keep the sketched length of the short leg, squared to 90 degrees.
        sl = short_v[0] * perp[0] + short_v[1] * perp[1]
        if abs(sl) < 1e-6:
            return None
        p_long = (v[0] + long_v[0], v[1] + long_v[1])
        p_short = (v[0] + perp[0] * sl, v[1] + perp[1] * sl)
        pts = [v, p_long, p_short]
    else:
        if variant == "equilateral":
            # Longest sketched edge is the base; use the ideal height.
            edges = [(dist(a, b), a, b, c), (dist(b, c), b, c, a),
                     (dist(c, a), c, a, b)]
            base_len, p1, p2, apex_src = max(edges, key=lambda e: e[0])
            height = base_len * math.sqrt(3.0) / 2.0
        else:
            # Isosceles: apex is the corner with the most equal adjacent sides.
            best = None
            for v, p, q in ((a, b, c), (b, c, a), (c, a, b)):
                score = abs(dist(v, p) - dist(v, q))
                if best is None or score < best[0]:
                    best = (score, v, p, q)
            _, v, p, q = best
            p1, p2, apex_src = p, q, v
            height = None
        if dist(p1, p2) < 1e-6:
            return None
        m = mid(p1, p2)
        n = norm((-(p2[1] - p1[1]), p2[0] - p1[0]))
        if (apex_src[0] - m[0]) * n[0] + (apex_src[1] - m[1]) * n[1] < 0:
            n = (-n[0], -n[1])
        if height is None:
            height = abs((apex_src[0] - m[0]) * n[0] + (apex_src[1] - m[1]) * n[1])
            if height < 1e-6:
                return None
        apex = (m[0] + n[0] * height, m[1] + n[1] * height)
        pts = [apex, p1, p2]
        ref_dir = norm(sub(p2, p1))

    # Keep near-axis sketches crisp: square the whole triangle up when its
    # reference edge is already within the snap tolerance of an axis.
    delta = _snap_axis_delta(math.atan2(ref_dir[1], ref_dir[0])) if ref_dir else None
    if delta:
        ccx = sum(p[0] for p in pts) / 3.0
        ccy = sum(p[1] for p in pts) / 3.0
        ca, sa = math.cos(delta), math.sin(delta)
        pts = [(ccx + (x - ccx) * ca - (y - ccy) * sa,
                ccy + (x - ccx) * sa + (y - ccy) * ca) for x, y in pts]

    if (dist(pts[0], pts[1]) < 1e-6 or dist(pts[1], pts[2]) < 1e-6
            or dist(pts[2], pts[0]) < 1e-6):
        return None
    return [_line_bezier(pts[0], pts[1]), _line_bezier(pts[1], pts[2]),
            _line_bezier(pts[2], pts[0])]


def shape_from_doodle(points, shape_kind, variant=None, corner_radius=None,
                      segments=None, constrain=False):
    """Generate standard shape as a list of bezier segments from doodled points.
    Returns (segments, canonical_points). Each segment is intended as a separate stroke when possible.

    Shapes follow the doodle's orientation (sketch a tilted outline and get a
    perfect tilted shape). ``corner_radius`` is a percentage (0-50) of the
    rect/square min side, ``segments`` the number of bezier arcs for
    ellipse/circle and ``constrain`` snaps a line to the nearest 45-degree
    direction."""
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
        if constrain:
            dx, dy = p3[0] - p0[0], p3[1] - p0[1]
            length = math.hypot(dx, dy)
            if length > 1e-6:
                angle = round(math.atan2(dy, dx) / (math.pi / 4.0)) * (math.pi / 4.0)
                p3 = (p0[0] + math.cos(angle) * length, p0[1] + math.sin(angle) * length)
        return [_line_bezier(p0, p3)], [p0, p3]
    if shape_kind == "rect":
        fr = _doodle_obb(points)
        if fr is not None:
            hw, hh = fr["hw"], fr["hh"]
            rad = min(2.0 * hw, 2.0 * hh) * float(corner_radius or 0.0) / 100.0
            segs = _frame_segs(_rect_beziers(-hw, -hh, hw, hh, rad), fr)
            corners = [_frame_point(sx * hw, sy * hh, fr)
                       for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
            return segs, corners
        rad = (min(w, h) * float(corner_radius or 0.0) / 100.0)
        segs = _rect_beziers(x1, y1, x2, y2, rad)
        return segs, [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    if shape_kind == "square":
        fr = _doodle_obb(points)
        if fr is not None:
            s = min(2.0 * fr["hw"], 2.0 * fr["hh"])
            rad = s * float(corner_radius or 0.0) / 100.0
            segs = _frame_segs(_rect_beziers(-s / 2.0, -s / 2.0, s / 2.0, s / 2.0, rad), fr)
            corners = [_frame_point(sx * s / 2.0, sy * s / 2.0, fr)
                       for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
            return segs, corners
        s = min(w, h)
        sx1, sy1 = cx - s / 2.0, cy - s / 2.0
        sx2, sy2 = cx + s / 2.0, cy + s / 2.0
        rad = (s * float(corner_radius or 0.0) / 100.0)
        segs = _rect_beziers(sx1, sy1, sx2, sy2, rad)
        return segs, [(sx1, sy1), (sx2, sy1), (sx2, sy2), (sx1, sy2), (sx1, sy1)]
    if shape_kind == "ellipse":
        fr = _doodle_obb(points)
        if fr is not None:
            segs = _ellipse_beziers(0.0, 0.0, fr["hw"], fr["hh"], segments or 4)
            return _frame_segs(segs, fr), None
        return _ellipse_beziers(cx, cy, w / 2.0, h / 2.0, segments or 4), None
    if shape_kind == "circle":
        r = min(w, h) / 2.0
        return _ellipse_beziers(cx, cy, r, r, segments or 4), None
    if shape_kind == "triangle":
        corners = _triangle_corners(points)
        if corners is not None:
            segs = _perfect_triangle(corners, variant or "isosceles")
            if segs is not None:
                return segs, None
        return _triangle_beziers(x1, y1, x2, y2, variant or "isosceles"), None
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

def bbox_handle_local_positions(bbox, mode="scale"):
    """Local (lx,ly) offsets from bbox center for handles, by transform mode.

    scale: 8 resize handles (corners+sides). No separate 'rot' handle.
    rotate: 4 corner rotation handles + 4 side skew handles.
    """
    if bbox is None:
        return {}
    if isinstance(bbox, dict) and "angle" in bbox:
        hw, hh = bbox["hw"], bbox["hh"]
    else:
        x1, y1, x2, y2 = bbox
        hw, hh = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    if mode == "rotate":
        return {
            "rot_nw": (-hw, -hh), "skew_n": (0, -hh), "rot_ne": (hw, -hh),
            "skew_e": (hw, 0), "rot_se": (hw, hh), "skew_s": (0, hh),
            "rot_sw": (-hw, hh), "skew_w": (-hw, 0),
        }
    # scale (default)
    return {
        "nw": (-hw, -hh), "n": (0, -hh), "ne": (hw, -hh),
        "e": (hw, 0), "se": (hw, hh), "s": (0, hh),
        "sw": (-hw, hh), "w": (-hw, 0),
    }

def bbox_handles(bbox, rot_offset=22, mode="scale"):
    """Handle positions for AABB tuple or OBB dict. OBB rotates with the shape.

    mode="scale": resize handles (nw,n,ne,e,se,s,sw,w).
    mode="rotate": rotation corners (rot_*) and skew sides (skew_*).
    Back-compat: always includes 'rot' as a separate rotation handle in scale mode.
    """
    if bbox is None:
        return {}
    if isinstance(bbox, dict) and "angle" in bbox:
        cx, cy = bbox["cx"], bbox["cy"]
        hw, hh = bbox["hw"], bbox["hh"]
        ang = bbox.get("angle", 0.0)
        ca, sa = math.cos(ang), math.sin(ang)
        def P(lx, ly):
            return (cx + lx*ca - ly*sa, cy + lx*sa + ly*ca)
        handles = {name: P(lx, ly) for name, (lx, ly) in bbox_handle_local_positions(bbox, mode).items()}
        if mode == "scale":
            handles["rot"] = P(0, -hh - rot_offset)
        return handles
    x1, y1, x2, y2 = bbox
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    hw, hh = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    fake = {"hw": hw, "hh": hh}
    def P(lx, ly):
        return (mx + lx, my + ly)
    handles = {name: P(lx, ly) for name, (lx, ly) in bbox_handle_local_positions(fake, mode).items()}
    if mode == "scale":
        handles["rot"] = P(0, -hh - rot_offset)
    return handles

def _bbox_local_point(bbox, pos):
    """Return (lx,ly) of pos in bbox-local coords and bbox center (cx,cy,hw,hh,ang)."""
    if bbox is None:
        return None
    if isinstance(bbox, dict) and "angle" in bbox:
        cx, cy = bbox["cx"], bbox["cy"]
        hw, hh = bbox["hw"], bbox["hh"]
        ang = bbox.get("angle", 0.0)
    else:
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        hw, hh = (x2 - x1) / 2.0, (y2 - y1) / 2.0
        ang = 0.0
    dx, dy = pos[0] - cx, pos[1] - cy
    ca, sa = math.cos(ang), math.sin(ang)
    lx = dx*ca + dy*sa
    ly = -dx*sa + dy*ca
    return (lx, ly, cx, cy, hw, hh, ang)

def bbox_handle_anchor_local(handle, bbox):
    """Opposite/fixed local anchor for a scale handle (Inkscape-like)."""
    if bbox is None:
        return (0.0, 0.0)
    if isinstance(bbox, dict) and "angle" in bbox:
        hw, hh = bbox["hw"], bbox["hh"]
    else:
        x1, y1, x2, y2 = bbox
        hw, hh = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    anchors = {
        "nw": (hw, hh), "n": (0, hh), "ne": (-hw, hh),
        "e": (-hw, 0), "se": (-hw, -hh), "s": (0, -hh),
        "sw": (hw, -hh), "w": (hw, 0),
    }
    return anchors.get(handle, (0.0, 0.0))

def hit_test_bbox_handle(bbox, pos, radius=8.0, mode="scale"):
    if bbox is None:
        return None
    handles = bbox_handles(bbox, mode=mode)
    if mode == "rotate":
        order = ["rot_nw", "rot_ne", "rot_se", "rot_sw", "skew_n", "skew_e", "skew_s", "skew_w"]
    else:
        order = ["rot", "nw", "ne", "se", "sw", "n", "e", "s", "w"]
    for name in order:
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
