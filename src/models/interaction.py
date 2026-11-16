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

def hit_test_point(stroke, pos, radius=8.0, seg_indices=None):
    segs = segs_of(stroke)
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
    """Oriented bbox of visible curve/lines (rotates with the shape)."""
    pts = []
    for i in indices:
        if 0 <= i < len(strokes):
            pts.extend(_stroke_outline_points(strokes[i]))
    return _min_area_obb(pts)
