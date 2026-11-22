"""Model: text rendered as editable cubic-bezier outlines.

Text is stored as ordinary stroke geometry (cubic segments) so it flows through
the existing transform, boolean, styling and export pipeline. A small metadata
block on the stroke keeps it re-editable: ``text_content``, ``font_family``,
``font_size`` and ``text_x``/``text_y`` (the baseline origin).

Glyph outlines come from fontTools (any TrueType/OpenType font). Quadratic
TrueType curves are converted to cubics so our single segment representation
covers every font. If no font file can be found, a lightweight block-letter
fallback is used so text still works on minimal installs.
"""
import os

from fontTools.ttLib import TTFont
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.recordingPen import RecordingPen

from bezier import cubic_bezier_point, cubic_bezier_derivative

# Font family key -> list of candidate font files (first existing wins).
FONT_FILES = {
    "Sans": [
        r"C:\Windows\Fonts\DejaVuSans.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "Sans Bold": [
        r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "Serif": [
        r"C:\Windows\Fonts\DejaVuSerif.ttf",
        r"C:\Windows\Fonts\times.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ],
    "Mono": [
        r"C:\Windows\Fonts\DejaVuSansMono.ttf",
        r"C:\Windows\Fonts\consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
}
FONT_FAMILIES = tuple(FONT_FILES)
DEFAULT_FONT = "Sans"
DEFAULT_SIZE = 36.0

_font_cache = {}


def font_path(family):
    """Return an existing font file path for ``family`` or ``None``."""
    key = family if family in FONT_FILES else DEFAULT_FONT
    if key in _font_cache:
        return _font_cache[key]
    found = None
    for candidate in FONT_FILES[key]:
        if candidate and os.path.isfile(candidate):
            found = candidate
            break
    _font_cache[key] = found
    return found


def _load_font(family):
    path = font_path(family)
    if not path:
        return None
    try:
        key = family if family in FONT_FILES else DEFAULT_FONT
        if ("font", key) not in _font_cache:
            _font_cache[("font", key)] = TTFont(path, lazy=True)
        return _font_cache[("font", key)]
    except Exception:
        return None


def _pt(p):
    return (float(p[0]), float(p[1]))


def new_text_stroke(text, x=0.0, y=0.0, family=DEFAULT_FONT, size=DEFAULT_SIZE,
                    color=(0.1, 0.1, 0.15, 1.0), path_segs=None, path_offset=0.0):
    """Create an editable text stroke whose glyphs are cubic outlines.

    When ``path_segs`` is provided the text is laid out along that path and the
    stroke stores ``text_path`` metadata so it can be re-edited/reflowed.
    """
    from models.strokes import new_stroke
    segs = text_to_segs(text, x, y, family, size)
    st = new_stroke(segs, stroke_color=color, stroke_width=0.0, fill_color=color)
    st["is_text"] = True
    st["text_content"] = str(text)
    st["font_family"] = family if family in FONT_FILES else DEFAULT_FONT
    st["font_size"] = float(size)
    st["text_x"] = float(x)
    st["text_y"] = float(y)
    if path_segs:
        st = set_text_path(st, path_segs, path_offset)
    return st


def set_text_path(stroke, path_segs, offset=0.0):
    """Attach/update text-on-path metadata and reflow outlines. Returns a copy."""
    if not isinstance(stroke, dict):
        return stroke
    try:
        path_copy = [tuple(tuple(p) for p in seg[:4]) for seg in (path_segs or []) if seg and len(seg) >= 4]
    except Exception:
        path_copy = []
    out = dict(stroke)
    out["text_path"] = {"segs": path_copy, "offset": float(offset or 0.0)}
    return update_text_stroke(out)


def clear_text_path(stroke):
    """Remove text-on-path metadata and reflow as straight text. Returns a copy."""
    if not isinstance(stroke, dict):
        return stroke
    out = dict(stroke)
    out.pop("text_path", None)
    return update_text_stroke(out)


def update_text_stroke(stroke, **fields):
    """Return a copy of a text stroke with edited fields and fresh outlines."""
    out = dict(stroke) if isinstance(stroke, dict) else {}
    # path control: path_segs/path_offset override text_path; text_path=None clears
    if "text_path" in fields:
        tpv = fields.pop("text_path")
        if tpv is None:
            out.pop("text_path", None)
        elif isinstance(tpv, dict):
            out["text_path"] = dict(tpv)
    if "path_segs" in fields:
        psegs = fields.pop("path_segs")
        poff = fields.pop("path_offset", (out.get("text_path") or {}).get("offset", 0.0) if isinstance(out.get("text_path"), dict) else 0.0)
        if psegs:
            try:
                pcopy = [tuple(tuple(p) for p in seg[:4]) for seg in (psegs or []) if seg and len(seg) >= 4]
            except Exception:
                pcopy = []
            out["text_path"] = {"segs": pcopy, "offset": float(poff or 0.0)}
        else:
            out.pop("text_path", None)
    elif "path_offset" in fields and isinstance(out.get("text_path"), dict):
        try:
            out["text_path"]["offset"] = float(fields.pop("path_offset") or 0.0)
        except Exception:
            fields.pop("path_offset", None)

    content = fields.get("text_content", out.get("text_content", ""))
    family = fields.get("font_family", out.get("font_family", DEFAULT_FONT))
    size = fields.get("font_size", out.get("font_size", DEFAULT_SIZE))
    x = fields.get("text_x", out.get("text_x", 0.0))
    y = fields.get("text_y", out.get("text_y", 0.0))
    out["text_content"] = str(content)
    out["font_family"] = family if family in FONT_FILES else DEFAULT_FONT
    try:
        out["font_size"] = max(1.0, float(size))
    except (TypeError, ValueError):
        out["font_size"] = DEFAULT_SIZE
    try:
        out["text_x"] = float(x)
        out["text_y"] = float(y)
    except (TypeError, ValueError):
        out["text_x"], out["text_y"] = 0.0, 0.0
    straight = text_to_segs(out["text_content"], out["text_x"], out["text_y"],
                            out["font_family"], out["font_size"])
    tp = out.get("text_path")
    if isinstance(tp, dict) and tp.get("segs"):
        try:
            off = float(tp.get("offset", 0.0) or 0.0)
        except Exception:
            off = 0.0
        out["segs"] = map_segs_to_path(straight, out["text_x"], out["text_y"], tp.get("segs") or [], off)
    else:
        out["segs"] = straight
    out["is_text"] = True
    out["obb"] = None
    try:
        from models.geometry import compute_stroke_obb
        out["obb"] = compute_stroke_obb(out)
    except Exception:
        pass
    return out


def is_text_stroke(stroke):
    return bool(isinstance(stroke, dict) and stroke.get("is_text"))


def text_metrics(text, family=DEFAULT_FONT, size=DEFAULT_SIZE):
    """Return ``(width, height)`` in pixels for single-line ``text``."""
    font = _load_font(family)
    line = str(text or "")
    if font is None:
        return (max(1, len(line)) * size * 0.6, size * 1.2)
    try:
        upem = float(font["head"].unitsPerEm)
        hmtx = font["hmtx"]
        cmap = font.getBestCmap()
        units = 0.0
        for ch in line:
            gname = cmap.get(ord(ch))
            if gname is not None:
                units += float(hmtx[gname][0])
        return (units / upem * size, size * 1.2)
    except Exception:
        return (max(1, len(line)) * size * 0.6, size * 1.2)


def text_to_segs(text, x=0.0, y=0.0, family=DEFAULT_FONT, size=DEFAULT_SIZE):
    """Convert ``text`` to cubic segments with its baseline at ``(x, y)``.

    The y axis is flipped (font coordinates are y-up, canvas is y-down) and
    glyph advances are applied left-to-right. Newlines start a fresh line
    one ``size * 1.2`` lower. Straight portions are represented as cubic
    segments with coincident control points, consistent with the other
    primitives in :mod:`models.geometry`.
    """
    lines = str(text or "").split("\n")
    font = _load_font(family)
    if font is None:
        return _fallback_segs(lines, x, y, size)
    try:
        upem = float(font["head"].unitsPerEm)
    except Exception:
        return _fallback_segs(lines, x, y, size)
    scale = float(size) / upem
    line_h = float(size) * 1.2
    segs = []
    glyph_set = None
    cmap = None
    hmtx = None
    try:
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap()
        hmtx = font["hmtx"]
    except Exception:
        return _fallback_segs(lines, x, y, size)

    for li, line in enumerate(lines):
        cursor = 0.0
        baseline = float(y) + li * line_h
        for ch in line:
            gname = cmap.get(ord(ch))
            if gname is not None:
                try:
                    rec = RecordingPen()
                    pen = Qu2CuPen(rec, max_err=1.0, all_cubic=True)
                    glyph_set[gname].draw(pen)
                    segs.extend(_contours_to_segs(rec.value, x + cursor * scale,
                                                  baseline, scale))
                except Exception:
                    pass
                try:
                    cursor += float(hmtx[gname][0])
                except Exception:
                    cursor += upem * 0.5
            else:
                cursor += upem * 0.5
    return segs


def _contours_to_segs(ops, origin_x, baseline, scale):
    """Turn a RecordingPen command stream into cubic segments."""
    out = []
    start = None
    current = None
    contour_start = None
    for op, args in ops:
        if op == "moveTo":
            current = _pt(args[0])
            start = current
            contour_start = current
        elif op == "lineTo":
            p = _pt(args[0])
            p0 = current or p
            out.append((_to_canvas(p0, origin_x, baseline, scale),
                        _to_canvas(p0, origin_x, baseline, scale),
                        _to_canvas(p, origin_x, baseline, scale),
                        _to_canvas(p, origin_x, baseline, scale)))
            current = p
        elif op == "curveTo":
            c1, c2, p = _pt(args[0]), _pt(args[1]), _pt(args[2])
            p0 = current or p
            out.append((_to_canvas(p0, origin_x, baseline, scale),
                        _to_canvas(c1, origin_x, baseline, scale),
                        _to_canvas(c2, origin_x, baseline, scale),
                        _to_canvas(p, origin_x, baseline, scale)))
            current = p
        elif op == "closePath":
            if current is not None and contour_start is not None:
                if abs(current[0] - contour_start[0]) > 1e-6 or abs(current[1] - contour_start[1]) > 1e-6:
                    c = contour_start
                    out.append((_to_canvas(current, origin_x, baseline, scale),
                                _to_canvas(current, origin_x, baseline, scale),
                                _to_canvas(c, origin_x, baseline, scale),
                                _to_canvas(c, origin_x, baseline, scale)))
            current = start
    return out


def _to_canvas(p, origin_x, baseline, scale):
    return (origin_x + p[0] * scale, baseline - p[1] * scale)



def _sample_path(path_segs, step=2.0):
    """Return cumulative-distance samples [(d,x,y,tx,ty,nx,ny), ...] along path segs."""
    import math as _m
    samples = []
    prev = None
    try:
        step = max(0.5, float(step))
    except Exception:
        step = 2.0
    for seg in (path_segs or []):
        if not seg or len(seg) < 4:
            continue
        p0, c1, c2, p3 = seg[0], seg[1], seg[2], seg[3]
        try:
            chord = _m.hypot(p3[0]-p0[0], p3[1]-p0[1])
            cpoly = (_m.hypot(c1[0]-p0[0], c1[1]-p0[1]) +
                     _m.hypot(c2[0]-c1[0], c2[1]-c1[1]) +
                     _m.hypot(p3[0]-c2[0], p3[1]-c2[1]))
            seg_len = 0.5 * chord + 0.5 * cpoly
        except Exception:
            seg_len = 0.0
        n = max(2, int(_m.ceil(seg_len / step)) + 1)
        for i in range(n):
            t = i / (n - 1) if n > 1 else 0.0
            try:
                x, y = cubic_bezier_point(p0, c1, c2, p3, t)
                dx, dy = cubic_bezier_derivative(p0, c1, c2, p3, t)
            except Exception:
                continue
            tl = _m.hypot(dx, dy)
            if tl < 1e-6:
                if prev is not None:
                    dx, dy = prev[3], prev[4]
                    tl = _m.hypot(dx, dy)
                if tl < 1e-6:
                    dx, dy, tl = 1.0, 0.0, 1.0
            tx, ty = dx / tl, dy / tl
            nx, ny = -ty, tx
            if samples and i == 0:
                last = samples[-1]
                extra = _m.hypot(x - last[1], y - last[2])
                s = (last[0] + extra, float(x), float(y), float(tx), float(ty), float(nx), float(ny))
                samples[-1] = s
                prev = s
            else:
                d = 0.0 if prev is None else prev[0] + _m.hypot(x - prev[1], y - prev[2])
                s = (d, float(x), float(y), float(tx), float(ty), float(nx), float(ny))
                samples.append(s)
                prev = s
    return samples


def _point_along_samples(samples, d):
    """Return (x,y,tx,ty,nx,ny) at arc length d, clamped to path ends."""
    if not samples:
        return None
    if d <= samples[0][0]:
        s = samples[0]
        return (s[1], s[2], s[3], s[4], s[5], s[6])
    if d >= samples[-1][0]:
        s = samples[-1]
        return (s[1], s[2], s[3], s[4], s[5], s[6])
    lo, hi = 0, len(samples) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if samples[mid][0] <= d:
            lo = mid
        else:
            hi = mid
    s0, s1 = samples[lo], samples[hi]
    span = s1[0] - s0[0]
    t = 0.0 if span < 1e-9 else (d - s0[0]) / span
    x = s0[1] + (s1[1] - s0[1]) * t
    y = s0[2] + (s1[2] - s0[2]) * t
    tx = s0[3] + (s1[3] - s0[3]) * t
    ty = s0[4] + (s1[4] - s0[4]) * t
    tl = (tx*tx + ty*ty) ** 0.5
    if tl < 1e-9:
        tx, ty, tl = s0[3], s0[4], 1.0
    tx, ty = tx / tl, ty / tl
    nx, ny = -ty, tx
    return (x, y, tx, ty, nx, ny)


def map_segs_to_path(segs, origin_x, baseline_y, path_segs, offset=0.0):
    """Map straight-laid-out text segments onto path_segs.

    Horizontal distance from ``origin_x`` maps to arc length along the path;
    vertical distance from ``baseline_y`` maps along the path normal.
    """
    if not segs or not path_segs:
        return list(segs or [])
    samples = _sample_path(path_segs)
    if len(samples) < 2:
        return list(segs)
    try:
        offset = float(offset or 0.0)
    except Exception:
        offset = 0.0
    out = []
    for seg in segs:
        if not seg or len(seg) < 4:
            continue
        nseg = []
        ok = True
        for p in seg[:4]:
            try:
                px, py = float(p[0]), float(p[1])
            except Exception:
                px, py = 0.0, 0.0
            dx = px - float(origin_x)
            dy = py - float(baseline_y)
            m = _point_along_samples(samples, dx + offset)
            if m is None:
                nseg.append((px, py))
            else:
                bx, by, tx, ty, nx, ny = m
                nseg.append((bx + nx * dy, by + ny * dy))
        if len(nseg) == 4:
            out.append(tuple(nseg))
    return out

# Minimal 5x7 block font used only when no TTF is available.
_BLOCK = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


def _fallback_segs(lines, x, y, size):
    segs = []
    unit = size / 7.0
    line_h = size * 1.2
    for li, line in enumerate(lines):
        cx = x
        base = y + li * line_h
        for ch in line.upper():
            pattern = _BLOCK.get(ch)
            if pattern is None:
                cx += unit * 6
                continue
            for row, bits in enumerate(pattern):
                for col, bit in enumerate(bits):
                    if bit != "1":
                        continue
                    px = cx + col * unit
                    py = base - row * unit
                    a = (px, py)
                    b = (px + unit, py)
                    c = (px + unit, py - unit)
                    d = (px, py - unit)
                    segs.extend([(a, a, b, b), (b, b, c, c),
                                 (c, c, d, d), (d, d, a, a)])
            cx += unit * 6
    return segs
