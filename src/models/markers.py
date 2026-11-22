"""Model: stroke end markers (arrowheads and decorative caps).

Markers are stored on a stroke as ``start_marker`` / ``end_marker`` strings.
Defaults are ``"none"`` so existing artwork renders byte-for-byte identically.
The legacy ``arrow_end`` boolean (used by the line primitive) is still honoured
and reported as an ``"arrow"`` end marker.

Marker geometry is only meaningful on open paths: a closed path has no free
ends, so :func:`marker_anchors` returns an empty list for it.
"""

import math

MARKER_TYPES = (
    "none",
    "arrow",        # open V of two lines (matches the legacy line arrow)
    "triangle",     # filled solid triangle
    "open_arrow",   # thinner open chevron
    "circle",       # filled dot
    "square",       # filled square
    "diamond",      # filled diamond
    "bar",          # perpendicular tick
)

_EPS = 6.0


def normalize_marker(value):
    """Coerce ``value`` to a known marker type."""
    if value is None:
        return "none"
    v = str(value).strip().lower()
    return v if v in MARKER_TYPES else "none"


def get_markers(stroke):
    """Return ``{"start": type, "end": type}`` for ``stroke``."""
    if not isinstance(stroke, dict):
        return {"start": "none", "end": "none"}
    start = normalize_marker(stroke.get("start_marker"))
    end = normalize_marker(stroke.get("end_marker"))
    if end == "none" and stroke.get("arrow_end"):
        end = "arrow"
    return {"start": start, "end": end}


def set_marker(stroke, end, marker_type):
    """Set the ``"start"`` or ``"end"`` marker on ``stroke`` (mutates+returns)."""
    if not isinstance(stroke, dict):
        return stroke
    key = "start_marker" if end == "start" else "end_marker"
    mt = normalize_marker(marker_type)
    if mt == "none":
        stroke.pop(key, None)
    else:
        stroke[key] = mt
    # Keep the legacy line-arrow flag in sync so old consumers agree.
    if end == "end":
        stroke["arrow_end"] = (mt != "none")
    return stroke


def cycle_marker(stroke, end, step=1):
    """Advance the marker on ``end`` by ``step`` types (mutates+returns)."""
    if not isinstance(stroke, dict):
        return stroke
    cur = get_markers(stroke)[end]
    idx = MARKER_TYPES.index(cur)
    nxt = MARKER_TYPES[(idx + step) % len(MARKER_TYPES)]
    return set_marker(stroke, end, nxt)


def _pts_close(a, b, eps=_EPS):
    try:
        return math.hypot(a[0] - b[0], a[1] - b[1]) <= eps
    except (TypeError, IndexError):
        return False


def stroke_is_closed(stroke):
    """True when the stroke's first and last anchors coincide."""
    segs = stroke.get("segs") if isinstance(stroke, dict) else None
    if not segs:
        return False
    try:
        return _pts_close(segs[0][0], segs[-1][3])
    except (TypeError, IndexError):
        return False


def _vec(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None
    return dx / length, dy / length


def marker_anchors(stroke):
    """Return ``[(end, point, ux, uy), ...]`` for open-path ends.

    ``ux, uy`` is the outward unit direction the marker should point along
    (away from the path) at that endpoint. Closed paths return ``[]``.
    """
    if not isinstance(stroke, dict):
        return []
    segs = stroke.get("segs") or []
    if not segs or stroke_is_closed(stroke):
        return []
    out = []
    # End: outward tangent is from the last control handle to the final point.
    try:
        seg = segs[-1]
        p_out = seg[3]
        d = _vec(seg[2], p_out) or _vec(seg[0], p_out)
        if d:
            out.append(("end", (float(p_out[0]), float(p_out[1])), d[0], d[1]))
    except (TypeError, IndexError):
        pass
    # Start: outward direction is the reverse of the first-segment tangent.
    try:
        seg = segs[0]
        p_out = seg[0]
        d = _vec(seg[1], p_out) or _vec(seg[3], p_out)
        if d:
            out.append(("start", (float(p_out[0]), float(p_out[1])), d[0], d[1]))
    except (TypeError, IndexError):
        pass
    return out


def marker_size(stroke, width=None):
    """Marker length in world units, scaled with the stroke weight."""
    if width is None:
        width = stroke.get("stroke_width", 3.0) if isinstance(stroke, dict) else 3.0
    try:
        return max(9.0, float(width or 3.0) * 3.5)
    except (TypeError, ValueError):
        return 9.0
