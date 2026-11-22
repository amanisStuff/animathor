"""Model: repeating pattern fills.

A pattern fill is stored on a stroke as ``fill_pattern``::

    {"type": "stripes"|"dots"|"checks"|"grid"|"zigzag",
     "fg": [r, g, b, a], "bg": [r, g, b, a] or None,
     "size": float, "angle": float}

Colours use the same 0..1 float RGBA convention as gradients. Patterns are
additive: when a stroke has no ``fill_pattern`` the renderer is byte-for-byte
identical to before.
"""

PATTERN_TYPES = ("stripes", "dots", "checks", "grid", "zigzag")

# Neutral defaults that read well on top of any artwork.
DEFAULT_PATTERN_FG = (0.22, 0.34, 0.58, 1.0)
DEFAULT_PATTERN_BG = (1.0, 1.0, 1.0, 1.0)
DEFAULT_PATTERN_SIZE = 14.0


def _rgba(value, fallback):
    try:
        vals = list(value)
    except TypeError:
        return list(fallback)
    if len(vals) == 3:
        vals = vals + [1.0]
    if len(vals) < 4:
        return list(fallback)
    out = []
    for v in vals[:4]:
        try:
            out.append(max(0.0, min(1.0, float(v))))
        except (TypeError, ValueError):
            return list(fallback)
    return out


def is_fill_pattern(fill):
    """True when ``fill`` is a well-formed pattern dict."""
    return (isinstance(fill, dict)
            and fill.get("type") in PATTERN_TYPES
            and isinstance(fill.get("fg", [0, 0, 0, 1]), (list, tuple)))


def new_pattern(ptype="stripes", fg=None, bg=None, size=DEFAULT_PATTERN_SIZE,
                angle=0.0):
    """Return a normalised pattern dict."""
    if ptype not in PATTERN_TYPES:
        ptype = "stripes"
    return {
        "type": ptype,
        "fg": _rgba(DEFAULT_PATTERN_FG if fg is None else fg, DEFAULT_PATTERN_FG),
        "bg": None if bg is None else _rgba(bg, DEFAULT_PATTERN_BG),
        "size": max(2.0, float(size or DEFAULT_PATTERN_SIZE)),
        "angle": float(angle or 0.0),
    }


def normalize_pattern(pat):
    """Coerce a loose dict into a valid pattern (or ``None``)."""
    if not isinstance(pat, dict) or pat.get("type") not in PATTERN_TYPES:
        return None
    return new_pattern(pat.get("type"), pat.get("fg"), pat.get("bg"),
                       pat.get("size"), pat.get("angle"))


def get_fill_pattern(stroke):
    """Return the stroke's pattern dict, or ``None``."""
    if not isinstance(stroke, dict):
        return None
    return normalize_pattern(stroke.get("fill_pattern"))


def set_pattern_fill(stroke, pattern):
    """Return ``stroke`` with a pattern fill (mutates and returns)."""
    if not isinstance(stroke, dict):
        return stroke
    pat = normalize_pattern(pattern)
    stroke["fill_pattern"] = pat
    if pat is not None:
        stroke["fill_color"] = None
        stroke["fill_gradient"] = None
    return stroke


def clear_pattern_fill(stroke):
    """Remove any pattern fill (mutates and returns)."""
    if isinstance(stroke, dict):
        stroke.pop("fill_pattern", None)
    return stroke


def cycle_pattern_type(pattern, step=1):
    """Return ``pattern`` with its motif advanced by ``step`` entries."""
    pat = normalize_pattern(pattern) or new_pattern()
    idx = PATTERN_TYPES.index(pat["type"])
    pat["type"] = PATTERN_TYPES[(idx + step) % len(PATTERN_TYPES)]
    return pat


def pattern_has_fill(stroke):
    """True when the stroke carries a pattern fill."""
    return get_fill_pattern(stroke) is not None
