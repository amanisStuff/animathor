"""Model: boolean set operations (union / intersection / difference) on filled
vector shapes.

The implementation builds a planar arrangement of the input boundaries and is
independent of pixels:

1. Sample every input shape's boundary into polylines.
2. Build one planar graph of all boundaries, splitting them at every crossing
   (reusing the geometry in ``models.fill``).
3. Enumerate the faces of that arrangement, keeping node ids.
4. Classify each bounded face as inside/outside each input shape using a point
   strictly inside the face and even-odd ray casting.
5. Select faces according to the operation:
       union        = in A or in B
       intersection = in A and in B
       difference   = in A and not in B (first shape minus the others)
6. Trace the directed edges separating selected from unselected faces into
   closed loops with the selected region on the left. Outer contours come out
   counter-clockwise and holes clockwise, which is correct for Cairo's default
   non-zero fill rule.
7. Fit a minimal chain of cubics to each loop, keeping sharp crossings hard.
"""

import math
from collections import defaultdict

import models.fill as _fill

# Public operation names.
UNION = "union"
INTERSECTION = "intersection"
DIFFERENCE = "difference"


def _faces_with_ids(nodes, edges):
    """Enumerate arrangement faces as ordered lists of node ids.

    Uses the same half-edge rule as ``fill._enumerate_faces`` (turn clockwise
    at each vertex, keeping the face on the left) but retains node ids so the
    face on either side of every directed edge can be identified.
    """
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
            face.append(cur[0])
            cur = next_edge.get(cur)
            steps += 1
        if len(face) >= 3:
            faces.append(face)
    return faces


def _face_probe_point(face_pts):
    """Return a point inside the region bordered by a directed face cycle.

    Tries points slightly to the left of long edges (inside the face by
    half-edge convention) and verifies containment to stay robust for thin
    faces. For the unbounded face the bordered region lies outside the vertex
    polygon, so verification accounts for face orientation.
    """
    n = len(face_pts)
    if n < 2:
        return face_pts[0] if face_pts else (0.0, 0.0)
    face_area = _fill._signed_area(face_pts)
    edges = []
    for i in range(n):
        a, b = face_pts[i], face_pts[(i + 1) % n]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length > 1e-9:
            edges.append((length, i, a, b))
    edges.sort(reverse=True)
    for length, _i, a, b in edges[:8]:
        dx, dy = b[0] - a[0], b[1] - a[1]
        mx, my = (a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5
        nx, ny = -dy / length, dx / length  # left normal of the directed edge
        for frac in (0.2, 0.1, 0.05, 0.02, 0.01):
            offset = max(0.05, min(0.75, length * frac))
            probe = (mx + nx * offset, my + ny * offset)
            in_poly = _fill._point_in_poly_ray(probe, face_pts)
            if (face_area >= 0 and in_poly) or (face_area < 0 and not in_poly):
                return probe
    # Fallback: centroid for bounded faces; for unbounded face, step outside.
    cx = sum(p[0] for p in face_pts) / n
    cy = sum(p[1] for p in face_pts) / n
    if face_area < 0:
        # push well outside the vertex polygon's bbox
        minx = min(p[0] for p in face_pts)
        miny = min(p[1] for p in face_pts)
        return (minx - 10.0, miny - 10.0)
    return (cx, cy)


def _point_in_shape(pt, shape_polylines):
    """Non-zero winding inside test across all boundary polylines of one shape."""
    winding = 0
    for pl in shape_polylines:
        if len(pl) >= 3:
            winding += _fill._poly_winding_number(pt, pl)
    return winding != 0


def boolean_loops(shapes, op=UNION, samples=18):
    """Return a list of closed output loops (each a list of 2D points).

    ``shapes`` is a sequence of stroke dicts (or raw segment lists). ``op`` is
    ``"union"``, ``"intersection"`` or ``"difference"``. Returns an empty list
    when the operation produces no region (e.g. intersection of disjoint
    shapes).
    """
    shapes = list(shapes)
    if len(shapes) < 2:
        return []
    op = (op or UNION).lower()

    shape_polys = []
    all_polys = []
    for shape in shapes:
        try:
            polys = _fill._stroke_boundary_polylines(shape, samples=samples)
        except Exception:
            polys = []
        polys = [pl for pl in polys if len(pl) >= 2]
        if not polys:
            return []
        shape_polys.append(polys)
        all_polys.extend(polys)

    nodes, edges = _fill._build_planar_graph(all_polys)
    if len(edges) < 3:
        return []

    faces = _faces_with_ids(nodes, edges)
    if not faces:
        return []

    # For every directed edge, the face on its left.
    directed_owner = {}
    for fi, face in enumerate(faces):
        m = len(face)
        for i in range(m):
            directed_owner[(face[i], face[(i + 1) % m])] = fi

    # Classify the region immediately left of every directed face cycle against
    # every input shape. Unbounded and hole cycles are classified too: a probe
    # just left of their edges correctly lands in the surrounding region.
    selected = []
    for face in faces:
        pts = [nodes[v] for v in face if v in nodes]
        if len(pts) < 3:
            selected.append(False)
            continue
        probe = _face_probe_point(pts)
        inside = [_point_in_shape(probe, polys) for polys in shape_polys]
        if op == INTERSECTION:
            keep = all(inside)
        elif op == DIFFERENCE:
            keep = inside[0] and not any(inside[1:])
        else:
            keep = any(inside)
        selected.append(keep)

    # Boundary directed edges: selected face on the left, non-selected on the
    # right. Those are exactly the edges of the result region.
    boundary = set()
    for fi, face in enumerate(faces):
        if not selected[fi]:
            continue
        m = len(face)
        for i in range(m):
            u, v = face[i], face[(i + 1) % m]
            other = directed_owner.get((v, u))
            if other is None or not selected[other]:
                boundary.add((u, v))
    if not boundary:
        return []

    # Boundary neighbors at each node, sorted counter-clockwise by angle.
    boundary_adj = defaultdict(list)
    for u, v in boundary:
        boundary_adj[u].append(v)
    for u, nbrs in boundary_adj.items():
        ux, uy = nodes[u]
        nbrs.sort(key=lambda v: math.atan2(nodes[v][1] - uy, nodes[v][0] - ux))

    two_pi = 2.0 * math.pi
    used = set()
    loops = []
    for start in list(boundary):
        if start in used:
            continue
        loop = []
        cur = start
        steps = 0
        while cur not in used and steps <= len(boundary) + 2:
            used.add(cur)
            u, v = cur
            loop.append(u)
            nbrs = boundary_adj.get(v, [])
            if not nbrs:
                break
            ang_u = math.atan2(nodes[u][1] - nodes[v][1], nodes[u][0] - nodes[v][0])
            # Leave via the boundary neighbor just clockwise from u, so the
            # selected region stays on the left (outer CCW, holes CW).
            best = None
            best_delta = None
            for w in nbrs:
                if (v, w) in used:
                    continue
                ang_w = math.atan2(nodes[w][1] - nodes[v][1], nodes[w][0] - nodes[v][0])
                delta = (ang_u - ang_w) % two_pi
                if delta < 1e-12:
                    continue
                if best is None or delta < best_delta:
                    best = w
                    best_delta = delta
            if best is None:
                break
            cur = (v, best)
            steps += 1
        if len(loop) >= 3:
            loops.append([nodes[v] for v in loop])
    return loops


def _mirror_handle(anchor, handle):
    return (2.0 * anchor[0] - handle[0], 2.0 * anchor[1] - handle[1])


def _is_symmetric_junction(seg_prev, seg_next, eps=1e-3):
    """True if the junction (seg_prev -> seg_next) has mirrored handles."""
    anchor = seg_next[0]
    h = seg_next[1]
    m = _mirror_handle(anchor, seg_prev[2])
    return math.hypot(m[0] - h[0], m[1] - h[1]) <= eps


def _loop_to_components(loop_segs, global_seg_offset=0):
    """Split a closed fitted loop into connected components at corner junctions.

    Returns (segs, components, corner_anchors) where components are consecutive
    curve segments joined by smooth/symmetrical nodes, and boundaries between
    components are non-symmetrical (corner) nodes.
    """
    n = len(loop_segs)
    if n == 0:
        return [], [], set()
    if n == 1:
        segs = list(loop_segs)
        comp = {"segs": list(segs), "raw_points": [], "draw_max_points": 4, "algorithm": "fit"}
        # single-segment closed loop: closure junction classification
        corners = set()
        if not _is_symmetric_junction(segs[0], segs[0]):
            corners.add((global_seg_offset, "p0"))
            corners.add((global_seg_offset, "p3"))
        return segs, [comp], corners

    corner_j = [not _is_symmetric_junction(loop_segs[j - 1], loop_segs[j]) for j in range(n)]
    corner_indices = [j for j, is_c in enumerate(corner_j) if is_c]
    if not corner_indices:
        segs = list(loop_segs)
        comp = {"segs": list(segs), "raw_points": [], "draw_max_points": 4, "algorithm": "fit"}
        return segs, [comp], set()

    # Start at a corner so component boundaries fall on contiguous slices.
    start = corner_indices[0]
    rotated = loop_segs[start:] + loop_segs[:start]
    rot_corner = corner_j[start:] + corner_j[:start]
    boundaries = [i for i, v in enumerate(rot_corner) if v]
    boundaries.append(n)

    components = []
    segs = []
    corner_anchors = set()
    for k in range(len(boundaries) - 1):
        a, b = boundaries[k], boundaries[k + 1]
        comp_segs = list(rotated[a:b])
        components.append({"segs": list(comp_segs), "raw_points": [], "draw_max_points": 4, "algorithm": "fit"})
        gi = global_seg_offset + a
        # Corner junction at boundary a: start of this component / end of previous.
        corner_anchors.add((gi, "p0"))
        prev_gi = global_seg_offset + (a - 1 if a > 0 else n - 1)
        corner_anchors.add((prev_gi, "p3"))
        segs.extend(comp_segs)
    return segs, components, corner_anchors


def boolean_result(shapes, op=UNION, samples=18, simplify_epsilon=1.5, max_segs=64):
    """Return (segs, components, corner_anchors) for the boolean result, or None.

    Result boundaries are split into connected components at non-symmetrical
    (corner) junctions, preserving the editing philosophy of smooth interior
    nodes and corner boundaries.
    """
    loops = boolean_loops(shapes, op=op, samples=samples)
    if not loops:
        return None
    all_segs = []
    all_components = []
    all_corners = set()
    for loop in loops:
        try:
            fitted = _fill._fit_face_beziers_adaptive(
                loop, simplify_epsilon, max_segs=max_segs
            )
        except Exception:
            fitted = None
        if not fitted or len(fitted) < 3:
            continue
        segs, comps, corners = _loop_to_components(fitted, global_seg_offset=len(all_segs))
        if not segs:
            continue
        all_segs.extend(segs)
        all_components.extend(comps)
        all_corners.update(corners)
    if len(all_segs) < 3:
        return None
    return all_segs, all_components, all_corners


def boolean_segs(shapes, op=UNION, samples=18, simplify_epsilon=1.5, max_segs=64):
    """Return closed cubic segments for the boolean result, or ``None``.

    Compatibility wrapper; see ``boolean_result`` for component/corner info.
    """
    res = boolean_result(shapes, op=op, samples=samples,
                         simplify_epsilon=simplify_epsilon, max_segs=max_segs)
    return res[0] if res else None
