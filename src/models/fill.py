"""Model: geometric bucket fill that creates a vector shape for an enclosed region.

This is independent of pixels. It samples the visible stroke boundaries into
polylines, splits them at every intersection (creating vertices at the crossing
points), builds a planar graph, then walks the faces of that graph to find the
smallest bounded face containing the click. The result is converted to a closed
Bezier shape. This is inspired by ray casting / planar face traversal.
"""

import math
from collections import defaultdict, deque

from bezier import fit_single_cubic_bezier, cubic_bezier_point

import models.strokes as _strokes
import models.waves as _waves

# Intersection / vertex merge tolerance, in canvas units.
_VERT_EPS = 0.5


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _seg_seg_intersection(p, p2, q, q2):
    """Return (t, u, (x,y)) where segment p->p2 crosses q->q2, or None.

    Handles proper crossings and T-junctions (one endpoint on the other
    segment), but skips a shared endpoint pair (those are connected elsewhere).
    """
    rx, ry = p2[0] - p[0], p2[1] - p[1]
    sx, sy = q2[0] - q[0], q2[1] - q[1]
    rxs = rx * sy - ry * sx
    qpx, qpy = q[0] - p[0], q[1] - p[1]
    qpxr = qpx * ry - qpy * rx
    eps = 1e-9
    if abs(rxs) < eps:
        # parallel or colinear -> no single crossing point
        return None
    t = (qpx * sy - qpy * sx) / rxs
    u = (qpx * ry - qpy * rx) / rxs
    if -eps <= t <= 1 + eps and -eps <= u <= 1 + eps:
        t = max(0.0, min(1.0, t))
        u = max(0.0, min(1.0, u))
        at_p_end = (t < eps or abs(t - 1.0) < eps)
        at_q_end = (u < eps or abs(u - 1.0) < eps)
        if at_p_end and at_q_end:
            return None
        return (t, u, (p[0] + t * rx, p[1] + t * ry))
    return None


def _stroke_boundary_polylines(stroke, samples=18):
    """Return polylines representing the visible boundaries of a stroke."""
    segs = _strokes.segs_of(stroke)
    if not segs:
        return []
    hidden = set()
    if isinstance(stroke, dict):
        hidden = set(stroke.get("hidden_segs", set()) or set())
    comps = _strokes._stroke_components(stroke)
    ranges = _strokes._component_ranges(stroke)
    polylines = []
    cur = None
    for ci, (s0, s1) in enumerate(ranges):
        comp = comps[ci] if ci < len(comps) else {}
        idxs = [i for i in range(s0, min(s1, len(segs))) if i not in hidden]
        if not idxs:
            continue
        if _waves._component_wave_enabled(comp) and len(idxs) == (min(s1, len(segs)) - s0):
            poly = _waves.sample_distorted_component(stroke, ci)
            if poly and len(poly) >= 2:
                sampled = [tuple(p) for p in poly]
                if cur is not None and _dist(cur[-1], sampled[0]) <= 1.0:
                    for pt in sampled[1:]:
                        if _dist(cur[-1], pt) > 1e-6:
                            cur.append(pt)
                else:
                    if cur and len(cur) >= 2:
                        polylines.append(cur)
                    cur = list(sampled)
                continue
            # fall through to segment sampling if distorted sampling failed
        for i in idxs:
            p0, c1, c2, p3 = segs[i]
            pts = [cubic_bezier_point(p0, c1, c2, p3, t / samples) for t in range(samples + 1)]
            if cur is None:
                cur = [tuple(pts[0])]
            elif _dist(cur[-1], pts[0]) > 1.0:
                if len(cur) >= 2:
                    polylines.append(cur)
                cur = [tuple(pts[0])]
            for pt in pts[1:]:
                tp = tuple(pt)
                if _dist(cur[-1], tp) > 1e-6:
                    cur.append(tp)
    if cur and len(cur) >= 2:
        polylines.append(cur)
    return polylines


def _build_planar_graph(polylines):
    """Split all segments at intersections and build a planar graph.

    Returns (nodes, edges) where nodes maps id -> (x, y) and edges is a list of
    (node_a, node_b). Intersection points become shared vertices, so curves that
    merely cross (without connected endpoints) form a connected graph.
    """
    segments = []
    for pl in polylines:
        for i in range(len(pl) - 1):
            a, b = pl[i], pl[i + 1]
            if _dist(a, b) > 1e-6:
                segments.append((a, b))
    if not segments:
        return {}, []

    # For each segment keep the sorted list of (t, point) split positions.
    splits = [[(0.0, s[0]), (1.0, s[1])] for s in segments]
    for i, (p, p2) in enumerate(segments):
        min1x, max1x = min(p[0], p2[0]), max(p[0], p2[0])
        min1y, max1y = min(p[1], p2[1]), max(p[1], p2[1])
        for j in range(i + 1, len(segments)):
            q, q2 = segments[j]
            min2x, max2x = min(q[0], q2[0]), max(q[0], q2[0])
            min2y, max2y = min(q[1], q2[1]), max(q[1], q2[1])
            if (max1x < min2x - _VERT_EPS or max2x < min1x - _VERT_EPS or
                    max1y < min2y - _VERT_EPS or max2y < min1y - _VERT_EPS):
                continue
            inter = _seg_seg_intersection(p, p2, q, q2)
            if inter is None:
                continue
            t, u, ipt = inter
            splits[i].append((t, ipt))
            splits[j].append((u, ipt))

    nodes = {}
    grid = defaultdict(list)

    def get_node(pt):
        """Reuse an existing node within _VERT_EPS, else create one.

        A spatial hash is used instead of round-to-grid bucketing: round()
        would assign different buckets to points that are only fractions of a
        pixel apart when they straddle a bucket boundary, which can leave a
        crossing point unmerged with a nearby sample point on another curve.
        """
        cx = math.floor(pt[0] / _VERT_EPS)
        cy = math.floor(pt[1] / _VERT_EPS)
        best = None
        best_d = _VERT_EPS
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for nid in grid.get((gx, gy), ()):
                    d = _dist(pt, nodes[nid])
                    if d < best_d:
                        best_d = d
                        best = nid
        if best is not None:
            return best
        nid = len(nodes)
        nodes[nid] = (float(pt[0]), float(pt[1]))
        grid[(cx, cy)].append(nid)
        return nid

    edges = []
    edge_set = set()
    for sp in splits:
        sp.sort(key=lambda x: x[0])
        # Dedupe only by parameter. Coincident points are collapsed by
        # get_node (nearest-node merge) when edges are built, so every split
        # point - including crossings - is registered as a vertex.
        compact = [sp[0]]
        for t, pt in sp[1:]:
            if abs(t - compact[-1][0]) < 1e-6:
                continue
            compact.append((t, pt))
        for k in range(len(compact) - 1):
            na = get_node(compact[k][1])
            nb = get_node(compact[k + 1][1])
            if na == nb:
                continue
            ekey = (min(na, nb), max(na, nb))
            if ekey in edge_set:
                continue
            edge_set.add(ekey)
            edges.append((na, nb))
    return nodes, edges


def _prune_dangling(nodes, edges):
    """Iteratively remove degree-1 vertices (open endpoints) and their edges.

    Dangling tips do not bound any face. Leaving them in makes the face walker
    traverse out-and-back spurs, producing degenerate self-overlapping faces.
    """
    if not nodes:
        return nodes, edges
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    active = {v: True for v in nodes}
    queue = deque(v for v in nodes if len(adj[v]) <= 1)
    while queue:
        v = queue.popleft()
        if not active[v]:
            continue
        active[v] = False
        for u in list(adj[v]):
            if active[u]:
                adj[u].discard(v)
                if len(adj[u]) <= 1:
                    queue.append(u)

    remap = {}
    new_nodes = {}
    for v in sorted(nodes):
        if active[v]:
            remap[v] = len(new_nodes)
            new_nodes[remap[v]] = nodes[v]
    new_edges = []
    seen = set()
    for a, b in edges:
        if a in remap and b in remap:
            na, nb = remap[a], remap[b]
            if na == nb:
                continue
            key = (min(na, nb), max(na, nb))
            if key in seen:
                continue
            seen.add(key)
            new_edges.append((na, nb))
    return new_nodes, new_edges


def _signed_area(poly):
    """Signed polygon area (positive for counter-clockwise)."""
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a * 0.5


def _enumerate_faces(nodes, edges):
    """Return every face as an ordered list of points using half-edge traversal."""
    if not edges:
        return []
    adj = defaultdict(list)
    for a, b in edges:
        if a in nodes and b in nodes:
            adj[a].append(b)
            adj[b].append(a)
    for v, nbrs in adj.items():
        vx, vy = nodes[v]
        nbrs.sort(key=lambda u: math.atan2(nodes[u][1] - vy, nodes[u][0] - vx))

    # For each directed edge (u -> v), the next directed edge (v -> w) that
    # keeps the face on the left is found by turning clockwise at v (the
    # neighbor just before u in CCW order).
    next_edge = {}
    for u, nbrs_u in adj.items():
        for v in nbrs_u:
            nbrs_v = adj[v]
            idx = nbrs_v.index(u)
            w = nbrs_v[(idx - 1) % len(nbrs_v)]
            next_edge[(u, v)] = (v, w)

    faces = []
    visited = set()
    for start in list(next_edge.keys()):
        if start in visited:
            continue
        face = []
        cur = start
        steps = 0
        max_steps = len(next_edge) + 2
        while cur is not None and cur not in visited and steps < max_steps:
            visited.add(cur)
            face.append(nodes[cur[0]])
            cur = next_edge.get(cur)
            steps += 1
        if len(face) >= 3:
            faces.append(face)
    return faces


def _point_in_poly_ray(pt, poly):
    """Even-odd ray cast point-in-polygon test."""
    x, y = pt
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xint = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xint:
                inside = not inside
        j = i
    return inside


def _poly_winding_number(pt, poly):
    """Winding number of a point with respect to a polygon."""
    x, y = pt
    winding = 0
    n = len(poly)
    if n < 3:
        return 0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if y1 <= y:
            if y2 > y:  # upward crossing
                if (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1) > 0:
                    winding += 1
        else:
            if y2 <= y:  # downward crossing
                if (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1) < 0:
                    winding -= 1
    return winding


def _point_in_poly_nonzero(pt, poly):
    """Non-zero winding rule point-in-polygon test."""
    return _poly_winding_number(pt, poly) != 0


def _face_containing_point(nodes, edges, point):
    """Find the smallest bounded face that contains `point`.

    Bounded faces have positive signed area under our left-face traversal; the
    single unbounded face has negative area and is excluded.
    """
    faces = _enumerate_faces(nodes, edges)
    candidates = []
    for face in faces:
        area = _signed_area(face)
        if area <= 1e-3:  # skip unbounded / degenerate faces
            continue
        if _point_in_poly_ray(point, face):
            candidates.append((area, face))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[0][1]


def _fit_face_beziers(dense, anchors):
    """Fit a closed chain of cubic Beziers through `anchors` to `dense` samples.

    This is deliberately NOT stroke_to_beziers: that helper smooths the input
    and forces smooth internal joins, which rounds off the intersection
    points. Here each anchor is a hard corner and each span is fitted only to
    the original curve samples between its two anchors, so the fill boundary
    stays exactly on the source curves and the corners stay sharp.
    """
    n = len(anchors)
    if n < 3 or len(dense) < 3:
        return None
    # Anchors are an ordered subsequence of dense (RDP returns input points).
    idxs = []
    j = 0
    for a in anchors:
        while j < len(dense) and _dist(dense[j], a) > 1e-6:
            j += 1
        if j >= len(dense):
            return None
        idxs.append(j)
        j += 1
    if len(idxs) != n:
        return None

    segs = []
    for k in range(n):
        i0 = idxs[k]
        i1 = idxs[(k + 1) % n]
        if i1 > i0:
            run = dense[i0:i1 + 1]
        else:
            run = dense[i0:] + dense[:i1 + 1]
        if len(run) < 2:
            run = [anchors[k], anchors[(k + 1) % n]]
        fitted = fit_single_cubic_bezier(run)
        if not fitted:
            return None
        segs.append(fitted[0])
    if len(segs) < 3:
        return None
    p0, c1, c2, _ = segs[-1]
    segs[-1] = (p0, c1, c2, segs[0][0])
    return segs


def _point_cubic_distance(p, cubic):
    """Perpendicular distance from point `p` to a cubic Bezier curve."""
    # Coarse scan for the nearest t, then ternary-search refinement. The
    # refinement matters for long spans: sparse sampling alone would make an
    # on-curve point look far away and trigger needless splits.
    coarse = 16
    best_t = 0.0
    best_d2 = float("inf")
    for i in range(coarse + 1):
        t = i / coarse
        q = cubic_bezier_point(*cubic, t)
        d2 = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_t = t
    lo = max(0.0, best_t - 1.0 / coarse)
    hi = min(1.0, best_t + 1.0 / coarse)
    for _ in range(8):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        q1 = cubic_bezier_point(*cubic, m1)
        q2 = cubic_bezier_point(*cubic, m2)
        d1 = (p[0] - q1[0]) ** 2 + (p[1] - q1[1]) ** 2
        d2 = (p[0] - q2[0]) ** 2 + (p[1] - q2[1]) ** 2
        if d1 < d2:
            hi = m2
        else:
            lo = m1
    t = (lo + hi) * 0.5
    q = cubic_bezier_point(*cubic, t)
    return _dist(p, q)


def _cubic_fit_error(points, cubic):
    """Return (max_perpendicular_error, index_of_worst_point)."""
    worst = 0.0
    worst_i = 0
    for i, p in enumerate(points):
        d = _point_cubic_distance(p, cubic)
        if d > worst:
            worst = d
            worst_i = i
    return worst, worst_i


def _fit_face_beziers_adaptive(dense, tol, max_segs=64):
    """Fit a minimal chain of cubic Beziers to the closed `dense` outline.

    RDP measures *straight-line* error, so it selects several anchors per
    smooth curve even though a single cubic reproduces that curve exactly.
    Here we fit one cubic to a span and only subdivide at the worst-deviation
    point when the actual cubic-fit error exceeds `tol`. Smooth spans collapse
    to one cubic; a sharp intersection corner is where a single cubic fits
    poorly, so it forces a split at that corner and the corner stays hard.
    """
    n = len(dense)
    if n < 3:
        return None
    seq = [(float(p[0]), float(p[1])) for p in dense]
    seq.append(seq[0])  # close the loop: valid span indices 0..n
    segments = []

    def fit_span(i0, i1):
        run = seq[i0:i1 + 1]
        fitted = fit_single_cubic_bezier(run)
        if not fitted:
            return
        cubic = fitted[0]
        if i1 - i0 < 2 or len(segments) >= max_segs:
            segments.append(cubic)
            return
        err, wi = _cubic_fit_error(run, cubic)
        if err <= tol:
            segments.append(cubic)
            return
        split = i0 + wi
        if split <= i0 or split >= i1:
            segments.append(cubic)
            return
        fit_span(i0, split)
        fit_span(split, i1)

    fit_span(0, n)
    if len(segments) < 3:
        return None
    p0, c1, c2, _ = segments[-1]
    segments[-1] = (p0, c1, c2, segments[0][0])
    return segments


def bucket_fill_to_beziers(strokes, pos, tolerance=12, simplify_epsilon=1.5, max_points=100):
    """Return Bezier segments for the smallest enclosed region containing `pos`.

    `strokes` supplies the geometric boundaries. `tolerance` is kept only for
    API compatibility (this fill is geometric, not pixel based).
    """
    if not strokes:
        return None
    polylines = []
    for st in strokes:
        try:
            pls = _stroke_boundary_polylines(st, samples=16)
        except Exception:
            pls = []
        for pl in pls:
            if len(pl) >= 2:
                polylines.append(pl)
    if not polylines:
        return None

    nodes, edges = _build_planar_graph(polylines)
    if len(edges) < 3:
        return None
    # Open curves have free endpoints; remove them so they don't create spurs.
    nodes, edges = _prune_dangling(nodes, edges)
    if len(edges) < 3:
        return None

    poly = _face_containing_point(nodes, edges, pos)
    if not poly or len(poly) < 3:
        return None
    if abs(_signed_area(poly)) < 4.0:
        return None

    pts = [(float(x), float(y)) for (x, y) in poly]
    dedup = [pts[0]]
    for p in pts[1:]:
        if _dist(dedup[-1], p) > 0.75:
            dedup.append(p)
    if len(dedup) >= 2 and _dist(dedup[0], dedup[-1]) < 0.75:
        dedup.pop()
    if len(dedup) < 3:
        return None

    try:
        # `simplify_epsilon` is now the cubic-fit tolerance (pixels). Adaptive
        # fitting emits only as many segments as the curves actually need.
        segs = _fit_face_beziers_adaptive(dedup, simplify_epsilon)
    except Exception:
        segs = None
    return segs
