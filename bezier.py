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


def stroke_to_beziers(points, simplify_epsilon=2.0, tension=0.0, max_points=None, mode="poly"):
    """Convert a raw stroke to cubic Bezier curve(s).

    mode:
      - "poly": simplify stroke and fit a chain of cubic Bezier segments
        (Catmull-Rom to Bezier). `max_points` limits simplified points.
      - "single": fit one cubic Bezier curve to the whole stroke.
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

    if mode == "single":
        return fit_single_cubic_bezier(filtered)

    simplified = rdp(filtered, simplify_epsilon)

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
            simplified = rdp(filtered, eps)
            if len(simplified) <= max_points:
                break
        if len(simplified) > max_points:
            simplified = _subsample(simplified, max_points)

    return catmull_rom_to_beziers(simplified, tension=tension)
