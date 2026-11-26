"""Model: snapping, hit testing and drawing-point collection."""

import math

from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

import models.geometry as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))

import models.strokes as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))

import models.waves as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))



def scrub_value(start_value, min_v, max_v, width, start_x, current_x,
                step=None, fine=False, coarse=False):
    """Map a horizontal drag delta to a value (Blender/Krita style scrubbing).

    The value follows the pointer *relative to where the drag started*: clicking
    a numeric field never jumps to the clicked position. A drag across the
    field width covers the full range; Ctrl is ten times finer and Shift five
    times coarser. ``step`` quantises the result when the field is integral.
    """
    lo, hi = float(min_v), float(max_v)
    if hi <= lo:
        return lo
    per_pixel = (hi - lo) / max(1.0, float(width))
    if fine:
        per_pixel *= 0.1
    elif coarse:
        per_pixel *= 5.0
    value = float(start_value) + (float(current_x) - float(start_x)) * per_pixel
    if step:
        value = round(value / float(step)) * float(step)
    return min(hi, max(lo, value))


def xform_step(fine=False, coarse=False):
    """Step size for the transform-field arrow nudge buttons/keys.

    ``Ctrl``/``Cmd`` selects a fine 0.1 step for precise adjustment, ``Shift``
    selects a coarse 10.0 step, and the default is 1.0. Fine wins when both
    modifiers are held so the user can always get the most specific control.
    """
    if fine:
        return 0.1
    if coarse:
        return 10.0
    return 1.0


def nearest_endpoint(pos, strokes, radius, extra_points=None):
    if radius <= 0:
        return None
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
    if radius <= 0:
        return None
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
        # Hidden/locked objects (organization/layers) are not canvas-selectable.
        if isinstance(stroke, dict) and (stroke.get("hidden", False) or stroke.get("locked", False)):
            continue
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

def erase_curve_at(strokes, pos, threshold=10.0):
    """Remove the curve/component (edge) clicked at pos. Returns (new_strokes, erased)."""
    si = hit_test_stroke(pos, strokes, threshold=threshold)
    if si is None or not (0 <= si < len(strokes)):
        return strokes, False
    stroke = strokes[si]
    comps = _stroke_components(stroke)
    if not comps:
        new_list = list(strokes)
        new_list.pop(si)
        return new_list, True
    ci = hit_test_component(stroke, pos, threshold=threshold)
    if ci is None:
        # fallback: remove whole stroke if clicked but component not resolved
        new_list = list(strokes)
        new_list.pop(si)
        return new_list, True
    if len(comps) <= 1:
        new_list = list(strokes)
        new_list.pop(si)
        return new_list, True
    # remove one component: replace stroke with remaining components as separate strokes
    replacements = []
    for j, comp in enumerate(comps):
        if j == ci:
            continue
        segs = list(comp.get("segs") or [])
        if not segs:
            continue
        sc, sw = _effective_component_style(stroke, j)
        st = new_stroke(segs, stroke_color=sc, stroke_width=sw, fill_color=None, algorithm=comp.get("algorithm", stroke.get("algorithm", "fit")))
        comp_copy = dict(comp)
        comp_copy["segs"] = list(segs)
        st["components"] = [comp_copy]
        # keep per-component style on component too
        if "stroke_color" in comp or sc is not None:
            st["components"][0]["stroke_color"] = sc
        if "stroke_width" in comp or sw is not None:
            st["components"][0]["stroke_width"] = sw
        replacements.append(st)
    new_list = list(strokes[:si]) + replacements + list(strokes[si + 1:])
    return new_list, True

# --- Split curve (razor) ----------------------------------------------------
# A cutter swipe is a polyline in canvas space. Every visible curve segment it
# crosses is split at the crossing (De Casteljau), turning the stroke into two
# or more independent strokes while keeping its style and component styles.

def _lerp_pt(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def split_cubic_at(seg, t):
    """Split a cubic bezier at parameter ``t``; returns (left, right)."""
    p0, c1, c2, p3 = seg
    a = _lerp_pt(p0, c1, t)
    b = _lerp_pt(c1, c2, t)
    c = _lerp_pt(c2, p3, t)
    d = _lerp_pt(a, b, t)
    e = _lerp_pt(b, c, t)
    f = _lerp_pt(d, e, t)
    return (tuple(p0), a, d, f), (f, e, c, tuple(p3))


def _sub_cubic(seg, t0, t1):
    """The portion of ``seg`` between parameters ``t0 < t1``."""
    if t0 <= 1e-9 and t1 >= 1.0 - 1e-9:
        return tuple(seg)
    left, right = split_cubic_at(seg, t0)
    if t1 >= 1.0 - 1e-9:
        return right
    t = (t1 - t0) / max(1e-9, 1.0 - t0)
    return split_cubic_at(right, t)[0]


# A razor cut breaks a curve at each crossing. With no gap the stroke stays one
# connected path: the crossing simply becomes a new anchor, so both new curves
# still share it and anything joined to the stroke stays joined. An optional
# gap trims a little material from each side and then the pieces are separate.


def _insert_cut_nodes(stroke, cuts):
    """Split a stroke at every cut into separately selectable curve components.

    Each crossing becomes a new anchor and also starts a new component, so the
    two resulting curves can be picked individually in Curve mode. The stroke
    itself stays one object and the halves share the node, so anything joined to
    the stroke stays joined. Returns the modified stroke, or ``None`` when no
    interior cut was found."""
    segs = list(segs_of(stroke))
    params_by_seg = {}
    for si, ts in (cuts or {}).items():
        if not (0 <= si < len(segs)):
            continue
        vals = sorted({clamp(float(t), 0.0, 1.0) for t in ts
                       if 1e-4 < float(t) < 1.0 - 1e-4})
        if vals:
            params_by_seg[si] = vals
    if not params_by_seg:
        return None

    new_segs = []
    seg_map = {}  # original segment index -> (first, last) new index
    for si, seg in enumerate(segs):
        ts = [0.0] + params_by_seg.get(si, []) + [1.0]
        first = len(new_segs)
        for t0, t1 in zip(ts, ts[1:]):
            new_segs.append(_sub_cubic(seg, t0, t1))
        seg_map[si] = (first, len(new_segs) - 1)

    if not isinstance(stroke, dict):
        return new_segs

    out = _copy_stroke(stroke)
    out["segs"] = new_segs

    # Anchors travel with their segment. Newly created cut/split nodes become
    # the start/end of the resulting curve components, so they should not be
    # forced symmetrical (endpoints of curves need not be symmetrical).
    corners = set()
    for si, name in _corners(stroke):
        if si in seg_map:
            first, last = seg_map[si]
            corners.add((first if name == "p0" else last, name))
    # Interior cut nodes: boundaries between split pieces of a segment.
    for si, ts in params_by_seg.items():
        first, last = seg_map[si]
        for k in range(first, last):
            corners.add((k, "p3"))
            corners.add((k + 1, "p0"))
    out["corner_anchors"] = corners

    hidden = set()
    for si in (stroke.get("hidden_segs") or ()):
        if si in seg_map:
            hidden.add(seg_map[si][0])
    out["hidden_segs"] = hidden

    pw = stroke.get("point_widths")
    if pw:
        new_pw = {}
        for si in range(len(segs)):
            first, last = seg_map[si]
            if si in params_by_seg:
                w0 = get_point_width(stroke, si, "p0")
                w1 = get_point_width(stroke, si, "p3")
                ts = [0.0] + params_by_seg[si] + [1.0]
                for k in range(len(ts) - 1):
                    new_pw[f"{first + k}:p0"] = w0 + (w1 - w0) * ts[k]
                    new_pw[f"{first + k}:p3"] = w0 + (w1 - w0) * ts[k + 1]
            else:
                for name, idx in (("p0", first), ("p3", last)):
                    key = f"{si}:{name}"
                    if key in pw:
                        new_pw[f"{idx}:{name}"] = pw[key]
        out["point_widths"] = new_pw

    # Rebuild components, breaking each one at the new cut nodes. Every half
    # keeps the original component's style, so the split is purely structural.
    comps_src = _stroke_components(stroke)
    ranges = _component_ranges(stroke)
    covered = ranges[-1][1] if ranges else 0
    if covered < len(segs):
        comps_src = list(comps_src) + [{}]
        ranges = list(ranges) + [(covered, len(segs))]

    new_comps = []
    for ci, (s0, s1) in enumerate(ranges):
        src = comps_src[ci] if ci < len(comps_src) else {}
        sub = []
        cur = []
        for si in range(s0, min(s1, len(segs))):
            first, last = seg_map[si]
            for k in range(first, last + 1):
                cur.append(new_segs[k])
                if k < last:
                    # Interior cut: end this component and start the next one.
                    sub.append(cur)
                    cur = []
        if cur:
            sub.append(cur)
        for seglist in sub:
            comp = dict(src)
            comp["segs"] = seglist
            # The old raw points describe the whole pre-cut curve; drop them so
            # redrawing a half cannot regenerate the other half.
            comp["raw_points"] = []
            new_comps.append(comp)
    out["components"] = new_comps
    try:
        out["obb"] = compute_stroke_obb(out)
    except Exception:
        pass
    return out


def _cubic_length(seg, samples=16):
    p0, c1, c2, p3 = seg
    prev = p0
    total = 0.0
    for k in range(1, samples + 1):
        pt = _cubic_point(p0, c1, c2, p3, k / float(samples))
        total += math.hypot(pt[0] - prev[0], pt[1] - prev[1])
        prev = pt
    return total


def _trim_piece_atoms(piece, gap_start, gap_end):
    """Keep the part of ``piece`` between the given arc-length trims."""
    if not piece:
        return None
    if gap_start <= 0.0 and gap_end <= 0.0:
        return piece
    lens = [_cubic_length(a["seg"]) for a in piece]
    total = sum(lens)
    if total <= (gap_start + gap_end) * 1.15:
        return None  # sliver: drop the whole piece

    def locate(dist):
        acc = 0.0
        for i, L in enumerate(lens):
            if acc + L >= dist:
                return i, clamp((dist - acc) / max(1e-9, L), 0.0, 1.0)
            acc += L
        return len(lens) - 1, 1.0

    si, sf = locate(gap_start) if gap_start > 0.0 else (0, 0.0)
    ei, ef = locate(total - gap_end) if gap_end > 0.0 else (len(lens) - 1, 1.0)
    if ei < si or (ei == si and ef - sf <= 1e-4):
        return None

    out = []
    for i in range(si, ei + 1):
        t0 = sf if i == si else 0.0
        t1 = ef if i == ei else 1.0
        if t1 - t0 <= 1e-6:
            continue
        atom = dict(piece[i])
        atom["seg"] = _sub_cubic(piece[i]["seg"], t0, t1)
        out.append(atom)
    return out or None


def _seg_cross_params(seg, a, b, samples=24):
    """Parameters along a cubic where it crosses the segment a-b."""
    p0, c1, c2, p3 = seg
    params = []
    prev = p0
    for k in range(1, samples + 1):
        pt = _cubic_point(p0, c1, c2, p3, k / float(samples))
        rx, ry = pt[0] - prev[0], pt[1] - prev[1]
        sx, sy = b[0] - a[0], b[1] - a[1]
        den = rx * sy - ry * sx
        if abs(den) > 1e-12:
            qx, qy = a[0] - prev[0], a[1] - prev[1]
            s = (qx * sy - qy * sx) / den   # along the cubic sub-segment
            u = (qx * ry - qy * rx) / den   # along the cutter segment
            if -1e-9 <= s <= 1.0 + 1e-9 and -1e-9 <= u <= 1.0 + 1e-9:
                params.append((k - 1 + clamp(s, 0.0, 1.0)) / float(samples))
        prev = pt
    return params


def _split_stroke_at_cuts(stroke, cuts, gap=0.0):
    """Split a stroke at {seg_index: [t, ...]}. Returns the piece strokes.

    ``t`` may be 0 or 1: a cut on a segment joint becomes a break there.
    ``gap`` is the material trimmed from *each* cut end (canvas px); 0 leaves
    the pieces sharing the exact intersection node."""
    segs = list(segs_of(stroke))
    ranges = _component_ranges(stroke)
    comps_src = _stroke_components(stroke)

    def comp_of(seg_i):
        for ci, (s0, s1) in enumerate(ranges):
            if s0 <= seg_i < s1:
                return ci
        return 0

    # Cuts landing on a joint break *before* the next segment.
    break_before = set()
    for si, ts in cuts.items():
        for t in ts:
            if t <= 1e-4:
                break_before.add(si)
            elif t >= 1.0 - 1e-4:
                break_before.add(si + 1)

    # Flatten the stroke into sub-segments ("atoms"), remembering the component
    # each atom belongs to.
    atoms = []
    for si, seg in enumerate(segs):
        ts = sorted(set([0.0] + list(cuts.get(si, ())) + [1.0]))
        for t0, t1 in zip(ts, ts[1:]):
            if t1 - t0 <= 1e-6:
                continue
            atoms.append({
                "seg": _sub_cubic(seg, t0, t1),
                "ci": comp_of(si),
                "si": si,
                "t0": t0,
                "t1": t1,
            })

    interior_cut = {(si, round(t, 9)) for si, ts in cuts.items()
                    for t in ts if 1e-4 < t < 1.0 - 1e-4}

    pieces = []
    current = []
    for atom in atoms:
        if current and atom["si"] in break_before:
            pieces.append(current)
            current = []
            break_before.discard(atom["si"])
        current.append(atom)
        if (atom["si"], round(atom["t1"], 9)) in interior_cut:
            pieces.append(current)
            current = []
    if current:
        pieces.append(current)
    if len(pieces) <= 1:
        return None

    is_dict = isinstance(stroke, dict)
    base_sc = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if is_dict else (0.1, 0.1, 0.15)
    base_sw = stroke.get("stroke_width", 3.0) if is_dict else 3.0
    fill = stroke.get("fill_color") if is_dict else None
    fill_grad = stroke.get("fill_gradient") if is_dict else None
    algo = stroke.get("algorithm", "fit") if is_dict else "fit"
    closed = (len(segs) > 1 and
              math.hypot(segs[0][0][0] - segs[-1][3][0],
                         segs[0][0][1] - segs[-1][3][1]) <= 1e-6)
    seam_cut = ((0 in cuts and any(t <= 1e-4 for t in cuts[0])) or
                ((len(segs) - 1) in cuts and
                 any(t >= 1.0 - 1e-4 for t in cuts[len(segs) - 1])))
    if closed and not seam_cut and len(pieces) > 1:
        # A closed loop is stored as an open polyline whose ends meet at the
        # seam; rejoin across it so a cut yields the expected arcs instead of
        # an extra split at the arbitrary seam point.
        pieces = [pieces[-1] + pieces[0]] + pieces[1:-1]
    gap = max(0.0, float(gap or 0.0))

    out = []
    for piece in pieces:
        first, last = piece[0], piece[-1]
        at_origin = (first["si"] == 0 and first["t0"] <= 1e-9)
        at_finish = (last["si"] == len(segs) - 1 and last["t1"] >= 1.0 - 1e-9)
        # "cut" ends get a visible gap; a "seam" is the stroke's original
        # closure point: it must not re-merge, but must not gain a gap either.
        start_kind = None if at_origin else "cut"
        end_kind = None if at_finish else "cut"
        if at_origin and closed:
            start_kind = "seam"
        if at_finish and closed:
            end_kind = "seam"

        trimmed = _trim_piece_atoms(
            piece,
            gap if start_kind == "cut" else 0.0,
            gap if end_kind == "cut" else 0.0,
        )
        if not trimmed:
            continue
        piece = trimmed
        piece_segs = [a["seg"] for a in piece]
        st = new_stroke(piece_segs, stroke_color=base_sc, stroke_width=base_sw,
                        fill_color=fill, algorithm=algo)
        if is_dict and fill_grad is not None:
            import copy as _copy
            st["fill_gradient"] = _copy.deepcopy(fill_grad)
        # Rebuild components so per-component styles (e.g. waves) survive.
        comps = []
        group_ci = None
        group = None
        for atom in piece:
            if group is None or atom["ci"] != group_ci:
                if group is not None:
                    comps.append(group)
                src = comps_src[atom["ci"]] if 0 <= atom["ci"] < len(comps_src) else {}
                group = dict(src)
                group["segs"] = []
                group["raw_points"] = []
                group_ci = atom["ci"]
            group["segs"].append(atom["seg"])
        if group is not None:
            comps.append(group)
        if comps:
            st["components"] = comps
        ends = {}
        if start_kind:
            ends["start"] = start_kind
        if end_kind:
            ends["end"] = end_kind
        if ends:
            st["cut_ends"] = ends
        out.append(st)
    return out or None


def cut_stroke_with_path(stroke, path, samples=24, gap=0.0):
    """Razor-cut one stroke along a canvas-space path.

    Returns a list of strokes, or ``None`` when the path misses. With ``gap`` 0
    the list holds the same connected stroke with nodes added at the crossings."""
    segs = list(segs_of(stroke))
    if not segs or len(path) < 2:
        return None
    hidden = set(stroke.get("hidden_segs") or ()) if isinstance(stroke, dict) else set()
    cuts = {}
    for si, seg in enumerate(segs):
        if si in hidden:
            continue
        params = []
        for a, b in zip(path, path[1:]):
            params.extend(_seg_cross_params(seg, a, b, samples=samples))
        params = sorted(clamp(p, 0.0, 1.0) for p in params)
        uniq = []
        for p in params:
            if not uniq or abs(p - uniq[-1]) > 1e-3:
                uniq.append(p)
        if uniq:
            cuts[si] = uniq
    if not cuts:
        return None
    if float(gap or 0.0) <= 0.0:
        # No gap: keep the stroke connected and just add anchors at the
        # crossings, so the object never breaks apart.
        inserted = _insert_cut_nodes(stroke, cuts)
        return [inserted] if inserted is not None else None
    return _split_stroke_at_cuts(stroke, cuts, gap=gap)


def cut_strokes_with_path(strokes, path, only_indices=None, gap=0.0):
    """Razor-cut strokes along a path.

    ``gap`` trims material from each cut end (canvas px); 0 inserts a node at
    each intersection and leaves the stroke connected.

    Returns ``(new_strokes, cut_indices)`` where ``cut_indices`` are the indices
    of the pieces created by the cut (useful for keeping them selected)."""
    out = []
    cut_indices = set()
    changed = False
    for i, stroke in enumerate(strokes):
        if only_indices is not None and i not in only_indices:
            out.append(stroke)
            continue
        pieces = cut_stroke_with_path(stroke, path, gap=gap)
        if pieces:
            start = len(out)
            out.extend(pieces)
            cut_indices.update(range(start, len(out)))
            changed = True
        else:
            out.append(stroke)
    return (out if changed else strokes), cut_indices


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

def hit_test_point(stroke, pos, radius=8.0, seg_indices=None, segs_override=None):
    segs = segs_override if segs_override is not None else segs_of(stroke)
    best = None
    best_d = radius
    names = ("p0", "c1", "c2", "p3")
    allowed = set(seg_indices) if seg_indices is not None else None
    for i, seg in enumerate(segs):
        if allowed is not None and i not in allowed:
            continue
        for j, name in enumerate(names):
            if name == "p0" and i > 0:
                # allow selecting p0 of first segment in range/component
                if allowed is None or i - 1 in allowed:
                    continue
            pt = seg[j]
            d = math.hypot(pos[0] - pt[0], pos[1] - pt[1])
            if d <= best_d:
                best_d = d
                best = (i, name)
    return best

def _selection_set(selected_indices):
    if selected_indices is None:
        return set()
    if isinstance(selected_indices, int):
        return {selected_indices}
    return set(selected_indices)

def combined_bbox(strokes, indices):
    """Axis-aligned bbox of visible curve/lines for the given strokes."""
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

def combined_obb(strokes, indices):
    """Bounding box of selected strokes: union of their stored shape frames."""
    obbs = []
    for i in indices:
        if 0 <= i < len(strokes):
            obb = stroke_obb(strokes[i])
            if obb is not None:
                obbs.append(obb)
    if not obbs:
        return None
    if len(obbs) == 1:
        o = obbs[0]
        # return a copy-like dict with corners ensured
        corners = o.get("corners")
        if not corners:
            cx, cy, hw, hh = o["cx"], o["cy"], o["hw"], o["hh"]
            ang = o.get("angle", 0.0)
            ca, sa = math.cos(ang), math.sin(ang)
            corners = [(cx + dx*ca - dy*sa, cy + dx*sa + dy*ca)
                       for dx, dy in [(-hw,-hh),(hw,-hh),(hw,hh),(-hw,hh)]]
        return {"cx": o["cx"], "cy": o["cy"], "hw": o["hw"], "hh": o["hh"],
                "angle": o.get("angle", 0.0), "corners": list(corners)}
    pts = []
    for o in obbs:
        corners = o.get("corners")
        if not corners:
            cx, cy, hw, hh = o["cx"], o["cy"], o["hw"], o["hh"]
            ang = o.get("angle", 0.0)
            ca, sa = math.cos(ang), math.sin(ang)
            corners = [(cx + dx*ca - dy*sa, cy + dx*sa + dy*ca)
                       for dx, dy in [(-hw,-hh),(hw,-hh),(hw,hh),(-hw,hh)]]
        pts.extend(corners)
    # Stable enclosing box of stored corners (no per-frame geometry resampling).
    return _min_area_obb(pts)
