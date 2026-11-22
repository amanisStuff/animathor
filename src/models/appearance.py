"""Model: appearance properties - object opacity, blend modes, drop shadows.

These are per-stroke properties layered on top of the base fill/stroke color.
Defaults (opacity 1.0, blend ``normal``, no shadow) leave existing artwork
visually unchanged, which keeps old documents and deterministic previews stable.
"""
import math

# Blend modes ordered from most to least common. Names match CSS compositing
# terminology so SVG/PDF concepts map cleanly.
BLEND_MODES = (
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "hard-light", "soft-light",
    "difference", "exclusion", "hue", "saturation", "color", "luminosity",
)

DEFAULT_APPEARANCE = {"opacity": 1.0, "blend_mode": "normal", "shadow": None}


def normalize_opacity(value, default=1.0):
    """Clamp an opacity value to 0..1 (defaults on invalid/NaN input)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(v):
        return default
    return max(0.0, min(1.0, v))


def normalize_blend_mode(value):
    """Return a valid blend-mode name, falling back to ``normal``."""
    mode = str(value or "normal").strip().lower().replace("_", "-")
    return mode if mode in BLEND_MODES else "normal"


def _normalize_color(value, default):
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]),
                    float(value[3]) if len(value) > 3 else 1.0)
        except (TypeError, ValueError):
            pass
    return default


def normalize_shadow(value):
    """Normalize a drop-shadow spec into ``{dx, dy, blur, color, opacity}``.

    Returns ``None`` for falsy/invalid values (meaning "no shadow"). Blur is
    clamped to a sane 0..64px range; offsets are clamped to +/-256px.
    """
    if not isinstance(value, dict):
        return None

    def num(key, default, lo, hi):
        try:
            v = float(value.get(key, default))
        except (TypeError, ValueError):
            v = default
        if not math.isfinite(v):
            v = default
        return max(lo, min(hi, v))

    return {
        "dx": num("dx", 4.0, -256.0, 256.0),
        "dy": num("dy", 4.0, -256.0, 256.0),
        "blur": num("blur", 4.0, 0.0, 64.0),
        "opacity": normalize_opacity(value.get("opacity", 0.4), 0.4),
        "color": _normalize_color(value.get("color"), (0.0, 0.0, 0.0, 1.0)),
    }


def get_appearance(stroke):
    """Return normalized appearance fields for ``stroke``."""
    if not isinstance(stroke, dict):
        return dict(DEFAULT_APPEARANCE)
    return {
        "opacity": normalize_opacity(stroke.get("opacity", 1.0), 1.0),
        "blend_mode": normalize_blend_mode(stroke.get("blend_mode", "normal")),
        "shadow": normalize_shadow(stroke.get("shadow")),
    }


def stroke_has_appearance(stroke):
    """True when ``stroke`` needs non-default appearance rendering."""
    a = get_appearance(stroke)
    return a["opacity"] < 1.0 or a["blend_mode"] != "normal" or a["shadow"] is not None


def set_appearance(stroke, **fields):
    """Return a shallow copy of ``stroke`` with normalized appearance fields.

    Accepted keyword fields: ``opacity``, ``blend_mode``, ``shadow``. Other
    fields are ignored so callers can pass a whole state dict safely.
    """
    out = dict(stroke) if isinstance(stroke, dict) else {}
    app = get_appearance(out)
    if "opacity" in fields:
        app["opacity"] = normalize_opacity(fields["opacity"], app["opacity"])
    if "blend_mode" in fields:
        app["blend_mode"] = normalize_blend_mode(fields["blend_mode"])
    if "shadow" in fields:
        app["shadow"] = normalize_shadow(fields["shadow"])
    out["opacity"] = app["opacity"]
    out["blend_mode"] = app["blend_mode"]
    out["shadow"] = app["shadow"]
    return out


def apply_opacity(color, opacity):
    """Return ``color`` with its alpha multiplied by ``opacity``.

    Returns ``None`` unchanged so "no color" stays "no color".
    """
    if color is None:
        return None
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        try:
            alpha = float(color[3]) if len(color) > 3 else 1.0
            return (float(color[0]), float(color[1]), float(color[2]),
                    alpha * normalize_opacity(opacity, 1.0))
        except (TypeError, ValueError):
            pass
    return color
