"""Model: SVG import - parse SVG vector shapes into editable cubic paths.

Supports the path data commands (M/L/H/V/C/S/Q/T/A/Z, absolute and relative)
plus the basic shape elements (rect, circle, ellipse, line, polygon, polyline).
Fills/strokes, opacity and group transforms are carried across. The result is a
list of stroke dicts compatible with ``models.new_stroke``.
"""
import math
import re
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Colour parsing
# ---------------------------------------------------------------------------

_NAMED_COLORS = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
    "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "orange": (255, 165, 0), "purple": (128, 0, 128),
    "pink": (255, 192, 203), "brown": (165, 42, 42), "transparent": None,
}


def parse_color(value, default=None):
    """Parse a CSS colour string into an RGBA tuple (0..1)."""
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ("none", "transparent"):
        return None
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) == 6:
            try:
                r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
                return (r / 255.0, g / 255.0, b / 255.0, 1.0)
            except ValueError:
                return default
    m = re.match(r"rgb\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", s)
    if m:
        return (min(255.0, float(m.group(1))) / 255.0,
                min(255.0, float(m.group(2))) / 255.0,
                min(255.0, float(m.group(3))) / 255.0, 1.0)
    if s in _NAMED_COLORS:
        rgb = _NAMED_COLORS[s]
        return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0) if rgb else None
    return default


# ---------------------------------------------------------------------------
# Transform matrices: (a, b, c, d, e, f) maps (x, y) to (a x + c y + e, b x + d y + f)
# ---------------------------------------------------------------------------

def _identity():
    return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _mat_mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _apply(m, p):
    a, b, c, d, e, f = m
    x, y = p
    return (a * x + c * y + e, b * x + d * y + f)


def parse_transform(value):
    """Parse an SVG ``transform`` attribute into a 2D matrix."""
    m = _identity()
    if not value:
        return m
    for name, argstr in re.findall(r"(translate|scale|rotate|matrix|skewX|skewY)\s*\(([^)]*)\)",
                                   value, re.IGNORECASE):
        nums = [float(n) for n in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", argstr)]
        name = name.lower()
        if name == "matrix" and len(nums) >= 6:
            t = tuple(nums[:6])
        elif name == "translate" and len(nums) >= 1:
            t = (1.0, 0.0, 0.0, 1.0, nums[0], nums[1] if len(nums) > 1 else 0.0)
        elif name == "scale" and len(nums) >= 1:
            t = (nums[0], 0.0, 0.0, nums[1] if len(nums) > 1 else nums[0], 0.0, 0.0)
        elif name == "rotate" and len(nums) >= 1:
            ang = math.radians(nums[0])
            cos, sin = math.cos(ang), math.sin(ang)
            rot = (cos, sin, -sin, cos, 0.0, 0.0)
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                t = _mat_mul(_mat_mul((1, 0, 0, 1, cx, cy), rot), (1, 0, 0, 1, -cx, -cy))
            else:
                t = rot
        elif name == "skewx" and len(nums) >= 1:
            t = (1.0, 0.0, math.tan(math.radians(nums[0])), 1.0, 0.0, 0.0)
        elif name == "skewy" and len(nums) >= 1:
            t = (1.0, math.tan(math.radians(nums[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            continue
        m = _mat_mul(m, t)
    return m


# ---------------------------------------------------------------------------
# Path data parser
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_CMD_RE = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")


def parse_path_data(d):
    """Parse SVG path ``d`` into a list of subpaths.

    Each subpath is a dict ``{"segs": [...], "closed": bool}`` where segs are
    cubics ``(p0, c1, c2, p3)`` in user (viewBox) coordinates.
    """
    tokens = [t for t in re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|" + _NUM_RE.pattern, d or "")]
    i = 0
    subpaths = []
    cur = None
    start = (0.0, 0.0)
    last_ctrl = None
    prev_cmd = None

    def num():
        nonlocal i
        if i >= len(tokens):
            return 0.0
        val = float(tokens[i]); i += 1
        return val

    def line_to(p0, p1):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        return (p0, (p0[0] + dx / 3.0, p0[1] + dy / 3.0),
                (p0[0] + 2 * dx / 3.0, p0[1] + 2 * dy / 3.0), p1)

    def quad_to_cubic(p0, q, p1):
        return (p0, (p0[0] + 2.0 / 3.0 * (q[0] - p0[0]), p0[1] + 2.0 / 3.0 * (q[1] - p0[1])),
                (p1[0] + 2.0 / 3.0 * (q[0] - p1[0]), p1[1] + 2.0 / 3.0 * (q[1] - p1[1])), p1)

    def arc_to_cubics(p0, rx, ry, phi_deg, large, sweep, p1):
        # Standard SVG endpoint-to-centre arc conversion, then sample into cubics.
        if p0 == p1 or rx <= 0 or ry <= 0:
            return [line_to(p0, p1)]
        phi = math.radians(phi_deg)
        cos_phi, sin_phi = math.cos(phi), math.sin(phi)
        dx2, dy2 = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
        x1p = cos_phi * dx2 + sin_phi * dy2
        y1p = -sin_phi * dx2 + cos_phi * dy2
        rx, ry = abs(rx), abs(ry)
        lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
        if lam > 1.0:
            s = math.sqrt(lam); rx *= s; ry *= s
        num = max(0.0, rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p)
        den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
        coef = math.sqrt(num / den) if den > 0 else 0.0
        if large == sweep:
            coef = -coef
        cxp = coef * rx * y1p / ry
        cyp = coef * -ry * x1p / rx
        cx = cos_phi * cxp - sin_phi * cyp + (p0[0] + p1[0]) / 2.0
        cy = sin_phi * cxp + cos_phi * cyp + (p0[1] + p1[1]) / 2.0

        def angle(ux, uy, vx, vy):
            dot = ux * vx + uy * vy
            cr = ux * vy - uy * vx
            ang = math.acos(max(-1.0, min(1.0, dot / math.sqrt((ux * ux + uy * uy) * (vx * vx + vy * vy)))))
            return -ang if cr < 0 else ang

        ux = (x1p - cxp) / rx; uy = (y1p - cyp) / ry
        vx = (-x1p - cxp) / rx; vy = (-y1p - cyp) / ry
        theta1 = angle(1, 0, ux, uy)
        delta = angle(ux, uy, vx, vy)
        if not sweep and delta > 0:
            delta -= 2 * math.pi
        elif sweep and delta < 0:
            delta += 2 * math.pi
        n = max(1, int(math.ceil(abs(delta) / (math.pi / 2.0))))
        out = []
        for k in range(n):
            t1 = theta1 + delta * k / n
            t2 = theta1 + delta * (k + 1) / n
            et1, et2 = t1 + delta / n, t2 - delta / n
            def ep(t):
                return (cx + rx * math.cos(t) * cos_phi - ry * math.sin(t) * sin_phi,
                        cy + rx * math.cos(t) * sin_phi + ry * math.sin(t) * cos_phi)
            def deriv(t):
                return (-rx * math.sin(t) * cos_phi - ry * math.cos(t) * sin_phi,
                        -rx * math.sin(t) * sin_phi + ry * math.cos(t) * cos_phi)
            p0e, p3e = ep(t1), ep(t2)
            d1, d2 = deriv(et1), deriv(et2)
            kappa = 4.0 / 3.0 * math.tan((t2 - t1) / 4.0)
            out.append((p0e, (p0e[0] + kappa * d1[0], p0e[1] + kappa * d1[1]),
                        (p3e[0] - kappa * d2[0], p3e[1] - kappa * d2[1]), p3e))
        return out

    while i < len(tokens):
        tok = tokens[i]
        if _CMD_RE.fullmatch(tok):
            cmd = tok; i += 1
        else:
            cmd = prev_cmd
            if cmd is None:
                break
        if cmd in "Zz":
            if cur and cur["segs"]:
                cur["closed"] = True
                subpaths.append(cur)
            cur = None
            start = (start[0], start[1])
            last_ctrl = None
            prev_cmd = cmd
            continue
        relative = cmd.islower()
        cu = cmd.upper()
        cx, cy = start  # current point tracked via last segment endpoint below
        if cur and cur["segs"]:
            cx, cy = cur["segs"][-1][3]
        ox, oy = cx, cy

        if cu == "M":
            x, y = num(), num()
            p = (x + ox, y + oy) if relative else (x, y)
            # A new moveto ends any subpath still being built.
            if cur and cur["segs"]:
                subpaths.append(cur)
            cur = {"segs": [], "closed": False}
            start = p
            last_ctrl = None
            prev_cmd = "l" if relative else "L"
            continue
        if cur is None:
            cur = {"segs": [], "closed": False}
            start = (0.0, 0.0)

        if cu == "L":
            x, y = num(), num()
            p = (x + ox, y + oy) if relative else (x, y)
            cur["segs"].append(line_to((cx, cy), p)); last_ctrl = None
        elif cu == "H":
            x = num()
            p = (x + ox, cy) if relative else (x, cy)
            cur["segs"].append(line_to((cx, cy), p)); last_ctrl = None
        elif cu == "V":
            y = num()
            p = (cx, y + oy) if relative else (cx, y)
            cur["segs"].append(line_to((cx, cy), p)); last_ctrl = None
        elif cu in ("C", "S"):
            if cu == "C":
                x1, y1, x2, y2, x, y = num(), num(), num(), num(), num(), num()
                c1 = (x1 + ox, y1 + oy) if relative else (x1, y1)
                c2 = (x2 + ox, y2 + oy) if relative else (x2, y2)
            else:
                x2, y2, x, y = num(), num(), num(), num()
                c2 = (x2 + ox, y2 + oy) if relative else (x2, y2)
                if last_ctrl is not None:
                    c1 = (2 * cx - last_ctrl[0], 2 * cy - last_ctrl[1])
                else:
                    c1 = (cx, cy)
            p = (x + ox, y + oy) if relative else (x, y)
            cur["segs"].append(((cx, cy), c1, c2, p)); last_ctrl = c2
        elif cu in ("Q", "T"):
            if cu == "Q":
                qx, qy, x, y = num(), num(), num(), num()
                q = (qx + ox, qy + oy) if relative else (qx, qy)
            else:
                x, y = num(), num()
                if last_ctrl is not None:
                    q = (2 * cx - last_ctrl[0], 2 * cy - last_ctrl[1])
                else:
                    q = (cx, cy)
            p = (x + ox, y + oy) if relative else (x, y)
            cur["segs"].append(quad_to_cubic((cx, cy), q, p)); last_ctrl = q
        elif cu == "A":
            rx, ry, phi, large, sweep, x, y = (num() for _ in range(7))
            p = (x + ox, y + oy) if relative else (x, y)
            cur["segs"].extend(arc_to_cubics(
                (cx, cy), rx, ry, phi, bool(int(large)), bool(int(sweep)), p))
            last_ctrl = None
        else:
            i += 1
            continue
        prev_cmd = cmd

    if cur and cur["segs"]:
        if not cur["closed"] and math.hypot(cur["segs"][0][0][0] - cur["segs"][-1][3][0],
                                            cur["segs"][0][0][1] - cur["segs"][-1][3][1]) <= 1e-6:
            cur["closed"] = True
        subpaths.append(cur)
    return subpaths


# ---------------------------------------------------------------------------
# Element conversion
# ---------------------------------------------------------------------------

def _shape_subpaths(tag, attrs):
    """Return path subpaths for a basic SVG shape element."""
    def f(name, default=0.0):
        try:
            return float(attrs.get(name, default))
        except (TypeError, ValueError):
            return default

    if tag == "rect":
        x, y, w, h = f("x"), f("y"), f("width"), f("height")
        if w <= 0 or h <= 0:
            return []
        rx = min(f("rx", f("ry")), w / 2.0, h / 2.0)
        ry = min(f("ry", f("rx")), w / 2.0, h / 2.0)
        if rx <= 0 or ry <= 0:
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        else:
            k = 0.5522847498307936
            pts = [(x + rx, y), (x + w - rx, y), (x + w, y + ry),
                   (x + w, y + h - ry), (x + w - rx, y + h), (x + rx, y + h),
                   (x, y + h - ry), (x, y + ry)]
        segs = []
        for a, b in zip(pts, pts[1:] + pts[:1]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            segs.append((a, (a[0] + dx / 3, a[1] + dy / 3),
                         (a[0] + 2 * dx / 3, a[1] + 2 * dy / 3), b))
        return [{"segs": segs, "closed": True}]
    if tag in ("circle", "ellipse"):
        if tag == "circle":
            cx, cy, r = f("cx"), f("cy"), f("r")
            rx = ry = max(0.0, r)
        else:
            cx, cy, rx, ry = f("cx"), f("cy"), f("r"), f("ry")
            rx, ry = max(0.0, rx), max(0.0, ry)
        if rx <= 0 or ry <= 0:
            return []
        n = 8
        d = 4.0 / 3.0 * math.tan(math.pi / (2 * n))
        segs = []
        for k in range(n):
            t1, t2 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            c1, s1, c2, s2 = math.cos(t1), math.sin(t1), math.cos(t2), math.sin(t2)
            segs.append(((cx + rx * c1, cy + ry * s1),
                         (cx + rx * (c1 - d * s1), cy + ry * (s1 + d * c1)),
                         (cx + rx * (c2 + d * s2), cy + ry * (s2 - d * c2)),
                         (cx + rx * c2, cy + ry * s2)))
        return [{"segs": segs, "closed": True}]
    if tag == "line":
        a = (f("x1"), f("y1")); b = (f("x2"), f("y2"))
        dx, dy = b[0] - a[0], b[1] - a[1]
        return [{"segs": [(a, (a[0] + dx / 3, a[1] + dy / 3),
                           (a[0] + 2 * dx / 3, a[1] + 2 * dy / 3), b)], "closed": False}]
    if tag in ("polygon", "polyline"):
        nums = [float(n) for n in _NUM_RE.findall(attrs.get("points", ""))]
        pts = list(zip(nums[0::2], nums[1::2]))
        if len(pts) < 2:
            return []
        closed = tag == "polygon"
        ordered = pts + pts[:1] if closed else pts
        segs = []
        for a, b in zip(ordered, ordered[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            segs.append((a, (a[0] + dx / 3, a[1] + dy / 3),
                         (a[0] + 2 * dx / 3, a[1] + 2 * dy / 3), b))
        return [{"segs": segs, "closed": closed}]
    return []


def _viewbox_transform(root):
    """Return matrix mapping viewBox coordinates into width/height units."""
    vb = root.get("viewBox")
    if not vb:
        return _identity()
    nums = [float(n) for n in _NUM_RE.findall(vb)]
    if len(nums) < 4:
        return _identity()
    vx, vy, vw, vh = nums[:4]
    if vw <= 0 or vh <= 0:
        return _identity()
    try:
        w = float(root.get("width", vw)); h = float(root.get("height", vh))
    except (TypeError, ValueError):
        w, h = vw, vh
    if w <= 0 or h <= 0:
        w, h = vw, vh
    scale = min(w / vw, h / vh)
    tx = (w - vw * scale) / 2.0 - vx * scale
    ty = (h - vh * scale) / 2.0 - vy * scale
    return (scale, 0.0, 0.0, scale, tx, ty)


def import_svg_text(text):
    """Parse SVG source text into a list of editable stroke dicts."""
    root = ET.fromstring(text)
    base = _viewbox_transform(root)
    strokes = []

    def walk(node, parent_mat, inherited):
        tag = node.tag.split("}")[-1].lower()
        mat = _mat_mul(parent_mat, parse_transform(node.get("transform")))
        style = dict(inherited)
        for key in ("fill", "stroke", "stroke-width", "opacity", "fill-opacity",
                    "stroke-opacity", "stroke-linecap", "stroke-linejoin"):
            if node.get(key) is not None:
                style[key] = node.get(key)
        if node.get("style"):
            for part in node.get("style").split(";"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    style[k.strip()] = v.strip()

        if tag == "path":
            subs = parse_path_data(node.get("d", ""))
        elif tag in ("rect", "circle", "ellipse", "line", "polygon", "polyline"):
            subs = _shape_subpaths(tag, node.attrib)
        else:
            subs = []

        fill = parse_color(style.get("fill"), (0.1, 0.1, 0.15, 1.0))
        stroke_col = parse_color(style.get("stroke"), None)
        try:
            sw = float(str(style.get("stroke-width", 1.0)).replace("px", ""))
        except ValueError:
            sw = 1.0
        try:
            opacity = float(style.get("opacity", 1.0))
        except ValueError:
            opacity = 1.0
        cap = str(style.get("stroke-linecap", "round")).lower()
        join = str(style.get("stroke-linejoin", "round")).lower()
        if cap not in ("butt", "round", "square"):
            cap = "round"
        if join not in ("miter", "round", "bevel"):
            join = "round"

        for sub in subs:
            segs = [(tuple(_apply(mat, p0)), tuple(_apply(mat, c1)),
                     tuple(_apply(mat, c2)), tuple(_apply(mat, p3)))
                    for (p0, c1, c2, p3) in sub["segs"]]
            if not segs:
                continue
            corners = set()
            if sub["closed"]:
                corners.add((0, "p0")); corners.add((len(segs) - 1, "p3"))
            strokes.append({
                "segs": segs,
                "stroke_color": tuple(stroke_col[:3]) + (stroke_col[3] * opacity,) if stroke_col else None,
                "stroke_width": float(sw) if stroke_col else 0.0,
                "fill_color": tuple(fill[:3]) + (fill[3] * opacity,) if fill else None,
                "corner_anchors": corners, "hidden_segs": set(),
                "algorithm": "svg", "line_cap": cap, "line_join": join,
                "miter_limit": 10.0, "dash": None, "opacity": opacity,
            })

        for child in node:
            walk(child, mat, style)

    for child in root:
        walk(child, base, {})
    return strokes


def import_svg(path):
    """Read an SVG file from disk and return editable strokes."""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return import_svg_text(handle.read())
