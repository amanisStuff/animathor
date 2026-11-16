"""MVC Model: stroke/geometry data, wave math, hit testing and transforms.

Pure computation only - no pygame, cairo or tkinter dependencies."""

import math

from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

from config import *


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

WAVE_SHAPES = ["sine", "triangle", "square", "sawtooth", "circular", "half_circle", "formula", "custom", "sine_bezier", "noise"]

WAVE_SHAPE_LABELS = [("sine", "Sine"), ("triangle", "Tri"), ("square", "Sq"), ("sawtooth", "Saw"),
                     ("circular", "Circ"), ("half_circle", "Half"), ("formula", "Formula"),
                     ("custom", "Custom"), ("sine_bezier", "Sine Béz"), ("noise", "Noise")]

WAVE_SHAPE_LABEL_DICT = dict(WAVE_SHAPE_LABELS)

def default_wave_params():
    return {
        "type": "wave",
        "enabled": False,
        "shape": "sine",
        "amplitude": 8.0,
        "frequency": 0.25,
        "phase": 0.0,
        "noise": 0.0,
        "seed": 0,
        "noise_scale": 2.0,
        "reverse": False,
        "formula": "sin(x)",
        "custom_points": [],
    }

def _component_styles(component):
    if not isinstance(component, dict):
        return []
    styles = component.get("styles")
    if isinstance(styles, list):
        return list(styles)
    w = component.get("wave")
    if isinstance(w, dict):
        d = default_wave_params()
        d.update({k: w.get(k, d[k]) for k in d.keys() if k != "type"})
        d["type"] = "wave"
        return [d]
    return []

def _wave_style_raw_list(component):
    """Raw wave style dicts stored on a component, in stack order."""
    out = []
    for s0 in _component_styles(component):
        if isinstance(s0, dict) and s0.get("type") == "wave":
            out.append(s0)
    if not out and isinstance(component, dict) and isinstance(component.get("wave"), dict):
        out.append(component["wave"])
    return out

def _get_wave_styles(component):
    """All wave styles on a component (defaults merged), in stack order."""
    out = []
    for s0 in _wave_style_raw_list(component):
        d = default_wave_params()
        d.update({k: s0.get(k, d[k]) for k in d.keys() if k != "type"})
        d["type"] = "wave"
        out.append(d)
    return out

def _get_wave_style(component, index=0):
    styles = _get_wave_styles(component)
    if 0 <= index < len(styles):
        return styles[index]
    return default_wave_params()

def _set_wave_style(component, wave_style, index=0):
    if not isinstance(component, dict):
        return
    d = default_wave_params()
    if isinstance(wave_style, dict):
        d.update({k: wave_style.get(k, d[k]) for k in d.keys() if k != "type"})
    d["type"] = "wave"
    others = [dict(s0) for s0 in _component_styles(component) if not (isinstance(s0, dict) and s0.get("type") == "wave")]
    waves = [dict(s0) for s0 in _wave_style_raw_list(component)]
    while len(waves) <= index:
        waves.append(default_wave_params())
    waves[index] = d
    component["styles"] = others + waves
    # legacy single-wave key mirrors the first style for backward compatibility
    component["wave"] = {k: waves[0][k] for k in waves[0].keys() if k != "type"}

def _remove_wave_style(component, index=0):
    if not isinstance(component, dict):
        return
    others = [dict(s0) for s0 in _component_styles(component) if not (isinstance(s0, dict) and s0.get("type") == "wave")]
    waves = [dict(s0) for s0 in _wave_style_raw_list(component)]
    if waves:
        if 0 <= index < len(waves):
            del waves[index]
        else:
            waves.pop()
    component["styles"] = others + waves
    if waves:
        component["wave"] = {k: waves[0][k] for k in waves[0].keys() if k != "type"}
    else:
        component.pop("wave", None)

def _wave_params(component):
    return _get_wave_style(component)

def _wave_style_active(wv):
    """True when a single wave style actually contributes a visible offset."""
    try:
        return bool(wv.get("enabled")) and (
            abs(float(wv.get("amplitude", 0) or 0)) > 1e-6
            or abs(float(wv.get("noise", 0) or 0)) > 1e-6
        )
    except Exception:
        return False

def _component_wave_enabled(component):
    return any(_wave_style_active(wv) for wv in _get_wave_styles(component))

def _pseudo_noise01(i, seed=0):
    # deterministic hash-based noise in [0,1)
    x = (int(i) * 374761393 + int(seed) * 668265263 + 1442695041) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) * 1274126177 & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFFFF) / 4294967295.0

def _smooth_noise1d(x, seed=0, scale=2.0):
    try:
        scale = max(0.1, float(scale))
    except Exception:
        scale = 2.0
    p = float(x) * scale
    i0 = int(math.floor(p))
    i1 = i0 + 1
    f = p - i0
    # smoothstep
    t = f * f * (3.0 - 2.0 * f)
    n0 = _pseudo_noise01(i0, seed) * 2.0 - 1.0
    n1 = _pseudo_noise01(i1, seed) * 2.0 - 1.0
    return n0 + (n1 - n0) * t

def _latex_to_python_expr(expr):
    """Best-effort conversion of LaTeX-like math formulas to Python expressions."""
    import re
    if expr is None:
        return "sin(x)"
    s = str(expr).strip()
    if not s:
        return "sin(x)"
    # strip f(x)=
    s = re.sub(r'^\s*[A-Za-z]\s*\\left\s*\(.*?\\right\s*\)\s*=\s*', '', s)
    s = re.sub(r'^\s*[A-Za-z]\s*\(.*?\)\s*=\s*', '', s)
    s = re.sub(r'^\s*y\s*=\s*', '', s)
    s = s.replace(r'\left', '').replace(r'\right', '')
    s = s.replace(r'\cdot', '*').replace(r'\times', '*')
    s = s.replace(r'\pi', 'pi')
    s = re.sub(r'\^\{([^{}]*)\}', r'**(\1)', s)
    s = s.replace('^', '**')
    s = re.sub(r'\\operatorname\s*\{([^}]+)\}', r'\1', s)
    # functions - longer/more specific first
    for k,v in [(r'\arcsin','asin'),(r'\arccos','acos'),(r'\arctan','atan'),
                (r'\sin','sin'),(r'\cos','cos'),(r'\tan','tan'),
                (r'\sqrt','sqrt'),(r'\ln','log'),(r'\log','log10'),(r'\exp','exp'),(r'\abs','abs')]:
        s = s.replace(k,v)
    s = re.sub(r'\\([A-Za-z]+)', r'\1', s)
    s = s.replace('\\', '')

    def read_group(text, j):
        while j < len(text) and text[j].isspace(): j += 1
        if j < len(text) and text[j] == '{':
            depth=0; k=j
            while k<len(text):
                if text[k]=='{': depth+=1
                elif text[k]=='}':
                    depth-=1
                    if depth==0: return text[j+1:k], k+1
                k+=1
            return text[j+1:], len(text)
        elif j<len(text): return text[j], j+1
        return '', j

    for _ in range(20):
        i=0; out=[]; changed=False
        while i<len(s):
            if s.startswith('frac',i) and (i==0 or not (s[i-1].isalnum() or s[i-1]=='_')):
                i+=4; a,i=read_group(s,i); b,i=read_group(s,i)
                out.append('((' + a + ')/(' + b + '))'); changed=True
            else:
                out.append(s[i]); i+=1
        ns=''.join(out)
        if not changed: break
        s=ns

    funcs=['sqrt','sin','cos','tan','asin','acos','atan','abs','log','log10','exp','sign','floor','ceil','min','max']
    for fn in funcs:
        for _ in range(12):
            i=0; out=[]; changed=False
            while i<len(s):
                if s.startswith(fn+'{',i) and (i==0 or not (s[i-1].isalnum() or s[i-1]=='_')):
                    j=i+len(fn); a,j=read_group(s,j)
                    out.append(fn+'('+a+')'); i=j; changed=True
                else:
                    out.append(s[i]); i+=1
            ns=''.join(out)
            if not changed: break
            s=ns

    for _ in range(12):
        m=re.search(r'\|([^|]+)\|', s)
        if not m: break
        s=s[:m.start()]+'abs('+m.group(1)+')'+s[m.end():]
    s=s.replace('|','').replace('{','(').replace('}',')')
    func_pat=r'(?:'+'|'.join(sorted(funcs,key=len,reverse=True))+r')'
    s=re.sub(r'(\d)([A-Za-z_\(])', r'\1*\2', s)
    s=re.sub(r'(\))([A-Za-z0-9_\(])', r'\1*\2', s)
    s=re.sub(r'(\bpi\b)([A-Za-z0-9_\(])', r'\1*\2', s)
    s=re.sub(r'([A-Za-z0-9_\)])(\bpi\b)', r'\1*\2', s)
    # insert * before function calls, but avoid splitting identifiers like asin -> a*sin
    def _mult_before_func(m):
        pre = m.group(1)
        fn = m.group(2)
        # if pre ends with letter and pre+fn forms a known function name, skip
        if pre and pre[-1].isalpha():
            combo = pre[-1] + fn
            if combo in funcs:
                return m.group(0)
        return pre + '*' + fn
    s=re.sub(r'([A-Za-z0-9_\)])(' + func_pat + r')\b', _mult_before_func, s)
    s=re.sub(r'\b(\d)\s*([A-Za-z])\b', r'\1*\2', s)
    s=s.replace('pi x','pi*x').replace('npi','n*pi')
    s=re.sub(r'^[A-Za-z]\s*\([^)]*\)\s*=\s*', '', s)
    return s.strip() or "sin(x)"

def _generate_sine_deriv_template(amp, freq):
    """Generate wave key/control points for a sine shape using derivative analysis.

    For a sine wave with angular frequency (per template period) = period, the
    wave value is v(t) = amp * sin(period * t) over normalized phase t in [0, 1].
    The derivative is dv/dt = amp * period * cos(period * t).
    Key positions where the derivative is zero (extrema) or at 45-degree tangent
    angles become the control points; y values come from the sine function.

    Returns a sorted list of (t, y) key points forming one smooth template period.
    """
    freq = max(0.05, float(freq))
    period = 2.0 * math.pi * freq  # angular frequency per template period
    # derivative zeros: period * t = pi/2 + k*pi  ->  t = (pi/2 + k*pi) / period
    key_ts = [0.0]
    k = 0
    while True:
        p_ang = math.pi / 2.0 + k * math.pi
        if p_ang > period - 1e-9:
            break
        t_val = p_ang / period
        if t_val < 1.0 - 1e-9 and t_val > 0.0:
            key_ts.append(t_val)
        k += 1
    key_ts.append(1.0)
    # Build unique sorted key points with y = amp * sin(period * t)
    seen = []
    for t_val in sorted(key_ts):
        if any(abs(t_val - existing) < 1e-6 for existing in seen):
            continue
        seen.append(t_val)
    points = []
    for t_val in seen:
        y_val = amp * math.sin(period * t_val)
        points.append((float(t_val), float(y_val)))
    # ensure endpoints exist
    if points[0][0] > 0:
        points.insert(0, (0.0, 0.0))
    if points[-1][0] < 1.0:
        points.append((1.0, float(amp * math.sin(period))))
    return points

def _formula_env_for(w):
    """Build the sandboxed evaluation environment for a formula wave style."""
    allowed_base = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    allowed_base.update({"pi": math.pi, "tau": math.tau, "e": math.e,
                         "abs": abs, "min": min, "max": max, "pow": pow, "round": round,
                         "sign": lambda v: (1.0 if v > 0 else (-1.0 if v < 0 else 0.0)),
                         "r": max(1.0, float(w.get("amplitude", 8.0) or 8.0)),
                         "n": 0.0,
                         "a": float(w.get("amplitude", 8.0) or 8.0),
                         "f": float(w.get("frequency", 0.25) or 0.25),
                         "phi": float(w.get("phase", 0.0) or 0.0)})
    formula = str(w.get("formula", "sin(x)") or "sin(x)")
    try:
        expr = _latex_to_python_expr(formula)
    except Exception:
        expr = "sin(x)"
    return (expr, allowed_base)

def _prepare_wave_evaluator(w, geom=None):
    """Precompute everything needed to evaluate one wave style along a curve.

    `geom` is {"diag": bbox diagonal, "length": curve length} in canvas units
    (defaults to 1.0/1.0 for previews and icons). Frequency semantics:
    0.01..1.0 means the cycle length equals freq * bbox diagonal (1.0 = one
    cycle spans the diagonal); values above 1.0 keep the legacy meaning of
    "N cycles across the curve" so old saved files still render the same.
    Amplitude is relative to the shape: amp/100 * diagonal/2 canvas units."""
    shape = str(w.get("shape", "sine") or "sine").lower()
    ev = {
        "shape": shape,
        "amp": float(w.get("amplitude", 0.0) or 0.0),
        "freq": float(w.get("frequency", 0.0) or 0.0),
        "phase": float(w.get("phase", 0.0) or 0.0),
        "noise": float(w.get("noise", 0.0) or 0.0),
        "seed": int(w.get("seed", 0) or 0),
        "noise_scale": float(w.get("noise_scale", 2.0) or 2.0),
        "formula_env": None,
        "custom_points": None,
        "cycles": 0.0,
        "amp_px": 0.0,
        "noise_px": 0.0,
        "reverse": False,
    }
    ev["reverse"] = bool(w.get("reverse"))
    diag = 1.0
    length = 1.0
    if isinstance(geom, dict):
        try:
            diag = max(1e-6, float(geom.get("diag", 1.0) or 1.0))
        except Exception:
            diag = 1.0
        try:
            length = max(1e-6, float(geom.get("length", 1.0) or 1.0))
        except Exception:
            length = 1.0
    freq = ev["freq"]
    if freq <= 0.0:
        ev["cycles"] = 0.0
    elif freq > 1.0:
        # legacy saved files: frequency was "cycles across the curve"
        ev["cycles"] = freq
    else:
        ev["cycles"] = length / (freq * diag)
    # amplitude (and legacy per-wave noise amount) scale with the shape size
    ev["amp_px"] = ev["amp"] / 100.0 * diag * 0.5
    ev["noise_px"] = ev["noise"] / 100.0 * diag * 0.5
    if shape == "formula":
        ev["formula_env"] = _formula_env_for(w)
    if shape == "sine_bezier":
        # derivative-generated template; values stay in [-1,1] (amp scales later)
        periods = freq if freq > 1.0 else 1.0
        ev["custom_points"] = _generate_sine_deriv_template(1.0, periods)
        ev["shape"] = "custom"
    else:
        ev["custom_points"] = w.get("custom_points", None)
    return ev

def _custom_wave_at(f, cps):
    """Catmull-Rom/Hermite interpolation of custom wave points at phase f in [0,1].
    Tangents come from neighbouring control points (normalised by pi/4 to match
    ideal sine derivatives), so few-point sine templates stay smooth."""
    if not cps or len(cps) < 2:
        return 0.0
    cps = sorted(cps, key=lambda cp: (cp[0], cp[1]))
    npts = len(cps)
    seg_idx = -1
    for j in range(npts - 1):
        if cps[j][0] <= f <= cps[j + 1][0]:
            seg_idx = j
            break
    if seg_idx < 0:
        # f outside the point x-range: clamp to nearest endpoint value
        return cps[0][1] if f < cps[0][0] else cps[-1][1]
    x0, y0 = cps[seg_idx]
    x1, y1 = cps[seg_idx + 1]
    dx = x1 - x0
    if abs(dx) < 1e-9:
        return y0
    t = (f - x0) / dx
    # Catmull-Rom tangents from neighbouring points
    if seg_idx > 0:
        tan_left_x = x0 - cps[seg_idx - 1][0]
        tan_left_y = y0 - cps[seg_idx - 1][1]
    else:
        tan_left_x = dx
        tan_left_y = y1 - y0
    if seg_idx + 2 < npts:
        tan_right_x = cps[seg_idx + 2][0] - x1
        tan_right_y = cps[seg_idx + 2][1] - y1
    else:
        tan_right_x = dx
        tan_right_y = y1 - y0
    # normalised slopes (dy/dx), scaled to ideal sine derivatives
    norm_factor = math.pi / 4.0
    m0 = (tan_left_y / tan_left_x if abs(tan_left_x) > 1e-9 else 0.0) * norm_factor
    m1 = (tan_right_y / tan_right_x if abs(tan_right_x) > 1e-9 else 0.0) * norm_factor
    # cubic Hermite basis
    t2 = t * t
    t3 = t2 * t
    h00 = 2 * t3 - 3 * t2 + 1
    h10 = t3 - 2 * t2 + t
    h01 = -2 * t3 + 3 * t2
    h11 = t3 - t2
    return h00 * y0 + h10 * m0 * dx + h01 * y1 + h11 * m1 * dx

CUSTOM_WAVE_SAMPLES = 128

def _custom_uniform_samples(cps, n=None):
    """Resample any point set onto the fixed uniform sample grid (t in [0,1])."""
    if n is None:
        n = CUSTOM_WAVE_SAMPLES
    n = max(2, int(n))
    if cps and len(cps) >= 2:
        return [(i / (n - 1.0), _custom_wave_at(i / (n - 1.0), cps)) for i in range(n)]
    return [(i / (n - 1.0), 0.0) for i in range(n)]

def _custom_wave_paint(w, box, pos, drag):
    """Paint the waveform under the cursor (click-hold-drag inside the box).

    `drag` is [last_index, last_amplitude], or None when starting a stroke.
    Every sample between the previous and current column is filled so fast
    horizontal moves stay continuous, exactly like LMMS Bit Invader."""
    if not box or box.w <= 0 or box.h <= 0:
        return drag
    t = clamp((pos[0] - box.x) / max(1, box.w - 1), 0.0, 1.0)
    amp = clamp((pos[1] - (box.y + box.h / 2.0)) / max(1, box.h / 2.0), -1.0, 1.0)
    n = CUSTOM_WAVE_SAMPLES
    pts = w.get("custom_points")
    if not pts or len(pts) != n:
        # convert legacy sparse points (or empty) onto the uniform grid first
        pts = _custom_uniform_samples(pts)
        w["custom_points"] = pts
    idx = int(round(t * (n - 1)))
    if drag is None or len(drag) < 2:
        drag = [idx, amp]
    i0, i1 = min(drag[0], idx), max(drag[0], idx)
    for i in range(i0, i1 + 1):
        f = 0.0 if i1 == i0 else (i - i0) / (i1 - i0)
        pts[i] = (i / (n - 1.0), drag[1] + (amp - drag[1]) * f)
    return [idx, amp]

def _custom_smooth_samples(cps, passes=2, window=5):
    """Wrap-around moving average over the fixed sample grid (the wave loops,
    so smoothing wraps across the ends and stays seamless)."""
    pts = _custom_uniform_samples(cps)
    n = len(pts)
    vals = [a for _t, a in pts]
    half = max(1, window // 2)
    for _ in range(max(0, passes)):
        vals = [sum(vals[(i + j) % n] for j in range(-half, half + 1)) / (2 * half + 1)
                for i in range(n)]
    return [(i / (n - 1.0), v) for i, v in enumerate(vals)]

def _wave_value_for(ev, s):
    """Evaluate one prepared wave style at normalized arc position s in [0,1].
    With the reverse flag set, the result is inverted: -f(x)."""
    v = _wave_value_raw(ev, s)
    return -v if ev["reverse"] else v

def _wave_value_raw(ev, s):
    """Raw wave shape value in [-1,1] (direction inversion not applied)."""
    freq = ev["freq"]
    if freq == 0:
        return 0.0
    # phase slider is in degrees (0..360) and maps to a full cycle; the number
    # of cycles across the curve comes from the geometry (cycle length is
    # freq * bbox diagonal for the 0.01..1.0 range)
    p = (s * ev["cycles"] * math.tau) + math.radians(ev["phase"])
    shape = ev["shape"]
    if shape == "noise":
        # standalone noise distortion: smooth pseudo-random profile in [-1,1]
        # so amplitude scales it exactly like every other shape. Phase does not
        # apply to noise (grayed out in the panel).
        return _smooth_noise1d(s * ev["cycles"] * 4.0, seed=ev["seed"], scale=ev["noise_scale"])
    if shape == "formula" and ev["formula_env"] is not None:
        fstr, abase = ev["formula_env"]
        try:
            env = dict(abase)
            frac = (p / math.tau) - math.floor(p / math.tau)
            env.update({"x": p, "p": p, "t": frac, "s": s, "frac": frac})
            return float(eval(fstr, {"__builtins__": {}}, env))
        except Exception:
            return math.sin(p)
    cps = ev["custom_points"]
    if shape == "custom" and cps and len(cps) >= 2:
        frac = max(0.0, min(1.0, (p / math.tau) - math.floor(p / math.tau)))
        return _custom_wave_at(frac, cps)
    # built-in shapes
    tval = p / math.tau
    frac = tval - math.floor(tval)
    if shape == "triangle":
        return 4.0 * abs(frac - 0.5) - 1.0
    if shape == "square":
        return 1.0 if frac < 0.5 else -1.0
    if shape == "sawtooth":
        return 2.0 * frac - 1.0
    if shape == "circular":
        if frac < 0.5:
            q = 4.0 * frac - 1.0
            return math.sqrt(max(0.0, 1.0 - q * q))
        q = 4.0 * (frac - 0.5) - 1.0
        return -math.sqrt(max(0.0, 1.0 - q * q))
    if shape == "half_circle":
        q = 2.0 * frac - 1.0
        return math.sqrt(max(0.0, 1.0 - q * q))
    return math.sin(p)

def _wave_icon_polyline(wave, n=20):
    """One normalized cycle of a wave style, for drawing shape thumbnail icons."""
    w = dict(wave) if isinstance(wave, dict) else {}
    w["frequency"] = 1.0
    w["phase"] = 0.0
    w["noise"] = 0.0
    ev = _prepare_wave_evaluator(w)
    pts = []
    for i in range(n + 1):
        s = i / n
        pts.append((s, _wave_value_for(ev, s)))
    return pts

def _wave_preview_polyline(wave, n=None):
    """Composed wave (amplitude/frequency/phase/noise) over the whole stroke,
    normalized to roughly [-1,1] for the live preview box."""
    ev = _prepare_wave_evaluator(wave if isinstance(wave, dict) else {})
    if n is None:
        # enough points to render every cycle and noise lattice cell smoothly
        cycles = abs(ev["cycles"])
        n = int(min(2400, max(240, cycles * 24)))
        if ev["shape"] == "noise" or ev["noise"] != 0.0:
            # noise needs several samples per lattice cell to look smooth
            noise_cells = max(1.0, cycles) * 4.0 * max(0.1, ev["noise_scale"])
            n = int(min(2400, max(n, noise_cells * 6)))
    pts = []
    for i in range(n + 1):
        s = i / n
        total = ev["amp"] * _wave_value_for(ev, s)
        if ev["noise"] != 0.0:
            nz = _smooth_noise1d(s * ev["cycles"] * 4.0, seed=ev["seed"], scale=ev["noise_scale"])
            total += ev["noise"] * nz
        pts.append((s, total / 100.0))
    return pts

def sample_distorted_component(stroke, comp_index, samples_per_seg=24):
    """Return sampled polyline points for a component with wave distortion applied.
    Distortion is for rendering only; base geometry remains unchanged."""
    comps = _stroke_components(stroke)
    if not (0 <= comp_index < len(comps)):
        return []
    comp = comps[comp_index]
    # Always sample from current stroke base geometry so distortion follows edits/transforms/redraws.
    ranges = _component_ranges(stroke)
    segs = []
    if 0 <= comp_index < len(ranges):
        s0, s1 = ranges[comp_index]
        segs = list(segs_of(stroke)[s0:s1])
    if not segs:
        segs = list(comp.get("segs") or [])
    if not segs:
        return []
    waves = [wv for wv in _get_wave_styles(comp) if _wave_style_active(wv)]
    if not waves:
        # no visible distortion: return dense samples of base for consistency? caller can choose; but return base polyline
        pts = []
        for si, (p0, c1, c2, p3) in enumerate(segs):
            if si == 0:
                pts.append(p0)
            steps = max(2, int(samples_per_seg))
            for i in range(1, steps + 1):
                pts.append(cubic_bezier_point(p0, c1, c2, p3, i / steps))
        return pts
    # approximate arc-length parameter for stable waves across segments
    # precompute cumulative lengths
    seg_samples = max(4, int(samples_per_seg))
    lengths = []
    total = 0.0
    for (p0, c1, c2, p3) in segs:
        prev = p0
        l = 0.0
        for i in range(1, seg_samples + 1):
            pt = cubic_bezier_point(p0, c1, c2, p3, i / seg_samples)
            l += math.hypot(pt[0] - prev[0], pt[1] - prev[1])
            prev = pt
        lengths.append(l)
        total += l
    if total <= 1e-6:
        total = 1.0

    # bounding box diagonal: frequency/amplitude are relative to the shape size
    xs = []
    ys = []
    for (p0, c1, c2, p3) in segs:
        for pt in (p0, c1, c2, p3):
            xs.append(pt[0])
            ys.append(pt[1])
    diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if diag <= 1e-6:
        diag = total
    geom = {"diag": diag, "length": total}

    # prepare each stacked wave style once; offsets are summed per sample
    evaluators = [_prepare_wave_evaluator(wv, geom) for wv in waves]
    # Per-evaluator sample requirements: 32 samples per wave cycle, plus 8
    # samples per noise lattice cell (cells = cycles * 4 * smoothing scale) for
    # the standalone noise shape and any legacy per-wave noise. The hungriest
    # style in the stack dictates the sample density.
    SAMPLES_PER_CYCLE = 32
    SAMPLES_PER_NOISE_CELL = 8
    needed = 8
    for ev in evaluators:
        needed = max(needed, int(math.ceil(abs(ev["cycles"]) * SAMPLES_PER_CYCLE)) + 8)
        if ev["shape"] == "noise" or ev["noise"] != 0.0:
            noise_cells = max(1.0, abs(ev["cycles"])) * 4.0 * max(0.1, ev["noise_scale"])
            needed = max(needed, int(math.ceil(noise_cells * SAMPLES_PER_NOISE_CELL)) + 8)

    # Adaptive sampling density: the wave phase advances cycles*tau across the
    # whole component, so a fixed samples_per_seg aliases into jagged zigzags
    # at high frequency. 'needed' (computed above) covers both cycles and
    # noise lattice cells for every style in the stack.
    fixed_total = seg_samples * max(1, len(segs))
    needed_total = min(max(fixed_total, needed), 8192)
    steps_list = []
    for _l in lengths:
        frac = (_l / total) if total > 0 else (1.0 / max(1, len(lengths)))
        steps_list.append(max(4, int(round(needed_total * frac))))

    # sample base points and tangents along whole component for stable normals
    base_pts = []
    base_s = []
    cum = 0.0
    for si, (p0, c1, c2, p3) in enumerate(segs):
        seg_len = lengths[si] if si < len(lengths) else 0.0
        start_s = cum / total
        end_s = (cum + seg_len) / total if total > 0 else start_s
        steps = steps_list[si] if si < len(steps_list) else seg_samples
        for i in range(0 if si == 0 else 1, steps + 1):
            t = i / steps
            x, y = cubic_bezier_point(p0, c1, c2, p3, t)
            s = start_s + (end_s - start_s) * t
            base_pts.append((x, y))
            base_s.append(s)
        cum += seg_len
    if len(base_pts) < 2:
        return base_pts

    # compute normals from finite differences to avoid derivative singularities/flips
    normals = []
    n = len(base_pts)
    for i in range(n):
        if i == 0:
            dx = base_pts[1][0] - base_pts[0][0]
            dy = base_pts[1][1] - base_pts[0][1]
        elif i == n - 1:
            dx = base_pts[-1][0] - base_pts[-2][0]
            dy = base_pts[-1][1] - base_pts[-2][1]
        else:
            dx = base_pts[i + 1][0] - base_pts[i - 1][0]
            dy = base_pts[i + 1][1] - base_pts[i - 1][1]
        l = math.hypot(dx, dy)
        if l < 1e-6:
            # fallback to previous normal or arbitrary
            if normals:
                normals.append(normals[-1])
            else:
                normals.append((0.0, -1.0))
            continue
        normals.append((-dy / l, dx / l))

    # ensure normal consistency (avoid sudden flips)
    for i in range(1, len(normals)):
        px, py = normals[i - 1]
        nx, ny = normals[i]
        if px * nx + py * ny < 0:
            normals[i] = (-nx, -ny)


    out = []
    for i, (pt, s, nrmv) in enumerate(zip(base_pts, base_s, normals)):
        x, y = pt
        nx, ny = nrmv
        offset = 0.0
        for ev in evaluators:
            offset += ev["amp_px"] * _wave_value_for(ev, s)
            if ev["noise"] != 0.0:
                nz = _smooth_noise1d(s * ev["cycles"] * 4.0, seed=ev["seed"], scale=ev["noise_scale"])
                offset += ev["noise_px"] * nz
        out.append((x + nx * offset, y + ny * offset))

    # Keep distorted curve endpoints exactly on the base/guide curve endpoints
    if out and segs:
        out[0] = tuple(segs[0][0])
        out[-1] = tuple(segs[-1][3])
    return out

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

def _stroke_has_wave(stroke):
    for comp in _stroke_components(stroke):
        if _component_wave_enabled(comp):
            return True
    return False

def _component_distorted_polyline(stroke, comp_index, samples_per_seg=24):
    comps = _stroke_components(stroke)
    if not (0 <= comp_index < len(comps)):
        return []
    comp = comps[comp_index]
    if not _component_wave_enabled(comp):
        return []
    return sample_distorted_component(stroke, comp_index, samples_per_seg=samples_per_seg)

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
