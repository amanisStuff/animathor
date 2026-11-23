"""View: cairo canvas rendering and reference image handling."""

import math
import os

try:
    import cairo  # pycairo (often bundles Cairo on Windows)
    CAIRO_BACKEND = "pycairo"
except Exception:
    import cairocffi as cairo  # type: ignore
    CAIRO_BACKEND = "cairocffi"

import pygame

import config as cfg
from config import *
from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))


def make_cairo_surface(width, height):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    return surface


# Stroke styling. Defaults deliberately match the app's historical round cap,
# round join and solid line so existing documents look identical.
LINE_CAPS = {
    "butt": cairo.LINE_CAP_BUTT,
    "round": cairo.LINE_CAP_ROUND,
    "square": cairo.LINE_CAP_SQUARE,
}
LINE_JOINS = {
    "miter": cairo.LINE_JOIN_MITER,
    "round": cairo.LINE_JOIN_ROUND,
    "bevel": cairo.LINE_JOIN_BEVEL,
}
DASH_PRESETS = {
    "solid": None,
    "dashed": (12.0, 8.0),
    "dotted": (1.0, 6.0),
}


# Appearance: map our blend-mode names onto Cairo compositing operators.
# ``getattr`` keeps this portable across Cairo builds lacking the HSL operators.
def _cairo_op(name, default="OPERATOR_OVER"):
    return getattr(cairo, name, getattr(cairo, default))


BLEND_OPERATORS = {
    "normal": cairo.OPERATOR_OVER,
    "multiply": _cairo_op("OPERATOR_MULTIPLY"),
    "screen": _cairo_op("OPERATOR_SCREEN"),
    "overlay": _cairo_op("OPERATOR_OVERLAY"),
    "darken": _cairo_op("OPERATOR_DARKEN"),
    "lighten": _cairo_op("OPERATOR_LIGHTEN"),
    "color-dodge": _cairo_op("OPERATOR_COLOR_DODGE"),
    "color-burn": _cairo_op("OPERATOR_COLOR_BURN"),
    "hard-light": _cairo_op("OPERATOR_HARD_LIGHT"),
    "soft-light": _cairo_op("OPERATOR_SOFT_LIGHT"),
    "difference": _cairo_op("OPERATOR_DIFFERENCE"),
    "exclusion": _cairo_op("OPERATOR_EXCLUSION"),
    "hue": _cairo_op("OPERATOR_HSL_HUE"),
    "saturation": _cairo_op("OPERATOR_HSL_SATURATION"),
    "color": _cairo_op("OPERATOR_HSL_COLOR"),
    "luminosity": _cairo_op("OPERATOR_HSL_LUMINOSITY"),
}


def blend_operator(mode):
    """Return the Cairo operator for a blend-mode name (``normal`` fallback)."""
    return BLEND_OPERATORS.get(str(mode or "normal").lower(), cairo.OPERATOR_OVER)


def draw_drop_shadow(ctx, stroke, shadow, stroke_color, stroke_width, fill_spec):
    """Paint an approximate drop shadow for ``stroke`` in the current context.

    The shadow is a blurred-looking, offset, translucent copy of the shape's
    art (fill and/or stroke). Cairo has no native blur, so a small deterministic
    ring of samples around the offset approximates it without extra surfaces.
    """
    segs = segs_of(stroke)
    if not segs or not isinstance(shadow, dict):
        return
    r, g, b, a = shadow.get("color", (0.0, 0.0, 0.0, 1.0))
    base_alpha = float(a) * float(shadow.get("opacity", 0.4))
    if base_alpha <= 0.0:
        return
    blur = float(shadow.get("blur", 4.0))
    dx = float(shadow.get("dx", 4.0))
    dy = float(shadow.get("dy", 4.0))
    if blur <= 0.5:
        offsets = [(0.0, 0.0)]
    else:
        s = blur * 0.5
        d = s * 0.7
        offsets = [(0.0, 0.0), (-s, 0.0), (s, 0.0), (0.0, -s), (0.0, s),
                   (-d, -d), (d, -d), (-d, d), (d, d)]
    weight = base_alpha / len(offsets)
    has_fill = fill_spec is not None
    has_stroke = (stroke_width is not None and float(stroke_width) > 0.0
                  and color_alpha(stroke_color, 1.0) > 0.0)
    ctx.save()
    try:
        for ox, oy in offsets:
            ctx.save()
            ctx.translate(dx + ox, dy + oy)
            if draw_stroke_path(ctx, stroke):
                if has_fill:
                    ctx.set_source_rgba(r, g, b, weight)
                    ctx.fill()
                if has_stroke:
                    ctx.set_source_rgba(r, g, b, weight)
                    ctx.set_line_width(float(stroke_width))
                    apply_stroke_style(ctx, stroke, float(stroke_width))
                    ctx.stroke()
            ctx.restore()
    finally:
        ctx.restore()


def normalize_dash(dash):
    """Return a Cairo dash array, or None for a solid stroke."""
    if dash is None:
        return None
    if isinstance(dash, str):
        return DASH_PRESETS.get(dash.lower())
    if isinstance(dash, (list, tuple)):
        values = [float(v) for v in dash]
        if len(values) >= 2 and all(v >= 0 for v in values) and any(v > 0 for v in values):
            return values
    return None


def apply_stroke_style(ctx, stroke, width=3.0):
    """Apply cap/join/miter/dash from a stroke dict to a Cairo context."""
    if not isinstance(stroke, dict):
        return
    ctx.set_line_cap(LINE_CAPS.get(str(stroke.get("line_cap", "round")).lower(),
                                   cairo.LINE_CAP_ROUND))
    ctx.set_line_join(LINE_JOINS.get(str(stroke.get("line_join", "round")).lower(),
                                     cairo.LINE_JOIN_ROUND))
    try:
        ctx.set_miter_limit(max(1.0, float(stroke.get("miter_limit", 10.0))))
    except Exception:
        pass
    dash = normalize_dash(stroke.get("dash"))
    if dash:
        # Dash lengths are expressed in multiples of the stroke width, which
        # keeps the pattern visually consistent when the weight changes.
        scale = max(0.25, float(width or 3.0)) / 3.0
        ctx.set_dash([v * scale for v in dash])
    else:
        ctx.set_dash([])


def _draw_variable_width_segments(ctx, stroke, seg_indices, base_color=None):
    """Draw selected segments with variable width (e.g. per-point endpoint widths)."""
    segs = segs_of(stroke)
    if not seg_indices:
        return
    ordered = [i for i in sorted(seg_indices) if 0 <= i < len(segs)]
    if not ordered:
        return
    seg_cs = []
    w_start = []
    w_end = []
    for i in ordered:
        ci = _component_index_for_seg(stroke, i)
        sc, _sw = _effective_component_style(stroke, ci)
        ws, we = _segment_endpoint_widths(stroke, i)
        seg_cs.append(sc if base_color is None else base_color)
        w_start.append(max(0.5, float(ws)))
        w_end.append(max(0.5, float(we)))
    ctx.save()
    steps = 8
    for k, i in enumerate(ordered):
        p0, c1, c2, p3 = segs[i]
        ws, we = w_start[k], w_end[k]
        ctx.set_source_rgba(*color_rgba(seg_cs[k], DEFAULT_STROKE_RGBA))
        pts = []
        for s in range(steps + 1):
            t = s / steps
            x, y = cubic_bezier_point(p0, c1, c2, p3, t)
            dx, dy = cubic_bezier_derivative(p0, c1, c2, p3, t)
            l = math.hypot(dx, dy)
            if l < 1e-6:
                dx, dy = (p3[0] - p0[0], p3[1] - p0[1])
                l = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / l, dx / l
            w = ws + (we - ws) * t
            hw = w * 0.5
            pts.append((x + nx * hw, y + ny * hw, x - nx * hw, y - ny * hw))
        for s in range(steps):
            ax, ay, bx, by = pts[s][0], pts[s][1], pts[s][2], pts[s][3]
            cx, cy, dx_, dy_ = pts[s + 1][0], pts[s + 1][1], pts[s + 1][2], pts[s + 1][3]
            ctx.new_path()
            ctx.move_to(ax, ay); ctx.line_to(cx, cy); ctx.line_to(dx_, dy_); ctx.line_to(bx, by); ctx.close_path()
            ctx.fill()
        x0, y0 = cubic_bezier_point(p0, c1, c2, p3, 0.0)
        x1, y1 = cubic_bezier_point(p0, c1, c2, p3, 1.0)
        ctx.set_source_rgba(*color_rgba(seg_cs[k], DEFAULT_STROKE_RGBA))
        ctx.new_path(); ctx.arc(x0, y0, ws * 0.5, 0, 2 * math.pi); ctx.fill()
        ctx.new_path(); ctx.arc(x1, y1, we * 0.5, 0, 2 * math.pi); ctx.fill()
    ctx.restore()

def draw_stroke_path(ctx, stroke):
    if _stroke_has_wave(stroke):
        return draw_stroke_path_distorted(ctx, stroke)
    segs = segs_of(stroke)
    if not segs:
        return False
    hidden = set()
    if isinstance(stroke, dict):
        hidden = set(stroke.get("hidden_segs", set()) or set())
    visible = [i for i in range(len(segs)) if i not in hidden]
    if not visible:
        return False
    ctx.new_path()
    drew = False
    for i in range(len(segs)):
        if i in hidden:
            continue
        p0, c1, c2, p3 = segs[i]
        if not drew or not _pts_close(segs[i][0], segs[i - 1][3], 1e-3):
            ctx.move_to(p0[0], p0[1])
        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
        drew = True
    # if closed and fully visible, close path for nicer fill
    if len(visible) == len(segs) and _pts_close(segs[0][0], segs[-1][3], 6.0):
        ctx.close_path()
    return True

def draw_stroke_path_distorted(ctx, stroke):
    segs = segs_of(stroke)
    if not segs:
        return False
    hidden = set()
    if isinstance(stroke, dict):
        hidden = set(stroke.get("hidden_segs", set()) or set())
    visible = [i for i in range(len(segs)) if i not in hidden]
    if not visible:
        return False
    comps = _stroke_components(stroke)
    ranges = _component_ranges(stroke)
    ctx.new_path()
    drew_any = False
    for ci, (s0, s1) in enumerate(ranges):
        comp_visible = [i for i in range(s0, min(s1, len(segs))) if i not in hidden]
        if not comp_visible:
            continue
        poly = _component_distorted_polyline(stroke, ci)
        if poly and len(poly) >= 2 and _component_wave_enabled(comps[ci] if ci < len(comps) else {}):
            # draw distorted polyline for whole component if fully/mostly visible; if partial hidden, fall back per-seg
            if len(comp_visible) == (min(s1, len(segs)) - s0):
                if not drew_any or not _pts_close(poly[0], segs[s0][0], 1e-3):
                    ctx.move_to(poly[0][0], poly[0][1])
                else:
                    ctx.line_to(poly[0][0], poly[0][1])
                for pt in poly[1:]:
                    ctx.line_to(pt[0], pt[1])
                drew_any = True
                continue
            # partial hidden: sample base segs for visible ones with distortion per seg
            for i in comp_visible:
                p0, c1, c2, p3 = segs[i]
                steps = 20
                pts = [cubic_bezier_point(p0, c1, c2, p3, t / steps) for t in range(steps + 1)]
                # approximate local distortion by sampling component and mapping? easier: draw base for hidden-partial case
                if not drew_any or not _pts_close(pts[0], segs[i - 1][3] if i > 0 else pts[0], 1e-3):
                    ctx.move_to(pts[0][0], pts[0][1])
                for pt in pts[1:]:
                    ctx.line_to(pt[0], pt[1])
                drew_any = True
            continue
        # base draw for this component range
        for i in comp_visible:
            p0, c1, c2, p3 = segs[i]
            if not drew_any or not _pts_close(segs[i][0], segs[i - 1][3] if i > 0 else segs[i][0], 1e-3):
                ctx.move_to(p0[0], p0[1])
            ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
            drew_any = True
    if not drew_any:
        return False
    if len(visible) == len(segs) and _pts_close(segs[0][0], segs[-1][3], 6.0):
        ctx.close_path()
    return True


_GRADIENT_TYPES = ("linear", "radial", "conic", "spiral", "diamond", "square", "mesh")


def _is_fill_gradient(fill):
    return isinstance(fill, dict) and fill.get("type") in _GRADIENT_TYPES


_PATTERN_TYPES = ("stripes", "dots", "checks", "grid", "zigzag")


def _is_fill_pattern(fill):
    return isinstance(fill, dict) and fill.get("type") in _PATTERN_TYPES


def _make_pattern_pattern(stroke, pat):
    """Build a repeating Cairo surface pattern for a ``fill_pattern`` dict.

    The tile is drawn in device-independent pixels and anchored to the shape's
    bounding box so moving artwork moves the pattern with it.
    """
    if not _is_fill_pattern(pat):
        return None
    try:
        import cairo as _c
        bbox = _gradient_bbox(stroke)
        x0, y0 = (bbox[0], bbox[1]) if bbox else (0.0, 0.0)
        size = max(2.0, float(pat.get("size", 14.0) or 14.0))
        w = h = int(round(size))
        if w < 2 or h < 2:
            return None
        tile = _c.ImageSurface(_c.FORMAT_ARGB32, w, h)
        tctx = _c.Context(tile)
        fg = pat.get("fg") or (0.2, 0.3, 0.5, 1.0)
        bg = pat.get("bg")
        if bg:
            tctx.set_source_rgba(*[float(c) for c in bg[:4]])
            tctx.paint()
        else:
            tctx.set_source_rgba(*cairo_rgb((0, 0, 0), 0.0))
            tctx.paint()
        tctx.set_source_rgba(*[float(c) for c in fg[:4]])
        ptype = pat.get("type")
        lw = max(1.0, size * 0.16)
        if ptype == "stripes":
            tctx.set_line_width(lw)
            tctx.move_to(-w, 0); tctx.line_to(0, -h)
            tctx.move_to(0, h); tctx.line_to(w, 0)
            tctx.move_to(-w, h); tctx.line_to(w, -h)
            tctx.stroke()
        elif ptype == "dots":
            tctx.arc(w / 2.0, h / 2.0, max(1.0, size * 0.18), 0, 6.283185)
            tctx.fill()
        elif ptype == "checks":
            tctx.rectangle(0, 0, w / 2.0, h / 2.0)
            tctx.rectangle(w / 2.0, h / 2.0, w / 2.0, h / 2.0)
            tctx.fill()
        elif ptype == "grid":
            tctx.set_line_width(lw)
            tctx.move_to(0, 0); tctx.line_to(w, 0)
            tctx.move_to(0, 0); tctx.line_to(0, h)
            tctx.stroke()
        elif ptype == "zigzag":
            tctx.set_line_width(lw)
            tctx.move_to(0, h)
            tctx.line_to(w / 2.0, 0)
            tctx.line_to(w, h)
            tctx.stroke()
        pattern = _c.SurfacePattern(tile)
        pattern.set_extend(_c.EXTEND_REPEAT)
        try:
            angle = float(pat.get("angle", 0.0) or 0.0)
        except (TypeError, ValueError):
            angle = 0.0
        m = _c.Matrix()
        m.translate(x0, y0)
        if angle:
            m.rotate(angle)
        pattern.set_matrix(m)
        return pattern
    except Exception:
        return None


def _gradient_bbox(stroke):
    try:
        pts = []
        for seg in (stroke.get("segs") or []):
            if not seg or len(seg) < 4:
                continue
            p0, p1, p2, p3 = seg[0], seg[1], seg[2], seg[3]
            for p in (p0, p1, p2, p3):
                if p is not None:
                    pts.append((float(p[0]), float(p[1])))
            for t in (0.25, 0.5, 0.75):
                mt = 1.0 - t
                x = mt*mt*mt*p0[0] + 3*mt*mt*t*p1[0] + 3*mt*t*t*p2[0] + t*t*t*p3[0]
                y = mt*mt*mt*p0[1] + 3*mt*mt*t*p1[1] + 3*mt*t*t*p2[1] + t*t*t*p3[1]
                pts.append((float(x), float(y)))
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            if x1 - x0 < 1e-3:
                x1 = x0 + 1.0
            if y1 - y0 < 1e-3:
                y1 = y0 + 1.0
            return (x0, y0, x1, y1)
    except Exception:
        pass
    return (0.0, 0.0, 1.0, 1.0)


def _normalize_gradient_stops(stops):
    norm_stops = []
    for st in (stops or []):
        if isinstance(st, dict):
            pos = st.get("pos", 0.0)
            col = st.get("color", [0, 0, 0, 1])
        else:
            try:
                pos = float(st[0])
                col = st[1]
            except Exception:
                continue
        try:
            pos = float(pos)
        except Exception:
            pos = 0.0
        pos = 0.0 if pos < 0.0 else (1.0 if pos > 1.0 else pos)
        if col is None:
            rgba = (0.0, 0.0, 0.0, 1.0)
        else:
            try:
                r = float(col[0]); g = float(col[1]); b = float(col[2])
                a = float(col[3]) if len(col) >= 4 else 1.0
            except Exception:
                rgba = (0.0, 0.0, 0.0, 1.0)
            else:
                rgba = (r, g, b, a)
        norm_stops.append((pos, rgba))
    norm_stops.sort(key=lambda t: t[0])
    if not norm_stops:
        norm_stops = [(0.0, (0.0, 0.0, 0.0, 1.0)), (1.0, (1.0, 1.0, 1.0, 1.0))]
    if len(norm_stops) == 1:
        norm_stops = [(0.0, norm_stops[0][1]), (1.0, norm_stops[0][1])]
    return norm_stops


def _sample_gradient_stops_array(t, norm_stops):
    """Sample sorted gradient stops at t (numpy array in [0,1]) -> (r,g,b,a) float arrays."""
    try:
        import numpy as np
    except Exception:
        return None
    t = np.clip(np.asarray(t, dtype=np.float32), 0.0, 1.0)
    pos = np.array([s[0] for s in norm_stops], dtype=np.float32)
    cols = np.array([s[1] for s in norm_stops], dtype=np.float32)  # (N,4)
    # indices of right stop for each t
    idx = np.searchsorted(pos, t, side='right')
    idx0 = np.clip(idx - 1, 0, len(pos) - 1)
    idx1 = np.clip(idx, 0, len(pos) - 1)
    p0 = pos[idx0]
    p1 = pos[idx1]
    denom = p1 - p0
    # avoid divide by zero (equal positions)
    lt = np.where(denom > 1e-6, (t - p0) / denom, 0.0).astype(np.float32)
    lt = np.clip(lt, 0.0, 1.0)
    c0 = cols[idx0]
    c1 = cols[idx1]
    lt4 = lt[..., None]
    out = c0 + (c1 - c0) * lt4
    return out  # (H,W,4) floats 0..1


def _make_shaped_gradient_pattern(stroke, grad, gtype, norm_stops):
    try:
        import numpy as np
    except Exception:
        return None
    x0, y0, x1, y1 = _gradient_bbox(stroke)
    w = max(1e-3, x1 - x0)
    h = max(1e-3, y1 - y0)
    # raster size: reasonable cap for performance
    max_dim = 512
    scale = min(1.0, max_dim / max(w, h))
    pw = max(2, int(math.ceil(w * scale)))
    ph = max(2, int(math.ceil(h * scale)))

    c = grad.get("center", [0.5, 0.5])
    try:
        rcx = float(c[0]); rcy = float(c[1])
    except Exception:
        rcx, rcy = 0.5, 0.5
    rcx = max(0.0, min(1.0, rcx)); rcy = max(0.0, min(1.0, rcy))
    radii = grad.get("radii", [0.5, 0.5])
    try:
        rx = float(radii[0]); ry = float(radii[1])
    except Exception:
        rx, ry = 0.5, 0.5
    rx = max(0.01, abs(rx)); ry = max(0.01, abs(ry))
    try:
        ang_deg = float(grad.get("angle", 0.0) or 0.0)
    except Exception:
        ang_deg = 0.0
    ang = math.radians(ang_deg)
    caa, saa = math.cos(ang), math.sin(ang)

    # pixel centers in bbox-local coords
    xs = (np.arange(pw, dtype=np.float32) + 0.5) * (w / pw)
    ys = (np.arange(ph, dtype=np.float32) + 0.5) * (h / ph)
    xx, yy = np.meshgrid(xs, ys)
    dx = xx - (rcx * w)
    dy = yy - (rcy * h)
    # rotate into gradient's local space (inverse rotation of shape)
    lx = (dx * caa + dy * saa) / max(1e-6, rx * w)
    ly = (-dx * saa + dy * caa) / max(1e-6, ry * h)

    if gtype == "radial":
        t = np.sqrt(lx * lx + ly * ly)
    elif gtype == "conic":
        # sweep angle; 0 along local +X axis
        theta = np.arctan2(ly, lx)
        t = (theta / (2.0 * math.pi)) + 0.5
        t = t - np.floor(t)
    elif gtype == "spiral":
        try:
            turns = float(grad.get("turns", 2.0) or 2.0)
        except Exception:
            turns = 2.0
        if not (turns > 0.01):
            turns = 2.0
        theta = np.arctan2(ly, lx)
        ang_t = (theta / (2.0 * math.pi)) + 0.5
        r_t = np.sqrt(lx * lx + ly * ly)
        t = ang_t + r_t * turns
        t = t - np.floor(t)
    elif gtype == "diamond":
        t = np.abs(lx) + np.abs(ly)
    elif gtype == "square":
        t = np.maximum(np.abs(lx), np.abs(ly))
    else:
        t = np.sqrt(lx * lx + ly * ly)

    t = np.clip(t, 0.0, 1.0)
    rgba = _sample_gradient_stops_array(t, norm_stops)
    if rgba is None:
        return None
    rgba = np.clip(rgba, 0.0, 1.0)
    # Cairo ARGB32 premultiplied, native-endian (BGRA byte order on little-endian)
    a = rgba[..., 3:4]
    rgb = rgba[..., :3] * a
    out = np.empty((ph, pw, 4), dtype=np.uint8)
    out[..., 0] = (rgb[..., 2] * 255.0 + 0.5).astype(np.uint8)  # B
    out[..., 1] = (rgb[..., 1] * 255.0 + 0.5).astype(np.uint8)  # G
    out[..., 2] = (rgb[..., 0] * 255.0 + 0.5).astype(np.uint8)  # R
    out[..., 3] = (a[..., 0] * 255.0 + 0.5).astype(np.uint8)    # A
    out = np.ascontiguousarray(out)
    try:
        surf = cairo.ImageSurface.create_for_data(out, cairo.FORMAT_ARGB32, pw, ph, pw * 4)
    except Exception:
        return None
    pat = cairo.SurfacePattern(surf)
    try:
        pat.set_filter(cairo.FILTER_BILINEAR)
    except Exception:
        pass
    try:
        m = cairo.Matrix()
        m.scale(w / pw, h / ph)
        m.translate(x0 / (w / pw), y0 / (h / ph))
        m.invert()
        pat.set_matrix(m)
    except Exception:
        pass
    # keep numpy buffer alive as long as pattern/surface uses it
    try:
        pat._np_buf = out
        surf._np_buf = out
    except Exception:
        pass
    return pat


def _make_gradient_pattern(stroke, grad):
    if not isinstance(grad, dict):
        return None
    gtype = str(grad.get("type", "linear"))
    x0, y0, x1, y1 = _gradient_bbox(stroke)
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    w = max(1e-3, x1 - x0)
    h = max(1e-3, y1 - y0)
    try:
        if gtype == "mesh":
            grid = grad.get("grid") or []
            try:
                rows = max(1, int(grad.get("rows", max(1, len(grid) - 1)) or 1))
                cols = max(1, int(grad.get("cols", max(1, len((grid[0] if grid else []) or []) - 1)) or 1))
            except Exception:
                rows, cols = 1, 1
            if not isinstance(grid, list) or len(grid) < rows + 1:
                return None
            pat = cairo.MeshPattern()
            for r in range(rows):
                row0 = grid[r] if isinstance(grid[r], list) else []
                row1 = grid[r + 1] if r + 1 < len(grid) and isinstance(grid[r + 1], list) else []
                for c in range(cols):
                    def _pt(rr, cc):
                        u = cc / cols
                        v = rr / rows
                        return (x0 + u * w, y0 + v * h)
                    def _col(rr, cc, fallback=(1.0, 1.0, 1.0, 1.0)):
                        src = grid[rr] if rr < len(grid) and isinstance(grid[rr], list) else []
                        val = src[cc] if cc < len(src) else None
                        return color_rgba(val, fallback)
                    p00 = _pt(r, c); p10 = _pt(r, c + 1); p11 = _pt(r + 1, c + 1); p01 = _pt(r + 1, c)
                    c00 = _col(r, c); c10 = _col(r, c + 1); c11 = _col(r + 1, c + 1); c01 = _col(r + 1, c)
                    pat.begin_patch()
                    pat.move_to(p00[0], p00[1])
                    pat.line_to(p10[0], p10[1])
                    pat.line_to(p11[0], p11[1])
                    pat.line_to(p01[0], p01[1])
                    pat.set_corner_color_rgba(0, *c00)
                    pat.set_corner_color_rgba(1, *c10)
                    pat.set_corner_color_rgba(2, *c11)
                    pat.set_corner_color_rgba(3, *c01)
                    pat.end_patch()
            return pat

        stops = grad.get("stops") or []
        if len(stops) < 2:
            return None
        norm_stops = _normalize_gradient_stops(stops)
        if gtype == "linear":
            angle = float(grad.get("angle", 0.0) or 0.0) * math.pi / 180.0
            dx = math.cos(angle) * w * 0.5
            dy = math.sin(angle) * h * 0.5
            pat = cairo.LinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
            for pos, rgba in norm_stops:
                pat.add_color_stop_rgba(pos, *rgba)
            return pat
        elif gtype == "radial":
            # Radial gradient with adjustable center, elliptical radii, and rotation.
            c = grad.get("center", [0.5, 0.5])
            try:
                rcx = float(c[0]); rcy = float(c[1])
            except Exception:
                rcx, rcy = 0.5, 0.5
            rcx = max(0.0, min(1.0, rcx))
            rcy = max(0.0, min(1.0, rcy))
            radii = grad.get("radii", [0.5, 0.5])
            try:
                rx = float(radii[0]); ry = float(radii[1])
            except Exception:
                rx, ry = 0.5, 0.5
            rx = max(0.01, abs(rx))
            ry = max(0.01, abs(ry))
            try:
                ang_deg = float(grad.get("angle", 0.0) or 0.0)
            except Exception:
                ang_deg = 0.0
            ang = math.radians(ang_deg)
            gcx = x0 + rcx * w
            gcy = y0 + rcy * h
            # Define gradient in unit space and map to rotated/scaled ellipse.
            pat = cairo.RadialGradient(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
            for pos, rgba in norm_stops:
                pat.add_color_stop_rgba(pos, *rgba)
            try:
                m = cairo.Matrix()
                # pattern space -> user space: scale to radii, rotate, translate to center
                m.translate(gcx, gcy)
                m.rotate(ang)
                m.scale(max(1e-6, w * rx), max(1e-6, h * ry))
                m.invert()
                pat.set_matrix(m)
            except Exception:
                r = 0.5 * math.hypot(w, h)
                pat = cairo.RadialGradient(cx, cy, 0.0, cx, cy, r)
                for pos, rgba in norm_stops:
                    pat.add_color_stop_rgba(pos, *rgba)
            return pat
        elif gtype in ("conic", "spiral", "diamond", "square"):
            return _make_shaped_gradient_pattern(stroke, grad, gtype, norm_stops)
        else:
            # unknown -> try linear fallback
            angle = float(grad.get("angle", 0.0) or 0.0) * math.pi / 180.0
            dx = math.cos(angle) * w * 0.5
            dy = math.sin(angle) * h * 0.5
            pat = cairo.LinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
            for pos, rgba in norm_stops:
                pat.add_color_stop_rgba(pos, *rgba)
            return pat
    except Exception:
        return None


def _apply_fill_source(ctx, stroke, fill):
    if fill is None:
        return False
    if _is_fill_pattern(fill):
        pat = _make_pattern_pattern(stroke, fill)
        if pat is None:
            return False
        try:
            ctx.set_source(pat)
            return True
        except Exception:
            return False
    if _is_fill_gradient(fill):
        pat = _make_gradient_pattern(stroke, fill)
        if pat is None:
            return False
        try:
            ctx.set_source(pat)
            return True
        except Exception:
            return False
    try:
        ctx.set_source_rgba(*color_rgba(fill, DEFAULT_FILL_RGBA))
        return True
    except Exception:
        return False


def _draw_hidden_segments(ctx, stroke, segs, hidden_set, stroke_width):

    if not hidden_set:

        return

    ctx.save()

    try:

        ctx.set_dash([6, 4])

    except Exception:

        pass

    # distinct style for hidden curves in edit modes

    ctx.set_source_rgba(*EDITOR_ACCENT, 0.55)

    ctx.set_line_width(max(1.5, float(stroke_width)))

    ctx.new_path()

    for i in sorted(hidden_set):

        if 0 <= i < len(segs):

            p0, c1, c2, p3 = segs[i]

            ctx.move_to(p0[0], p0[1])

            ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])

    ctx.stroke()

    try:

        ctx.set_dash([])

    except Exception:

        pass

    ctx.restore()



def _draw_arrowhead(ctx, segs, color, width):

    """Draw an arrowhead at the end of the last segment (line shapes)."""

    if not segs:

        return

    try:

        p2, p3 = segs[-1][2], segs[-1][3]

    except Exception:

        return

    dx, dy = p3[0] - p2[0], p3[1] - p2[1]

    length = math.hypot(dx, dy)

    if length < 1e-6:

        try:

            p2, p3 = segs[-1][0], segs[-1][3]

            dx, dy = p3[0] - p2[0], p3[1] - p2[1]

            length = math.hypot(dx, dy)

        except Exception:

            return

    if length < 1e-6:

        return

    ux, uy = dx / length, dy / length

    size = max(9.0, float(width or 3.0) * 3.5)

    ang = math.radians(26.0)

    ca, sa = math.cos(ang), math.sin(ang)

    ctx.new_path()

    for sign in (-1.0, 1.0):

        rx = -ux * ca + uy * sa * sign

        ry = -ux * sa * sign - uy * ca

        ctx.move_to(p3[0], p3[1])

        ctx.line_to(p3[0] + rx * size, p3[1] + ry * size)

    ctx.set_source_rgba(*color_rgba(color, DEFAULT_STROKE_RGBA))

    ctx.set_line_width(max(1.0, float(width or 3.0)))

    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    ctx.stroke()





def _draw_marker(ctx, mtype, point, ux, uy, color, width):

    """Draw one end marker of type ``mtype`` at ``point`` pointing along u."""

    if mtype == "none":

        return

    px, py = point

    perp = (-uy, ux)

    size = marker_size({"stroke_width": width}, width)

    rgba = color_rgba(color, DEFAULT_STROKE_RGBA)

    lw = max(1.0, float(width or 3.0))

    ctx.new_path()

    if mtype in ("arrow", "open_arrow"):

        ang = math.radians(20.0 if mtype == "open_arrow" else 26.0)

        ca, sa = math.cos(ang), math.sin(ang)

        scale = 0.8 if mtype == "open_arrow" else 1.0

        for sign in (-1.0, 1.0):

            rx = -ux * ca + uy * sa * sign

            ry = -ux * sa * sign - uy * ca

            ctx.move_to(px, py)

            ctx.line_to(px + rx * size * scale, py + ry * size * scale)

        ctx.set_source_rgba(*rgba)

        ctx.set_line_width(lw)

        ctx.set_line_cap(cairo.LINE_CAP_ROUND)

        ctx.stroke()

    elif mtype == "triangle":

        hw = size * 0.45

        bx, by = px - ux * size, py - uy * size

        ctx.move_to(px, py)

        ctx.line_to(bx + perp[0] * hw, by + perp[1] * hw)

        ctx.line_to(bx - perp[0] * hw, by - perp[1] * hw)

        ctx.close_path()

        ctx.set_source_rgba(*rgba)

        ctx.fill()

    elif mtype == "bar":

        hw = size * 0.5

        ctx.move_to(px + perp[0] * hw, py + perp[1] * hw)

        ctx.line_to(px - perp[0] * hw, py - perp[1] * hw)

        ctx.set_source_rgba(*rgba)

        ctx.set_line_width(lw)

        ctx.stroke()

    else:

        # centred shapes sit just behind the endpoint so the tip stays crisp

        cx, cy = px - ux * size * 0.3, py - uy * size * 0.3

        r = size * 0.32

        if mtype == "circle":

            ctx.arc(cx, cy, r, 0.0, 2.0 * math.pi)

        elif mtype == "square":

            ctx.move_to(cx + ux * r + perp[0] * r, cy + uy * r + perp[1] * r)

            ctx.line_to(cx - ux * r + perp[0] * r, cy - uy * r + perp[1] * r)

            ctx.line_to(cx - ux * r - perp[0] * r, cy - uy * r - perp[1] * r)

            ctx.line_to(cx + ux * r - perp[0] * r, cy + uy * r - perp[1] * r)

            ctx.close_path()

        else:  # diamond

            ctx.move_to(cx + ux * r, cy + uy * r)

            ctx.line_to(cx + perp[0] * r, cy + perp[1] * r)

            ctx.line_to(cx - ux * r, cy - uy * r)

            ctx.line_to(cx - perp[0] * r, cy - perp[1] * r)

            ctx.close_path()

        ctx.set_source_rgba(*rgba)

        ctx.fill()



def _draw_markers(ctx, stroke, color, width):

    """Draw all configured start/end markers for ``stroke``."""

    if not isinstance(stroke, dict):

        return

    markers = get_markers(stroke) if 'get_markers' in globals() else {"start": "none", "end": "none"}

    if markers.get("start", "none") == "none" and markers.get("end", "none") == "none":

        return

    anchors = marker_anchors(stroke) if 'marker_anchors' in globals() else []

    for which, point, ux, uy in anchors:

        mtype = markers.get(which, "none")

        _draw_marker(ctx, mtype, point, ux, uy, color, width)


















# Export capability table. Raster formats are rendered through Cairo then
# encoded by Pillow; vector formats use the matching Cairo surface.
EXPORT_FORMATS = {
    ".png": "PNG",
    ".svg": "SVG",
    ".pdf": "PDF",
    ".eps": "EPS",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
}






























from views.canvas_extra import *
