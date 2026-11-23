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





def _stroke_has_active_thickness(stroke):

    try:

        for comp in _stroke_components(stroke):

            for sv in _get_distortion_styles(comp):

                if isinstance(sv, dict) and sv.get("type") == "thickness" and _distortion_style_active(sv):

                    return True

    except Exception:

        pass

    return False



def _draw_stroke_segments(ctx, stroke, seg_indices, stroke_color, stroke_width):

    if not seg_indices:

        return

    seg_set = set(seg_indices)

    if _stroke_needs_variable_width(stroke, seg_set):

        _draw_variable_width_segments(ctx, stroke, seg_set, None)

        return

    segs_all = segs_of(stroke)

    ranges = _component_ranges(stroke)

    comps = _stroke_components(stroke)



    def _draw_polyline(pts):

        if not pts or len(pts) < 2:

            return False

        ctx.move_to(pts[0][0], pts[0][1])

        for pt in pts[1:]:

            ctx.line_to(pt[0], pt[1])

        return True



    # draw by components to support per-component styles and wave distortion

    for ci, (s0, s1) in enumerate(ranges):

        idxs = [i for i in range(s0, min(s1, len(segs_all))) if i in seg_set]

        if not idxs:

            continue

        sc_i, sw_i = _effective_component_style(stroke, ci)

        comp = comps[ci] if ci < len(comps) else {}

        ctx.new_path()

        drew_c = False

        is_thickness = False

        try:

            _styles = _get_distortion_styles(comp) if '_get_distortion_styles' in dir() else (comp.get("styles") or [])

            is_thickness = any(isinstance(sv, dict) and sv.get("type") == "thickness" and _distortion_style_active(sv) for sv in _styles)

        except Exception:

            is_thickness = False

        if _component_wave_enabled(comp) and len(idxs) == (min(s1, len(segs_all)) - s0):

            poly = sample_distorted_component(stroke, ci)

            if poly and len(poly) >= 2:

                if is_thickness:

                    # Ribbon: [bottom_start..bottom_end, top_end..top_start]

                    n = len(poly) // 2

                    if n >= 2:

                        # Fill closed ribbon

                        ctx.new_path()

                        ctx.move_to(poly[0][0], poly[0][1])

                        for pt in poly[1:]:

                            ctx.line_to(pt[0], pt[1])

                        ctx.close_path()

                        eff_sc = sc_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_color

                        eff_sw = sw_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_width

                        ctx.save()

                        ctx.set_source_rgba(*color_rgba(eff_sc, DEFAULT_STROKE_RGBA))

                        ctx.fill_preserve()

                        # Stroke only top edge + caps, not the bottom baseline

                        ctx.new_path()

                        ctx.move_to(poly[n - 1][0], poly[n - 1][1])  # bottom_end -> end cap

                        for pt in poly[n:]:

                            ctx.line_to(pt[0], pt[1])  # top_end..top_start

                        ctx.line_to(poly[0][0], poly[0][1])  # start cap

                        if eff_sw is not None and float(eff_sw) > 0.0 and color_alpha(eff_sc, 1.0) > 0.0:

                            ctx.set_line_width(float(eff_sw))

                            apply_stroke_style(ctx, stroke, float(eff_sw))

                            ctx.stroke()

                        else:

                            ctx.new_path()

                        ctx.restore()

                        drew_c = True

                    else:

                        drew_c = _draw_polyline(poly)

                else:

                    drew_c = _draw_polyline(poly)

        if not drew_c:

            for i in idxs:

                p0, c1, c2, p3 = segs_all[i]

                ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])

                drew_c = True

        if drew_c and not is_thickness:

            eff_sc = sc_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_color

            eff_sw = sw_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_width

            if eff_sw is not None and float(eff_sw) > 0.0 and color_alpha(eff_sc, 1.0) > 0.0:

                ctx.save()

                ctx.set_source_rgba(*color_rgba(eff_sc, DEFAULT_STROKE_RGBA))

                ctx.set_line_width(float(eff_sw))

                apply_stroke_style(ctx, stroke, float(eff_sw))

                ctx.stroke()

                ctx.restore()

            else:

                ctx.new_path()

        elif drew_c and is_thickness:

            pass




def _draw_canvas_overlays(ctx, for_export, view_zoom, view_pan, guides, smart_guides, artboards, active_artboard):
    if for_export or not (getattr(cfg, "SHOW_GRID", False) or guides or smart_guides or artboards):
        return
    try:
        zoom = float(view_zoom) or 1.0
        wx0 = (0.0 - float(view_pan[0])) / zoom
        wy0 = (0.0 - float(view_pan[1])) / zoom
        wx1 = (float(cfg.CANVAS_W) - float(view_pan[0])) / zoom
        wy1 = (float(cfg.canvas_viewport_height()) - float(view_pan[1])) / zoom
        thin = 1.0 / zoom
        if getattr(cfg, "SHOW_GRID", False):
            spacing = float(getattr(cfg, "GRID_SIZE", 20.0) or 20.0)
            major_every = int(getattr(cfg, "GRID_MAJOR_EVERY", 5) or 5)
            minor, major_c = cfg.GRID_MINOR_RGB, cfg.GRID_MAJOR_RGB
            for x in grid_positions(wx0, wx1, spacing):
                is_major = (round(x / spacing) % major_every == 0)
                ctx.set_source_rgba(*(cairo_rgb(major_c if is_major else minor, 0.85)))
                ctx.set_line_width(thin)
                ctx.move_to(x, wy0); ctx.line_to(x, wy1); ctx.stroke()
            for y in grid_positions(wy0, wy1, spacing):
                is_major = (round(y / spacing) % major_every == 0)
                ctx.set_source_rgba(*(cairo_rgb(major_c if is_major else minor, 0.85)))
                ctx.set_line_width(thin)
                ctx.move_to(wx0, y); ctx.line_to(wx1, y); ctx.stroke()
        if artboards:
            for _ai, _ab in enumerate(artboards or ()):
                if not isinstance(_ab, dict):
                    continue
                try:
                    ax = float(_ab.get("x", 0.0)); ay = float(_ab.get("y", 0.0))
                    aw = float(_ab.get("w", 0.0)); ah = float(_ab.get("h", 0.0))
                except Exception:
                    continue
                if aw <= 0 or ah <= 0:
                    continue
                is_active = (_ai == active_artboard)
                ctx.save()
                try:
                    ctx.set_dash([])
                except Exception:
                    pass
                if is_active:
                    ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "ACCENT_RGB", (59, 130, 246)), 0.95)))
                    ctx.set_line_width(max(thin * 1.5, 2.0 / zoom))
                else:
                    ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "BORDER_RGB", (203, 213, 225)), 0.9)))
                    ctx.set_line_width(max(thin, 1.0 / zoom))
                ctx.rectangle(ax, ay, aw, ah)
                ctx.stroke()
                try:
                    name = str(_ab.get("name") or f"Artboard {_ai + 1}")
                    ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "MUTED_RGB", (100, 116, 139)), 0.95 if is_active else 0.75)))
                    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                    ctx.set_font_size(max(10.0 / zoom, 8.0 / zoom))
                    ctx.move_to(ax, ay - 4.0 / zoom)
                    ctx.show_text(name)
                except Exception:
                    pass
                ctx.restore()
        for g in guides or ():
            try:
                pos = float(g.get("pos", 0.0))
            except (TypeError, ValueError):
                continue
            ctx.set_source_rgba(*(cairo_rgb(cfg.GUIDE_RGB, 0.9)))
            ctx.set_line_width(thin)
            try:
                ctx.set_dash([6.0 / zoom, 4.0 / zoom])
            except Exception:
                pass
            if g.get("axis") == "x":
                ctx.move_to(pos, wy0); ctx.line_to(pos, wy1)
            else:
                ctx.move_to(wx0, pos); ctx.line_to(wx1, pos)
            ctx.stroke()
            try:
                ctx.set_dash([])
            except Exception:
                pass
        if smart_guides:
            ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "SMART_GUIDE_RGB", (236, 72, 153)), 0.95)))
            ctx.set_line_width(max(thin, 1.0 / zoom))
            try:
                ctx.set_dash([])
            except Exception:
                pass
            for sg in smart_guides:
                try:
                    if sg.get("axis") == "x":
                        pos = float(sg["pos"])
                        ctx.move_to(pos, float(sg.get("y0", wy0))); ctx.line_to(pos, float(sg.get("y1", wy1))); ctx.stroke()
                    elif sg.get("axis") == "y":
                        pos = float(sg["pos"])
                        ctx.move_to(float(sg.get("x0", wx0)), pos); ctx.line_to(float(sg.get("x1", wx1)), pos); ctx.stroke()
                except Exception:
                    continue
    except Exception:
        pass

def _draw_bezier_pen_preview(ctx, for_export, bezier_pen):
    if for_export or not (bezier_pen and isinstance(bezier_pen, dict)):
        return
    try:
        anchors = list(bezier_pen.get("anchors") or [])
        if not anchors:
            return
        preview_pt = bezier_pen.get("preview_pt")
        if len(anchors) >= 2:
            ctx.set_source_rgb(*EDITOR_SELECTION)
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.new_path()
            ctx.move_to(anchors[0]["pt"][0], anchors[0]["pt"][1])
            for i in range(len(anchors) - 1):
                a, b = anchors[i], anchors[i + 1]
                p0, p3 = a["pt"], b["pt"]
                c1 = a.get("h_out") or p0
                c2 = b.get("h_in") or p3
                ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
            ctx.stroke()
        if preview_pt is not None and not bezier_pen.get("mouse_down", False):
            last = anchors[-1]
            lp = last["pt"]
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.7)
            ctx.set_line_width(EDITOR_LINE_WIDTH)
            try:
                ctx.set_dash([6, 4])
            except Exception:
                pass
            ctx.new_path(); ctx.move_to(lp[0], lp[1]); ctx.line_to(preview_pt[0], preview_pt[1]); ctx.stroke()
            try:
                ctx.set_dash([])
            except Exception:
                pass
        ctx.set_source_rgba(*EDITOR_ACCENT, 0.7)
        ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
        for a in anchors:
            pt = a["pt"]
            for hk in ("h_in", "h_out"):
                hp = a.get(hk) or pt
                if abs(hp[0] - pt[0]) > 0.5 or abs(hp[1] - pt[1]) > 0.5:
                    ctx.new_path(); ctx.move_to(pt[0], pt[1]); ctx.line_to(hp[0], hp[1]); ctx.stroke()
        for a in anchors:
            pt = a["pt"]
            for hk in ("h_in", "h_out"):
                hp = a.get(hk) or pt
                if abs(hp[0] - pt[0]) > 0.5 or abs(hp[1] - pt[1]) > 0.5:
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(hp[0], hp[1], EDITOR_HANDLE_HALF, 0, 2 * math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(hp[0], hp[1], EDITOR_HANDLE_HALF, 0, 2 * math.pi); ctx.stroke()
        for idx, a in enumerate(anchors):
            pt = a["pt"]; s = EDITOR_HANDLE_HALF + 1
            ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0] - s, pt[1] - s, 2 * s, 2 * s); ctx.fill_preserve()
            ctx.set_source_rgb(*(EDITOR_ACCENT if idx == len(anchors) - 1 else EDITOR_SELECTION))
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD if idx == len(anchors) - 1 else EDITOR_LINE_WIDTH)
            ctx.stroke()
        if preview_pt is not None and not bezier_pen.get("mouse_down", False):
            px, py = preview_pt; s = EDITOR_HANDLE_HALF
            ctx.set_source_rgba(*EDITOR_HANDLE_FILL, 0.8); ctx.rectangle(px - s, py - s, 2 * s, 2 * s); ctx.fill_preserve()
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.8); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
        if len(anchors) >= 3 and preview_pt is not None and not bezier_pen.get("mouse_down", False):
            try:
                fp = anchors[0]["pt"]
                if math.hypot(preview_pt[0] - fp[0], preview_pt[1] - fp[1]) <= 10.0:
                    ctx.set_source_rgba(*EDITOR_ACCENT, 0.25); ctx.arc(fp[0], fp[1], EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(fp[0], fp[1], EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.stroke()
            except Exception:
                pass
    except Exception:
        pass

def _draw_gradient_edit_handles(ctx, edit_mode, gradient_edit_info):
    if not (edit_mode and gradient_edit_info and isinstance(gradient_edit_info, dict)):
        return
    try:
        gtype = gradient_edit_info.get("type")
        hs = gradient_edit_info.get("handles") or {}
        if gtype == "linear" and "p1" in hs and "p2" in hs:
            p1, p2 = hs["p1"], hs["p2"]
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.95); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.move_to(p1[0], p1[1]); ctx.line_to(p2[0], p2[1]); ctx.stroke()
            for name in ("p1", "p2"):
                pt = hs.get(name)
                if pt is None: continue
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
            cpt = hs.get("center")
            if cpt is not None:
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(cpt[0], cpt[1], EDITOR_HANDLE_HALF, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(cpt[0], cpt[1], EDITOR_HANDLE_HALF, 0, 2*math.pi); ctx.stroke()
        elif gtype in ("radial", "conic", "spiral", "diamond", "square"):
            cpt, rx_pt, ry_pt, rot_pt = hs.get("center"), hs.get("rx"), hs.get("ry"), hs.get("rot")
            if cpt is not None:
                gcx, gcy = cpt
                rpx = float(gradient_edit_info.get("radii_px", (0.0, 0.0))[0] or 0.0)
                rpy = float(gradient_edit_info.get("radii_px", (0.0, 0.0))[1] or 0.0)
                ang = float(gradient_edit_info.get("angle", 0.0) or 0.0)
                if rpx > 0.5 and rpy > 0.5:
                    ctx.save(); ctx.translate(gcx, gcy); ctx.rotate(ang); ctx.scale(rpx, rpy); ctx.new_sub_path()
                    if gtype == "square": ctx.rectangle(-1.0, -1.0, 2.0, 2.0)
                    elif gtype == "diamond": ctx.move_to(0.0, -1.0); ctx.line_to(1.0, 0.0); ctx.line_to(0.0, 1.0); ctx.line_to(-1.0, 0.0); ctx.close_path()
                    else: ctx.arc(0.0, 0.0, 1.0, 0, 2*math.pi)
                    ctx.restore(); ctx.set_source_rgba(*EDITOR_SELECTION, 0.9); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
                    if rx_pt is not None: ctx.move_to(gcx, gcy); ctx.line_to(rx_pt[0], rx_pt[1])
                    if ry_pt is not None: ctx.move_to(gcx, gcy); ctx.line_to(ry_pt[0], ry_pt[1])
                    ctx.set_source_rgba(*EDITOR_SELECTION, 0.7); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE); ctx.stroke()
                if rot_pt is not None and rx_pt is not None:
                    ctx.set_source_rgba(*EDITOR_ROTATION, 0.8); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
                    ctx.move_to(rx_pt[0], rx_pt[1]); ctx.line_to(rot_pt[0], rot_pt[1]); ctx.stroke()
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(rot_pt[0], rot_pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ROTATION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(rot_pt[0], rot_pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
                for name, pt in hs.items():
                    if pt is None: continue
                    if name == "center":
                        ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                        ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
                    elif name in ("rx", "ry", "edge"):
                        ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0]-EDITOR_HANDLE_HALF, pt[1]-EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF); ctx.fill_preserve()
                        ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
    except Exception:
        pass

def _draw_selection_overlays(ctx, strokes, sel_set, edit_mode, selection_submode, selected_curve, selected_curves, transform_handle_mode, pivot_pos):
    if not (edit_mode and sel_set):
        return
    selected_in_range = [i for i in sel_set if 0 <= i < len(strokes)]
    if selection_submode == "curve":
        sel_curves = selected_curves if selected_curves else (([selected_curve] if selected_curve is not None else []))
        for scv in sel_curves:
            try:
                si, comp_i = scv
            except Exception:
                continue
            if si not in selected_in_range or not (0 <= si < len(strokes)):
                continue
            segs = segs_of(strokes[si])
            ranges = _component_ranges(strokes[si])
            if not (0 <= comp_i < len(ranges)):
                continue
            s0, s1 = ranges[comp_i]
            dsegs = component_display_segs(strokes[si], comp_i) if 'component_display_segs' in globals() else None
            draw_segs = list(dsegs) if dsegs is not None and len(dsegs) == (min(s1, len(segs)) - s0) else list(segs[s0:min(s1, len(segs))])
            for p0, c1, c2, p3 in draw_segs:
                ctx.new_path(); ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                ctx.set_source_rgba(*EDITOR_ACCENT, 0.9)
                w = strokes[si].get("stroke_width", 3.0) if isinstance(strokes[si], dict) else 3.0
                ctx.set_line_width(max(4.0, w + 2.0)); ctx.stroke()
    if selection_submode == "nodes" and len(selected_in_range) == 1:
        idx = selected_in_range[0]
        segs = stroke_display_segs(strokes[idx]) if 'stroke_display_segs' in globals() else segs_of(strokes[idx])
        ctx.set_source_rgba(*EDITOR_GUIDE, 0.8); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
        for si, (p0, c1, c2, p3) in enumerate(segs):
            ctx.move_to(p0[0], p0[1]); ctx.line_to(c1[0], c1[1]); ctx.move_to(p3[0], p3[1]); ctx.line_to(c2[0], c2[1])
        ctx.stroke()
        for si, (p0, c1, c2, p3) in enumerate(segs):
            hr, hhalf = EDITOR_HANDLE_RADIUS, EDITOR_HANDLE_HALF
            if si == 0:
                for pt in (p0,):
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.stroke()
            for pt in (p3,):
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.stroke()
            for pt in (c1, c2):
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0]-hhalf, pt[1]-hhalf, 2*hhalf, 2*hhalf); ctx.fill_preserve()
                ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
    elif selection_submode == "transform":
        obb = combined_obb(strokes, selected_in_range)
        if obb:
            corners = obb.get("corners", [])
            handles = bbox_handles(obb, mode=transform_handle_mode)
            try: ctx.set_dash([6, 4])
            except Exception: pass
            ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH)
            if corners:
                ctx.move_to(corners[0][0], corners[0][1])
                for cpt in corners[1:]: ctx.line_to(cpt[0], cpt[1])
                ctx.close_path(); ctx.stroke()
            try: ctx.set_dash([])
            except Exception: pass
            if transform_handle_mode == "scale" and "n" in handles and "rot" in handles:
                npt, rpt = handles["n"], handles["rot"]
                ctx.set_source_rgb(*EDITOR_ROTATION); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
                ctx.move_to(npt[0], npt[1]); ctx.line_to(rpt[0], rpt[1]); ctx.stroke()
            for name, pt in handles.items():
                if name == "rot" or name.startswith("rot_"):
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ROTATION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
                elif name.startswith("skew_"):
                    d = EDITOR_SKEW_RADIUS
                    ctx.move_to(pt[0], pt[1]-d); ctx.line_to(pt[0]+d, pt[1]); ctx.line_to(pt[0], pt[1]+d); ctx.line_to(pt[0]-d, pt[1]); ctx.close_path()
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.fill_preserve()
                    ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
                else:
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0]-EDITOR_HANDLE_HALF, pt[1]-EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF); ctx.fill_preserve()
                    ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
            pv = pivot_pos if pivot_pos is not None else (obb["cx"], obb["cy"])
            if pv is not None:
                px, py = pv; r_out, r_in = EDITOR_PIVOT_RADIUS, EDITOR_PIVOT_INNER_RADIUS
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(px, py, r_out, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(px, py, r_out, 0, 2*math.pi); ctx.stroke()
                ctx.move_to(px-r_out, py); ctx.line_to(px-r_in, py); ctx.move_to(px+r_in, py); ctx.line_to(px+r_out, py)
                ctx.move_to(px, py-r_out); ctx.line_to(px, py-r_in); ctx.move_to(px, py+r_in); ctx.line_to(px, py+r_out); ctx.stroke()
                ctx.arc(px, py, r_in, 0, 2*math.pi); ctx.fill()
    elif selection_submode == "nodes" and len(selected_in_range) > 1:
        obb = combined_obb(strokes, selected_in_range)
        if obb:
            corners = obb.get("corners", [])
            try: ctx.set_dash([4, 4])
            except Exception: pass
            ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
            if corners:
                ctx.move_to(corners[0][0], corners[0][1])
                for cpt in corners[1:]: ctx.line_to(cpt[0], cpt[1])
                ctx.close_path(); ctx.stroke()
            try: ctx.set_dash([])
            except Exception: pass
def draw_scene(cairo_surface, strokes, active_stroke=None, snap_point=None, selected_index=None, selected_indices=None, edit_mode=False, selection_submode="transform", selected_curve=None, selected_curves=None, snap_kind="connect", redrawing_curve=None, ref_img=None, view_zoom=None, view_pan=None, pivot_pos=None, for_export=False, transform_handle_mode="scale", gradient_edit_info=None, export_scale=1.0, guides=None, smart_guides=None, bezier_pen=None, artboards=None, active_artboard=-1):

    # Backward compat: selected_index (single) or selected_indices (collection)
    if selected_indices is None and selected_index is not None:
        selected_indices = selected_index
    sel_set = _selection_set(selected_indices)

    if view_zoom is None:
        view_zoom = getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0
    if view_pan is None:
        view_pan = (getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0))

    ctx = cairo.Context(cairo_surface)
    try:
        ctx.set_antialias(cairo.ANTIALIAS_BEST)
    except Exception:
        pass
    # background in screen/viewport space (skip for export: keep transparent/no background)
    if not for_export:
        ctx.save()
        ctx.identity_matrix()
        ctx.set_source_rgb(*BG_COLOR)
        ctx.paint()
        ctx.restore()

    # world/view transform
    ctx.save()
    ctx.translate(float(view_pan[0]), float(view_pan[1]))
    ctx.scale(float(view_zoom), float(view_zoom))
    if export_scale and float(export_scale) != 1.0:
        ctx.scale(float(export_scale), float(export_scale))

    # Grid + ruler guides + artboards overlay (view-only; never part of an export).
    _draw_canvas_overlays(ctx, for_export, view_zoom, view_pan, guides, smart_guides, artboards, active_artboard)

    # Reference image, behind strokes
    if ref_img and ref_img.get("visible", True) and ref_img.get("surface") is not None:
        try:
            rsurf = ref_img["surface"]
            ctx.save()
            ctx.translate(float(ref_img.get("x", 0)), float(ref_img.get("y", 0)))
            s = float(ref_img.get("scale", 1.0))
            ctx.scale(s, s)
            ctx.set_source_surface(rsurf, 0, 0)
            ctx.paint_with_alpha(clamp(float(ref_img.get("opacity", 0.5)), 0.0, 1.0))
            ctx.restore()
        except Exception:
            pass

    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    redraw_target = None
    if redrawing_curve is not None:
        redraw_target = (redrawing_curve.get("stroke_idx"), redrawing_curve.get("comp_idx", redrawing_curve.get("seg_idx")))


    for idx, stroke in enumerate(strokes):
        # Hidden objects (organization/layers) are excluded from all rendering.
        if isinstance(stroke, dict) and stroke.get("hidden", False):
            continue
        segs = segs_of(stroke)
        if not segs:
            continue
        stroke_color = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if isinstance(stroke, dict) else (0.1, 0.1, 0.15)
        stroke_width = stroke.get("stroke_width", 3.0) if isinstance(stroke, dict) else 3.0
        fill_color = stroke.get("fill_color") if isinstance(stroke, dict) else None
        fill_gradient = stroke.get("fill_gradient") if isinstance(stroke, dict) else None
        fill_pattern = stroke.get("fill_pattern") if isinstance(stroke, dict) else None
        hidden = set(stroke.get("hidden_segs", set()) or set()) if isinstance(stroke, dict) else set()
        is_selected_stroke = (idx in sel_set and edit_mode)
        show_hidden = edit_mode and selection_submode in ("curve", "nodes") and bool(hidden)

        # Hint: show original/base (guide) shape for distorted curves so they remain selectable
        if (not for_export) and _stroke_has_wave(stroke):

            comps = _stroke_components(stroke)
            ranges = _component_ranges(stroke)
            ctx.save()
            try:
                ctx.set_dash([4, 4])
            except Exception:
                pass
            for ci, (s0, s1) in enumerate(ranges):
                comp = comps[ci] if ci < len(comps) else {}
                if not _component_wave_enabled(comp):
                    continue
                # Thickness replaces the curve with a filled ribbon; don't draw original-path guide.
                try:
                    _is_thick_guide = any(isinstance(sv, dict) and sv.get("type") == "thickness" and _distortion_style_active(sv) for sv in _get_distortion_styles(comp))
                except Exception:
                    _is_thick_guide = False
                if _is_thick_guide:
                    continue
                ctx.new_path()
                drew_g = False
                for i in range(s0, min(s1, len(segs))):
                    if i in hidden:
                        continue
                    p0, c1, c2, p3 = segs[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                    drew_g = True
                if drew_g:
                    ctx.set_source_rgba(*EDITOR_SELECTION, 0.35)
                    ctx.set_line_width(max(1.0, float(stroke_width) * 0.8))
                    ctx.stroke()
            try:
                ctx.set_dash([])
            except Exception:
                pass
            ctx.restore()

        if redraw_target and redraw_target[0] == idx:
            comp_i = redraw_target[1]
            ranges = _component_ranges(stroke)
            in_redraw = set()
            if 0 <= comp_i < len(ranges):
                s0, s1 = ranges[comp_i]
                in_redraw = set(range(s0, min(s1, len(segs))))

            # draw non-redraw, non-hidden segments normally
            normal_segs_set = {i for i in range(len(segs)) if i not in in_redraw and i not in hidden}
            if normal_segs_set:
                # selection highlight for normal part
                if is_selected_stroke:
                    ctx.new_path()
                    for i in sorted(normal_segs_set):
                        p0, c1, c2, p3 = segs[i]
                        ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                    ctx.set_source_rgba(*EDITOR_SELECTION, 0.35)
                    ctx.set_line_width(stroke_width + 4.0)
                    ctx.stroke()
                _draw_stroke_segments(ctx, stroke, normal_segs_set, stroke_color, stroke_width)

            # draw redrawn component as bright yellow low-opacity template
            if in_redraw:
                ctx.new_path()
                for i in sorted(in_redraw):
                    p0, c1, c2, p3 = segs[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                ctx.set_source_rgba(*EDITOR_TEMPLATE, 0.35)
                ctx.set_line_width(max(stroke_width, 2.0))
                ctx.stroke()
            # hidden segments styled (except those being redrawn template)
            if show_hidden:
                _draw_hidden_segments(ctx, stroke, segs, hidden - in_redraw, stroke_width)
            continue

        # Selection highlight behind the stroke so the actual stroke color stays visible
        if is_selected_stroke and (not _stroke_has_active_thickness(stroke)) and draw_stroke_path(ctx, stroke):
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.35)
            ctx.set_line_width(stroke_width + 4.0)
            ctx.stroke()

        visible_segs = [i for i in range(len(segs)) if i not in hidden]
        has_stroke = (stroke_width is not None and float(stroke_width) > 0.0 and color_alpha(stroke_color, 1.0) > 0.0)
        fill_spec = fill_pattern if fill_pattern is not None else (fill_gradient if fill_gradient is not None else fill_color)

        # Appearance: object opacity + blend mode are composited as a single
        # unit via a temporary group; drop shadows are painted behind the art.
        _app = get_appearance(stroke) if isinstance(stroke, dict) else dict(DEFAULT_APPEARANCE)
        _grouped = (_app["opacity"] < 1.0 or _app["blend_mode"] != "normal")
        if _app["shadow"] is not None:
            draw_drop_shadow(ctx, stroke, _app["shadow"], stroke_color,
                             stroke_width, fill_spec)
        if _grouped:
            ctx.save()
            ctx.push_group()

        if _stroke_has_active_thickness(stroke):
            # Thickness draws its own filled ribbon; avoid original-path fill/stroke artifacts.
            _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
        elif fill_spec is not None and draw_stroke_path(ctx, stroke):
            if not _apply_fill_source(ctx, stroke, fill_spec):
                fill_spec = None
            if fill_spec is not None:
                if _stroke_needs_variable_width(stroke, visible_segs):
                    ctx.fill()
                    if has_stroke or _stroke_has_component_styles(stroke):
                        _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
                else:
                    if has_stroke or _stroke_has_component_styles(stroke):
                        ctx.fill_preserve()
                        if _stroke_has_component_styles(stroke):
                            ctx.new_path()
                        _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
                    else:
                        ctx.fill()
            else:
                ctx.new_path()
                _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
        else:
            _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)

        if isinstance(stroke, dict) and has_stroke:
            _draw_markers(ctx, stroke, stroke_color, stroke_width)

        if _grouped:
            # Composite the isolated art with the object's blend mode and
            # opacity as one unit (so overlapping fill+stroke don't double-blend).
            _pat = ctx.pop_group()
            ctx.set_operator(blend_operator(_app["blend_mode"]))
            ctx.set_source(_pat)
            ctx.paint_with_alpha(_app["opacity"])
            ctx.restore()

        # Show hidden curves differently in edit curve/nodes modes for easier selection
        if show_hidden:
            _draw_hidden_segments(ctx, stroke, segs, hidden, stroke_width)

    _draw_selection_overlays(ctx, strokes, sel_set, edit_mode, selection_submode, selected_curve, selected_curves, transform_handle_mode, pivot_pos)

    _draw_gradient_edit_handles(ctx, edit_mode, gradient_edit_info)

    if snap_point is not None:
        x, y = snap_point
        if snap_kind == "assist":
            r = 10.0
            ctx.new_path()
            ctx.move_to(x, y - r); ctx.line_to(x + r, y); ctx.line_to(x, y + r); ctx.line_to(x - r, y); ctx.close_path()
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.22)
            ctx.fill_preserve()
            ctx.set_source_rgb(*EDITOR_SELECTION)
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.stroke()
            ctx.new_path()
            ctx.move_to(x, y - EDITOR_SNAP_INNER); ctx.line_to(x + EDITOR_SNAP_INNER, y); ctx.line_to(x, y + EDITOR_SNAP_INNER); ctx.line_to(x - EDITOR_SNAP_INNER, y); ctx.close_path()
            ctx.fill()
        else:
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.25)
            ctx.arc(x, y, EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.fill()
            ctx.set_source_rgb(*EDITOR_SELECTION)
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.arc(x, y, EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.stroke()
            ctx.arc(x, y, EDITOR_SNAP_INNER, 0, 2 * math.pi); ctx.fill()

    ctx.restore()  # view transform
    cairo_surface.flush()

def surface_to_pygame(cairo_surface):
    width = cairo_surface.get_width()
    height = cairo_surface.get_height()
    buf = cairo_surface.get_data()
    try:
        data = buf.tobytes()
    except Exception:
        data = bytes(buf)
    return pygame.image.frombuffer(data, (width, height), "BGRA")


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


def export_format_for(path):
    """Return the export format name for ``path``, or ``None`` if unknown."""
    return EXPORT_FORMATS.get(os.path.splitext(str(path))[1].lower())


def normalize_export_scale(scale):
    """Clamp an export scale factor to a sane range (1x default)."""
    try:
        value = float(scale)
    except (TypeError, ValueError):
        return 1.0
    if value <= 0.0 or not math.isfinite(value):
        return 1.0
    return max(0.1, min(10.0, value))


def _export_base_size(size):
    if size:
        return max(1, int(size[0])), max(1, int(size[1]))
    return max(1, int(cfg.CANVAS_W)), max(1, int(cfg.canvas_viewport_height()))


def _resolve_export_artboard(artboard, size, view_zoom, view_pan):
    """Return (base_size, view_zoom, view_pan) adjusted for an active artboard."""
    if isinstance(artboard, dict):
        try:
            ax = float(artboard.get("x", 0.0)); ay = float(artboard.get("y", 0.0))
            aw = float(artboard.get("w", 0.0)); ah = float(artboard.get("h", 0.0))
            if aw > 0 and ah > 0:
                return (max(1, int(round(aw))), max(1, int(round(ah)))), 1.0, (-ax, -ay)
        except Exception:
            pass
    return _export_base_size(size), view_zoom, view_pan


def _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=None):
    draw_scene(surf, strokes, ref_img=ref_img, view_zoom=view_zoom,
               view_pan=view_pan, for_export=True, export_scale=scale)


def _raster_surface(w, h, scale):
    sw = max(1, int(round(w * scale)))
    sh = max(1, int(round(h * scale)))
    return make_cairo_surface(sw, sh)


def _png_bytes(surf):
    import io
    buf = io.BytesIO()
    surf.write_to_png(buf)
    buf.seek(0)
    return buf


def export_scene_png(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, dpi=None, artboard=None):
    """Export the current scene to a PNG file (viewport- or artboard-sized)."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    surf = _raster_surface(w, h, scale)
    _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=artboard)
    if dpi:
        # Cairo does not embed pHYs metadata; Pillow does.
        from PIL import Image
        img = Image.open(_png_bytes(surf)).convert("RGBA")
        img.save(path, "PNG", dpi=(float(dpi), float(dpi)))
    else:
        surf.write_to_png(path)


def export_scene_svg(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, artboard=None):
    """Export the current scene to an SVG file (viewport- or artboard-sized)."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    surf = cairo.SVGSurface(str(path), w * scale, h * scale)
    try:
        _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=artboard)
        try:
            surf.flush()
        except Exception:
            pass
    finally:
        try:
            surf.finish()
        except Exception:
            pass


def export_scene_pdf(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, dpi=None, artboard=None):
    """Export to PDF. ``dpi`` sets the physical page size (72 pt/in)."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    factor = 72.0 / float(dpi) if dpi and float(dpi) > 0 else 1.0
    surf = cairo.PDFSurface(str(path), w * factor, h * factor)
    try:
        _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale * factor, artboard=artboard)
    finally:
        try:
            surf.finish()
        except Exception:
            pass


def export_scene_eps(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, dpi=None, artboard=None):
    """Export to Encapsulated PostScript. ``dpi`` sets the page size."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    factor = 72.0 / float(dpi) if dpi and float(dpi) > 0 else 1.0
    surf = cairo.PSSurface(str(path), w * factor, h * factor)
    try:
        try:
            surf.set_eps(True)
        except Exception:
            pass
        _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale * factor, artboard=artboard)
    finally:
        try:
            surf.finish()
        except Exception:
            pass


def export_scene_raster(path, strokes, fmt, ref_img=None, view_zoom=1.0,
                        view_pan=(0.0, 0.0), size=None, scale=1.0, dpi=None, quality=92, artboard=None):
    """Export to JPEG or WebP via Pillow (Cairo only writes PNG natively)."""
    from PIL import Image
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    surf = _raster_surface(w, h, scale)
    _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=artboard)
    img = Image.open(_png_bytes(surf)).convert("RGBA")
    save_kwargs = {"quality": int(quality)}
    if fmt == "JPEG":
        # JPEG has no alpha channel: flatten onto white.
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    if dpi:
        save_kwargs["dpi"] = (float(dpi), float(dpi))
    img.save(path, fmt, **save_kwargs)


def export_scene_image(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                       size=None, scale=1.0, dpi=None, artboard=None):
    """Export the scene using the file extension to select the format.

    Supported: PNG, SVG, PDF, EPS, JPG/JPEG, WebP. Unknown extensions raise
    ``ValueError`` instead of silently writing PNG bytes under a wrong name.
    If ``artboard`` is provided, export is cropped/sized to that artboard.
    """
    fmt = export_format_for(path)
    if fmt is None:
        raise ValueError(f"Unsupported export format: {path}")
    kwargs = dict(ref_img=ref_img, view_zoom=view_zoom, view_pan=view_pan,
                  size=size, scale=scale, artboard=artboard)
    if fmt in ("PNG", "PDF", "EPS", "JPEG", "WEBP"):
        kwargs["dpi"] = dpi
    if fmt == "PNG":
        export_scene_png(path, strokes, **kwargs)
    elif fmt == "SVG":
        export_scene_svg(path, strokes, **kwargs)
    elif fmt == "PDF":
        export_scene_pdf(path, strokes, **kwargs)
    elif fmt == "EPS":
        export_scene_eps(path, strokes, **kwargs)
    else:
        export_scene_raster(path, strokes, fmt, **kwargs)

def _pygame_image_to_cairo_surface(path):
    """Load any pygame-supported image and copy its pixels into a cairo surface.

    Returns a cairo.ImageSurface (ARGB32) or None. The pixels are copied into
    the surface's own buffer, so there is no external buffer whose lifetime we
    have to track. (pycairo surfaces are C objects and cannot hold a reference
    to a Python buffer as an attribute, which previously made every non-PNG
    load fail silently.)
    """
    try:
        img = pygame.image.load(path)
    except Exception:
        return None
    try:
        img = img.convert_alpha()
    except Exception:
        # No display / conversion unavailable: use the loaded surface as-is.
        pass
    w, h = img.get_size()
    if w <= 0 or h <= 0:
        return None
    try:
        data = pygame.image.tobytes(img, "BGRA")
    except AttributeError:  # older pygame
        data = pygame.image.tostring(img, "BGRA")
    try:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        view = surf.get_data()
        view[:len(data)] = data
        # We wrote straight into the surface's buffer, so tell cairo the pixels
        # changed. Without this it can keep painting a stale (blank) snapshot.
        try:
            surf.mark_dirty()
        except Exception:
            pass
        return surf
    except Exception:
        return None


def load_reference_image(path):
    """Load image file into a cairo ImageSurface (ARGB32) for reference drawing.

    PNG uses cairo's native loader (fast and exact). Everything else — and any
    PNG cairo cannot decode — goes through pygame, so JPG/JPEG/BMP/GIF/WEBP all
    work consistently. Returns None only if the file genuinely cannot be read.
    """
    if not path:
        return None
    surf = None
    # Prefer cairo's PNG loader when possible.
    if str(path).lower().endswith(".png"):
        try:
            surf = cairo.ImageSurface.create_from_png(path)
        except Exception:
            surf = None
    # Fall back to pygame for other formats and unreadable PNGs.
    if surf is None:
        surf = _pygame_image_to_cairo_surface(path)
        if surf is None:
            return None
    w, h = surf.get_width(), surf.get_height()
    return {"surface": surf, "w": w, "h": h, "x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 0.5, "visible": True, "path": path}
