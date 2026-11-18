"""Model: stroke data structures and operations."""

import math

from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

import models.geometry as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))



def new_stroke(segs, stroke_color=(0.1, 0.1, 0.15), stroke_width=3.0, fill_color=None, corner_anchors=None, algorithm="fit"):
    out = {
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
    try:
        out["obb"] = compute_stroke_obb(out)
    except Exception:
        pass
    return out

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
        try:
            out["obb"] = compute_stroke_obb(out)
        except Exception:
            pass
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

def _effective_component_style(stroke, comp_i):
    comps = _stroke_components(stroke)
    base_sc = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if isinstance(stroke, dict) else (0.1, 0.1, 0.15)
    base_sw = stroke.get("stroke_width", 3.0) if isinstance(stroke, dict) else 3.0
    if 0 <= comp_i < len(comps):
        c = comps[comp_i]
        if "stroke_color" in c and c["stroke_color"] is not None:
            base_sc = c["stroke_color"]
        if "stroke_width" in c and c["stroke_width"] is not None:
            base_sw = c["stroke_width"]
    return base_sc, float(base_sw)

def _stroke_has_component_styles(stroke):
    comps = _stroke_components(stroke) if isinstance(stroke, dict) else []
    for c in comps:
        if "stroke_color" in c or "stroke_width" in c:
            return True
    return False

def _stroke_has_varying_widths(stroke):
    comps = _stroke_components(stroke) if isinstance(stroke, dict) else []
    if len(comps) <= 1:
        return False
    widths = []
    for i in range(len(comps)):
        _, sw = _effective_component_style(stroke, i)
        widths.append(round(float(sw), 4))
    return len(set(widths)) > 1

def _component_index_for_seg(stroke, seg_i):
    ranges = _component_ranges(stroke)
    for ci, (s0, s1) in enumerate(ranges):
        if s0 <= seg_i < s1:
            return ci
    return 0

def _point_width_key(seg_i, anchor_name):
    return f"{int(seg_i)}:{anchor_name}"

def get_point_width(stroke, seg_i, anchor_name):
    """Width at an anchor point (p0/p3). Returns float or None if not set."""
    if not isinstance(stroke, dict):
        return None
    pw = stroke.get("point_widths") or {}
    if not pw:
        return None
    # direct
    k = _point_width_key(seg_i, anchor_name)
    if k in pw:
        try:
            return float(pw[k])
        except Exception:
            return None
    # shared anchor: p3 of seg_i-1 == p0 of seg_i
    segs = segs_of(stroke)
    if anchor_name == "p0" and seg_i > 0:
        k2 = _point_width_key(seg_i - 1, "p3")
        if k2 in pw:
            try:
                return float(pw[k2])
            except Exception:
                return None
    elif anchor_name == "p3" and seg_i + 1 < len(segs):
        k2 = _point_width_key(seg_i + 1, "p0")
        if k2 in pw:
            try:
                return float(pw[k2])
            except Exception:
                return None
    # closed shape wrap
    if segs and _is_closed_segs(segs, 6.0):
        if anchor_name == "p0" and seg_i == 0:
            k2 = _point_width_key(len(segs) - 1, "p3")
            if k2 in pw:
                try:
                    return float(pw[k2])
                except Exception:
                    return None
        elif anchor_name == "p3" and seg_i == len(segs) - 1:
            k2 = _point_width_key(0, "p0")
            if k2 in pw:
                try:
                    return float(pw[k2])
                except Exception:
                    return None
    return None

def set_point_width(stroke, seg_i, anchor_name, width):
    """Set width at an anchor point and sync shared/closed anchors."""
    if not isinstance(stroke, dict):
        return
    segs = segs_of(stroke)
    if not (0 <= seg_i < len(segs)) or anchor_name not in ("p0", "p3"):
        return
    pw = dict(stroke.get("point_widths") or {})
    keys = {_point_width_key(seg_i, anchor_name)}
    # shared neighbors
    if anchor_name == "p0" and seg_i > 0:
        keys.add(_point_width_key(seg_i - 1, "p3"))
    elif anchor_name == "p3" and seg_i + 1 < len(segs):
        keys.add(_point_width_key(seg_i + 1, "p0"))
    # closed wrap
    if segs and _is_closed_segs(segs, 6.0):
        if anchor_name == "p0" and seg_i == 0:
            keys.add(_point_width_key(len(segs) - 1, "p3"))
        elif anchor_name == "p3" and seg_i == len(segs) - 1:
            keys.add(_point_width_key(0, "p0"))
    w = max(0.5, float(width))
    for k in keys:
        pw[k] = w
    stroke["point_widths"] = pw

def _segment_endpoint_widths(stroke, seg_i):
    """(w_start, w_end) for segment, considering point widths and component fallback."""
    ci = _component_index_for_seg(stroke, seg_i)
    _, base_w = _effective_component_style(stroke, ci)
    w0 = get_point_width(stroke, seg_i, "p0")
    w1 = get_point_width(stroke, seg_i, "p3")
    return (float(w0) if w0 is not None else float(base_w),
            float(w1) if w1 is not None else float(base_w))

def _stroke_needs_variable_width(stroke, seg_indices=None):
    if not isinstance(stroke, dict):
        return False
    segs = segs_of(stroke)
    if seg_indices is None:
        seg_indices = range(len(segs))
    for i in seg_indices:
        if 0 <= i < len(segs):
            ws, we = _segment_endpoint_widths(stroke, i)
            if abs(ws - we) > 1e-6:
                return True
    if stroke.get("point_widths"):
        return True
    return False

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
    try:
        out["obb"] = compute_stroke_obb(out)
    except Exception:
        pass
    return out

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
        obb = get_stroke_obb(out)
        if obb is not None:
            out["obb"] = translate_obb(obb, dx, dy)
        return out
    return moved

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
        obb = get_stroke_obb(out)
        if obb is not None:
            out["obb"] = transform_obb_corners(
                obb, lambda pt: apply_affine(pt, cx, cy, ca, sa, scale_x, scale_y)
            )
        return out
    return moved

def scale_stroke_local(stroke, fixed_pt, ang, su, sv):
    """Scale stroke in local axes (rotated by ang) keeping fixed_pt fixed."""
    ca, sa = math.cos(ang), math.sin(ang)
    fx, fy = fixed_pt
    def _xf(pt):
        dx, dy = pt[0] - fx, pt[1] - fy
        lx = dx * ca + dy * sa
        ly = -dx * sa + dy * ca
        lx *= su; ly *= sv
        return (fx + lx * ca - ly * sa, fy + lx * sa + ly * ca)
    segs = segs_of(stroke)
    moved = [(_xf(p0), _xf(c1), _xf(c2), _xf(p3)) for (p0, c1, c2, p3) in segs]
    if isinstance(stroke, dict):
        out = dict(stroke); out["segs"] = moved
        obb = get_stroke_obb(out)
        if obb is not None:
            out["obb"] = scale_obb_local(obb, fixed_pt, ang, su, sv)
        return out
    return moved

def rotate_stroke_around(stroke, cx, cy, angle_rad):
    """Rotate stroke around (cx,cy) by angle_rad."""
    ca, sa = math.cos(angle_rad), math.sin(angle_rad)
    def _xf(pt):
        dx, dy = pt[0] - cx, pt[1] - cy
        return (cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)
    segs = segs_of(stroke)
    moved = [(_xf(p0), _xf(c1), _xf(c2), _xf(p3)) for (p0, c1, c2, p3) in segs]
    if isinstance(stroke, dict):
        out = dict(stroke); out["segs"] = moved
        obb = get_stroke_obb(out)
        if obb is not None:
            out["obb"] = rotate_obb(obb, cx, cy, angle_rad)
        return out
    return moved

def skew_stroke_local(stroke, center_pt, ang, skew_x, skew_y):
    """Skew stroke in local axes around center_pt.
    skew_x shears local X by local Y (x' = x + skew_x*y), skew_y shears Y by X.
    """
    ca, sa = math.cos(ang), math.sin(ang)
    cx, cy = center_pt
    def _xf(pt):
        dx, dy = pt[0] - cx, pt[1] - cy
        lx = dx * ca + dy * sa
        ly = -dx * sa + dy * ca
        lx2 = lx + skew_x * ly
        ly2 = ly + skew_y * lx
        return (cx + lx2 * ca - ly2 * sa, cy + lx2 * sa + ly2 * ca)
    segs = segs_of(stroke)
    moved = [(_xf(p0), _xf(c1), _xf(c2), _xf(p3)) for (p0, c1, c2, p3) in segs]
    if isinstance(stroke, dict):
        out = dict(stroke); out["segs"] = moved
        obb = get_stroke_obb(out)
        if obb is not None:
            out["obb"] = skew_obb_local(obb, center_pt, ang, skew_x, skew_y)
        return out
    return moved

def mirror_stroke(stroke, cx, cy, axis="h"):
    """Mirror (flip) stroke across a vertical (axis='h') or horizontal (axis='v') line through (cx,cy)."""
    segs = segs_of(stroke)
    if axis == "v":
        def _xf(pt):
            return (pt[0], 2 * cy - pt[1])
    else:
        def _xf(pt):
            return (2 * cx - pt[0], pt[1])
    moved = [(_xf(p0), _xf(c1), _xf(c2), _xf(p3)) for (p0, c1, c2, p3) in segs]
    if isinstance(stroke, dict):
        out = _copy_stroke(stroke)
        out["segs"] = moved
        obb = get_stroke_obb(out)
        if obb is not None:
            out["obb"] = mirror_obb(obb, cx, cy, axis)
        # segment geometry is mirrored but topology/indices are unchanged
        return out
    return moved

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
        try:
            out["obb"] = compute_stroke_obb(out)
        except Exception:
            pass
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
        # start/end swap when the direction flips
        ce = _cut_ends(out)
        if ce:
            swapped = {}
            if "end" in ce:
                swapped["start"] = ce["end"]
            if "start" in ce:
                swapped["end"] = ce["start"]
            out["cut_ends"] = swapped
        return out
    return rev

def _pts_close(a, b, eps=6.0):
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= eps

def _with_segs(stroke, segs):
    if isinstance(stroke, dict):
        out = dict(stroke)
        out["segs"] = segs
        try:
            out["obb"] = compute_stroke_obb(out)
        except Exception:
            pass
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
    if "cut_ends" in out:
        out["cut_ends"] = dict(out.get("cut_ends") or {})
    if "components" in out:
        out["components"] = [dict(c) for c in (out.get("components") or [])]
    if "obb" in out and isinstance(out["obb"], dict):
        obb = dict(out["obb"])
        if "corners" in obb and obb["corners"] is not None:
            obb["corners"] = [tuple(p) for p in obb["corners"]]
        out["obb"] = obb
    return out

def _cut_ends(stroke):
    """Endpoint flags set by the razor: {"start"/"end": "cut"|"seam"}."""
    if isinstance(stroke, dict):
        return dict(stroke.get("cut_ends") or {})
    return {}

def _close_path_if_needed(stroke, eps=6.0):
    """If a path's endpoints are within eps, make them exactly identical.

    Closing a path joins the two ends, so the closure anchor is marked as a corner.
    Razor-cut ends are left open: closing them would undo the cut.
    """
    if _cut_ends(stroke):
        return stroke
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
                ca, cb = _cut_ends(a), _cut_ends(b)
                merged = None
                merged_comps = None
                merged_ends = None
                if "end" not in ca and "start" not in cb and _pts_close(a_end, b_start, eps):
                    # A followed by B
                    b2 = list(b_segs)
                    b2[0] = (a_end, b2[0][1], b2[0][2], b2[0][3])
                    na = len(a_segs)
                    corners = _corners(a) | _shift_corners(_corners(b), na) | {(na - 1, "p3"), (na, "p0")}
                    merged = _set_corners(_with_segs(a, list(a_segs) + b2), corners)
                    merged_comps = _stroke_components(a) + _stroke_components(b)
                    merged_ends = {"start": ca.get("start"), "end": cb.get("end")}
                elif "end" not in ca and "end" not in cb and _pts_close(a_end, b_end, eps):
                    # A followed by reversed B
                    rb = reverse_stroke(b)
                    rb_segs = list(segs_of(rb))
                    rb_segs[0] = (a_end, rb_segs[0][1], rb_segs[0][2], rb_segs[0][3])
                    na = len(a_segs)
                    corners = _corners(a) | _shift_corners(_corners(rb), na) | {(na - 1, "p3"), (na, "p0")}
                    merged = _set_corners(_with_segs(a, list(a_segs) + rb_segs), corners)
                    merged_comps = _stroke_components(a) + _stroke_components(rb)
                    merged_ends = {"start": ca.get("start"), "end": cb.get("start")}
                elif "start" not in ca and "end" not in cb and _pts_close(a_start, b_end, eps):
                    # B followed by A
                    a2 = list(a_segs)
                    a2[0] = (b_end, a2[0][1], a2[0][2], a2[0][3])
                    nb = len(b_segs)
                    corners = _corners(b) | _shift_corners(_corners(a), nb) | {(nb - 1, "p3"), (nb, "p0")}
                    merged = _set_corners(_with_segs(b, list(b_segs) + a2), corners)
                    merged_comps = _stroke_components(b) + _stroke_components(a)
                    merged_ends = {"start": cb.get("start"), "end": ca.get("end")}
                elif "start" not in ca and "start" not in cb and _pts_close(a_start, b_start, eps):
                    # Reversed B followed by A
                    rb = reverse_stroke(b)
                    rb_segs = list(segs_of(rb))
                    a2 = list(a_segs)
                    a2[0] = (rb_segs[-1][3], a2[0][1], a2[0][2], a2[0][3])
                    nb = len(rb_segs)
                    corners = _corners(rb) | _shift_corners(_corners(a), nb) | {(nb - 1, "p3"), (nb, "p0")}
                    merged = _set_corners(_with_segs(rb, rb_segs + a2), corners)
                    merged_comps = _stroke_components(rb) + _stroke_components(a)
                    merged_ends = {"start": cb.get("end"), "end": ca.get("end")}
                if merged is not None:
                    if isinstance(merged, dict) and merged_comps is not None:
                        merged["components"] = merged_comps
                        # hidden segs offsets across merges are complex; reset for safety
                        merged["hidden_segs"] = set()
                    if isinstance(merged, dict):
                        ends = {k: v for k, v in (merged_ends or {}).items() if v}
                        if ends:
                            merged["cut_ends"] = ends
                        else:
                            merged.pop("cut_ends", None)
                    paths[i] = _close_path_if_needed(merged, eps=eps)
                    paths.pop(j)
                    changed = True
                    break
            if changed:
                break
    for i in range(len(paths)):
        paths[i] = _close_path_if_needed(paths[i], eps=eps)
    return paths

def _stroke_has_wave(stroke):
    for comp in _stroke_components(stroke):
        if _component_wave_enabled(comp):
            return True
    return False


def join_components_in_stroke(stroke, comp_indices):
    """Merge consecutive selected components of *stroke* into single components.

    *comp_indices* is an iterable of component indices to join. Only runs of
    consecutive indices in component order are merged (e.g. selecting 0,1,3 joins
    0+1 but leaves 3 alone). Returns ``(new_stroke, index_map)`` where
    ``index_map[old_i]`` is the component index in the returned stroke. If
    nothing can be merged, returns ``(stroke, None)``.
    """
    if not isinstance(stroke, dict):
        return stroke, None
    comps = _stroke_components(stroke)
    n = len(comps)
    wanted = sorted({int(i) for i in (comp_indices or []) if 0 <= int(i) < n})
    if len(wanted) < 2:
        return stroke, None
    wanted_set = set(wanted)

    # Build contiguous runs that should be merged.
    runs = []
    i = 0
    while i < n:
        if i in wanted_set:
            j = i + 1
            while j < n and j in wanted_set:
                j += 1
            runs.append((i, j))  # [i, j)
            i = j
        else:
            runs.append((i, i + 1))
            i += 1

    if not any(e - s >= 2 for s, e in runs):
        return stroke, None

    new_comps = []
    index_map = {}
    # Track global seg indices of internal join boundaries (end of seg i / start i+1)
    # created by merging components; these must become smooth/symmetrical interior nodes.
    join_junction_seg_indices = set()
    global_offset = 0
    for s, e in runs:
        if e - s == 1:
            index_map[s] = len(new_comps)
            segs_k = comps[s].get("segs") or []
            if not segs_k:
                ranges = _component_ranges(stroke)
                if 0 <= s < len(ranges):
                    a, b = ranges[s]
                    segs_k = list(segs_of(stroke))[a:b]
            global_offset += len(segs_k)
            new_comps.append(comps[s])
            continue
        # Merge components s..e-1.
        merged = dict(comps[s])
        merged_segs = []
        run_local_offset = 0
        for k in range(s, e):
            c = comps[k]
            segs_k = c.get("segs") or []
            if not segs_k:
                ranges = _component_ranges(stroke)
                if 0 <= k < len(ranges):
                    a, b = ranges[k]
                    segs_k = list(segs_of(stroke))[a:b]
            segs_k = list(segs_k)
            if merged_segs and segs_k:
                # Junction between previous and this component inside the merged run.
                join_junction_seg_indices.add(global_offset + run_local_offset - 1)
            merged_segs.extend(segs_k)
            run_local_offset += len(segs_k)
        merged["segs"] = merged_segs
        # A joined curve is a new structural unit; raw points from pre-split
        # pieces were cleared on split and can't represent the whole.
        merged["raw_points"] = []
        new_idx = len(new_comps)
        for k in range(s, e):
            index_map[k] = new_idx
        new_comps.append(merged)
        global_offset += run_local_offset

    out = _copy_stroke(stroke)
    out["components"] = new_comps
    # Keep top-level segs consistent with components.
    all_segs = []
    for c in new_comps:
        all_segs.extend(list(c.get("segs") or []))
    if all_segs:
        out["segs"] = all_segs
    # Enforce symmetry at internal join junctions: nodes that are not end/start
    # of a curve must be symmetrical. Joining makes former endpoints interior, so
    # mirror handles at the join (shape may change, which is acceptable).
    corners = set(_corners(out))
    segs_list = [list(s) for s in segs_of(out)]
    n_segs = len(segs_list)
    for i in sorted(join_junction_seg_indices):
        if i < 0 or i + 1 >= n_segs:
            continue
        # Junction between seg i (p3/c2) and seg i+1 (p0/c1).
        corners.discard((i, "p3"))
        corners.discard((i + 1, "p0"))
        anchor = segs_list[i][3]
        # Keep left outgoing handle, mirror it to the right incoming handle.
        segs_list[i + 1][1] = _mirror_handle(anchor, segs_list[i][2])
        segs_list[i + 1][0] = anchor
        segs_list[i][3] = anchor
    if join_junction_seg_indices:
        out["segs"] = [tuple(s) for s in segs_list]
        # keep component segs consistent
        pos = 0
        for c in new_comps:
            k = len(c.get("segs") or [])
            c["segs"] = list(out["segs"][pos:pos + k])
            pos += k
        out["components"] = new_comps
        out = _set_corners(out, corners)
    # Structural change: clear hidden segs for safety (consistent with redraw).
    out["hidden_segs"] = set()
    # Point widths are keyed by segment indices; after a structural merge of
    # components the global seg layout is unchanged, so keep them as-is.
    return out, index_map

