import math


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def rdp(points, epsilon):
    """Ramer-Douglas-Peucker simplification."""
    if len(points) < 3:
        return list(points)

    start = points[0]
    end = points[-1]
    index = -1
    dmax = 0.0

    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    seg_len_sq = dx * dx + dy * dy

    for i in range(1, len(points) - 1):
        px, py = points[i]
        if seg_len_sq == 0:
            d = distance((px, py), start)
        else:
            t = ((px - sx) * dx + (py - sy) * dy) / seg_len_sq
            t = max(0.0, min(1.0, t))
            proj = (sx + t * dx, sy + t * dy)
            d = distance((px, py), proj)
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        left = rdp(points[: index + 1], epsilon)
        right = rdp(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, s):
    return (a[0] * s, a[1] * s)


def catmull_rom_to_beziers(points, tension=0.0):
    """Convert polyline points to cubic Bezier segments.

    Uses Catmull-Rom to Bezier conversion. Each segment is
    (p0, c1, c2, p3) suitable for cairo curve_to(c1x,c1y,c2x,c2y,p3x,p3y).
    """
    pts = list(points)
    if len(pts) < 2:
        return []
    if len(pts) == 2:
        p0, p1 = pts
        c1 = _add(_mul(p0, 2 / 3), _mul(p1, 1 / 3))
        c2 = _add(_mul(p0, 1 / 3), _mul(p1, 2 / 3))
        return [(p0, c1, c2, p1)]

    # Duplicate endpoints for end conditions
    ext = [pts[0]] + pts + [pts[-1]]
    beziers = []
    s = (1.0 - tension) / 6.0

    for i in range(len(pts) - 1):
        p0 = ext[i]
        p1 = ext[i + 1]
        p2 = ext[i + 2]
        p3 = ext[i + 3]

        c1 = _add(p1, _mul(_sub(p2, p0), s))
        c2 = _sub(p2, _mul(_sub(p3, p1), s))
        beziers.append((p1, c1, c2, p2))
    return beziers


def _subsample(points, max_points):
    """Uniformly subsample points to at most max_points, keeping endpoints."""
    if max_points is None or len(points) <= max_points:
        return list(points)
    if max_points <= 2:
        return [points[0], points[-1]]
    n = max_points
    last = len(points) - 1
    indices = [round(i * last / (n - 1)) for i in range(n)]
    # Ensure strictly increasing indices where possible
    result = []
    seen = -1
    for idx in indices:
        idx = max(seen + 1, min(idx, last))
        if idx > seen:
            result.append(points[idx])
            seen = idx
    if result[-1] != points[-1]:
        if len(result) < max_points:
            result.append(points[-1])
        else:
            result[-1] = points[-1]
    return result


def _normalize_t(points):
    """Chord-length parameterization in [0,1] for points."""
    if len(points) == 1:
        return [0.0]
    dists = [0.0]
    total = 0.0
    for i in range(1, len(points)):
        total += distance(points[i - 1], points[i])
        dists.append(total)
    if total == 0:
        return [i / (len(points) - 1) for i in range(len(points))]
    return [d / total for d in dists]


def smooth_points(points, iterations=1):
    """Smooth a polyline with endpoint-preserving neighbor averaging."""
    pts = list(points)
    if len(pts) < 3 or iterations <= 0:
        return pts
    for _ in range(iterations):
        if len(pts) < 3:
            break
        new_pts = [pts[0]]
        for i in range(1, len(pts) - 1):
            x = (pts[i - 1][0] + pts[i][0] * 2 + pts[i + 1][0]) / 4.0
            y = (pts[i - 1][1] + pts[i][1] * 2 + pts[i + 1][1]) / 4.0
            new_pts.append((x, y))
        new_pts.append(pts[-1])
        pts = new_pts
    return pts


def fit_single_cubic_bezier(points):
    """Fit one cubic Bezier curve to stroke points.

    Returns a list with a single segment [(p0, c1, c2, p3)].
    Uses chord-length parameterization and least-squares fit for the two
    inner control points (endpoints fixed to first/last stroke points).
    """
    if len(points) < 2:
        return []
    if len(points) == 2:
        p0, p3 = points[0], points[1]
        c1 = _add(_mul(p0, 2 / 3), _mul(p3, 1 / 3))
        c2 = _add(_mul(p0, 1 / 3), _mul(p3, 2 / 3))
        return [(p0, c1, c2, p3)]

    p0 = points[0]
    p3 = points[-1]
    ts = _normalize_t(points)

    # B(t) = (1-t)^3 p0 + 3(1-t)^2 t c1 + 3(1-t) t^2 c2 + t^3 p3
    # Solve least squares for c1,c2: A [c1; c2] = b
    s11 = s12 = s22 = 0.0
    bx = by = cx = cy = 0.0
    for p, t in zip(points, ts):
        b1 = 3.0 * (1.0 - t) * (1.0 - t) * t
        b2 = 3.0 * (1.0 - t) * t * t
        b0 = (1.0 - t) ** 3
        b3 = t ** 3
        s11 += b1 * b1
        s12 += b1 * b2
        s22 += b2 * b2
        rx = p[0] - b0 * p0[0] - b3 * p3[0]
        ry = p[1] - b0 * p0[1] - b3 * p3[1]
        bx += b1 * rx
        by += b1 * ry
        cx += b2 * rx
        cy += b2 * ry

    det = s11 * s22 - s12 * s12
    if abs(det) < 1e-8:
        # Fallback: place controls along the chord
        c1 = _add(_mul(p0, 2 / 3), _mul(p3, 1 / 3))
        c2 = _add(_mul(p0, 1 / 3), _mul(p3, 2 / 3))
    else:
        inv11 = s22 / det
        inv22 = s11 / det
        inv12 = -s12 / det
        c1 = (inv11 * bx + inv12 * cx, inv11 * by + inv12 * cy)
        c2 = (inv12 * bx + inv22 * cx, inv12 * by + inv22 * cy)

    return [(p0, c1, c2, p3)]


def _indices_for_simplified(smoothed, simplified, eps=1e-9):
    """Return indices in smoothed for each point in simplified (subsequence)."""
    indices = []
    j = 0
    for i, p in enumerate(smoothed):
        if j >= len(simplified):
            break
        q = simplified[j]
        if abs(p[0] - q[0]) <= eps and abs(p[1] - q[1]) <= eps:
            indices.append(i)
            j += 1
    # Fallback: if matching failed (e.g. due to float quirks), map by nearest in order
    if len(indices) != len(simplified):
        indices = []
        start = 0
        for q in simplified:
            best_i = start
            best_d = float("inf")
            for i in range(start, len(smoothed)):
                d = (smoothed[i][0] - q[0]) ** 2 + (smoothed[i][1] - q[1]) ** 2
                if d < best_d:
                    best_d = d
                    best_i = i
            indices.append(best_i)
            start = best_i + 1
    return indices


def enforce_smooth_internal_joins(beziers):
    """Make handles symmetric at internal joints between adjacent segments.

    Least-squares fitting per segment can produce mismatched (non-mirrored)
    handles at shared anchors. Internal joins in a traced stroke should be
    smooth/symmetric, so we average opposing handle vectors around each joint.
    """
    if len(beziers) < 2:
        return beziers
    segs = [list(s) for s in beziers]
    for k in range(len(segs) - 1):
        # joint between seg k (p3) and seg k+1 (p0)
        anchor = segs[k][3]
        segs[k + 1][0] = anchor
        c2 = segs[k][2]      # incoming handle
        c1 = segs[k + 1][1]  # outgoing handle
        # symmetric: c1 - anchor == anchor - c2
        v_in = (anchor[0] - c2[0], anchor[1] - c2[1])
        v_out = (c1[0] - anchor[0], c1[1] - anchor[1])
        vx = (v_in[0] + v_out[0]) / 2.0
        vy = (v_in[1] + v_out[1]) / 2.0
        segs[k][2] = (anchor[0] - vx, anchor[1] - vy)
        segs[k + 1][1] = (anchor[0] + vx, anchor[1] + vy)
    return [tuple(s) for s in segs]


def fit_polyline_to_beziers(smoothed, simplified):
    """Fit cubic Bezier segments to smoothed stroke, one per simplified interval.

    Endpoints of each segment are the simplified anchor points; control points
    are least-squares fitted to the original/smoothed stroke samples in that
    interval for a closer reproduction of the drawn stroke.
    """
    if len(simplified) < 2:
        return []
    if len(simplified) == 2:
        # fit to all points between endpoints
        return fit_single_cubic_bezier(smoothed if smoothed else simplified)

    indices = _indices_for_simplified(smoothed, simplified)
    beziers = []
    for k in range(len(indices) - 1):
        i0, i1 = indices[k], indices[k + 1]
        if i1 < i0:
            i0, i1 = i1, i0
        seg_pts = smoothed[i0:i1 + 1]
        if len(seg_pts) < 2:
            seg_pts = [simplified[k], simplified[k + 1]]
        # Ensure endpoints match anchors exactly
        if seg_pts[0] != simplified[k]:
            seg_pts = [simplified[k]] + list(seg_pts[1:])
        if seg_pts[-1] != simplified[k + 1]:
            seg_pts = list(seg_pts[:-1]) + [simplified[k + 1]]
        fitted = fit_single_cubic_bezier(seg_pts)
        if fitted:
            beziers.append(fitted[0])
        else:
            # fallback straight segment
            p0, p3 = simplified[k], simplified[k + 1]
            c1 = _add(_mul(p0, 2 / 3), _mul(p3, 1 / 3))
            c2 = _add(_mul(p0, 1 / 3), _mul(p3, 2 / 3))
            beziers.append((p0, c1, c2, p3))
    return enforce_smooth_internal_joins(beziers)


def stroke_to_beziers(points, simplify_epsilon=2.0, tension=0.0, max_points=None, mode="poly", algorithm=None):
    """Convert a raw stroke to cubic Bezier curve(s).

    algorithm (preferred):
      - "fit": (default) simplify to anchor points and least-squares fit control
        points per segment to best replicate the stroke. Respects max_points.
      - "catmull-rom": simplify to anchor points and derive control points from
        Catmull-Rom tangents (faster heuristic, may fit less closely).
      - "single": fit one cubic Bezier curve to the whole stroke.

    mode is kept for backward compatibility ("single" -> single, "poly" -> fit).
    """
    if len(points) < 2:
        return []
    # Remove consecutive duplicates / near-duplicates
    filtered = [points[0]]
    for p in points[1:]:
        if distance(p, filtered[-1]) >= 0.5:
            filtered.append(p)
    if len(filtered) < 2:
        return []

    # Smooth input slightly to reduce jitter and produce smoother curves/edges
    smoothed = smooth_points(filtered, iterations=2)

    if algorithm is None:
        algorithm = "single" if mode == "single" else "fit"

    if algorithm == "single":
        return fit_single_cubic_bezier(smoothed)

    simplified = rdp(smoothed, simplify_epsilon)

    if max_points is not None:
        try:
            max_points = int(max_points)
        except Exception:
            max_points = None
    if max_points is not None and max_points >= 2 and len(simplified) > max_points:
        eps = simplify_epsilon
        # Increase simplification tolerance until within limit (or capped)
        for _ in range(12):
            eps *= 1.6
            simplified = rdp(smoothed, eps)
            if len(simplified) <= max_points:
                break
        if len(simplified) > max_points:
            simplified = _subsample(simplified, max_points)

    if len(simplified) < 2:
        return []
    if len(simplified) == 2:
        # best replication for a single segment regardless of heuristic algorithm
        return fit_single_cubic_bezier(smoothed)

    if algorithm == "catmull-rom":
        return catmull_rom_to_beziers(simplified, tension=tension)

    # Default "fit": fit control points to the stroke for better replication
    return fit_polyline_to_beziers(smoothed, simplified)
