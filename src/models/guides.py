"""Model: pages grid, ruler guides and snapping helpers.

The canvas works in "world" coordinates; the view applies a zoom/pan transform.
These helpers are pure math so both the renderer (overlay) and the controller
(interaction/snapping) can share one definition.

A guide is a plain dict ``{"axis": "x"|"y", "pos": float}`` where ``axis="x"``
is a vertical guide at world x = pos and ``axis="y"`` is horizontal. Guides are
serialised with the document like any other generic value.
"""


def grid_positions(low, high, spacing, origin=0.0):
    """Return grid line coordinates in ``[low, high]`` for ``spacing``.

    Values are inclusive of the first line at or above ``low``. A non-positive
    spacing returns an empty list so callers never divide by zero.
    """
    if spacing is None or spacing <= 0 or high < low:
        return []
    import math
    first = math.ceil((low - origin) / spacing)
    last = math.floor((high - origin) / spacing)
    return [origin + i * spacing for i in range(first, last + 1)]


def ruler_ticks(low, high, spacing, min_pixels=48.0, zoom=1.0):
    """Return a visual tick step so ruler labels never collide.

    Starts at ``spacing`` and doubles until at least ``min_pixels`` screen
    pixels separate ticks at the current ``zoom``.
    """
    step = float(spacing) if spacing and spacing > 0 else 1.0
    z = float(zoom) if zoom and zoom > 0 else 1.0
    while step * z < min_pixels:
        step *= 2.0
    return step


def snap_value(value, step, threshold=None):
    """Snap ``value`` to the nearest multiple of ``step``.

    ``threshold`` (in the same units) limits how far a snap may move the value;
    ``None`` snaps unconditionally.
    """
    if not step or step <= 0:
        return value
    snapped = round(value / step) * step
    if threshold is not None and abs(snapped - value) > threshold:
        return value
    return snapped


def snap_point_to_grid(point, spacing, origin=(0.0, 0.0), threshold=None):
    """Snap a 2D point to the nearest grid intersection."""
    return (snap_value(point[0], spacing, threshold) if spacing else point[0],
            snap_value(point[1], spacing, threshold) if spacing else point[1])


def _guide_step(point, guide):
    """Distance from ``point`` to ``guide`` along the guide's axis."""
    if guide.get("axis") == "x":
        return point[0] - float(guide.get("pos", 0.0))
    return point[1] - float(guide.get("pos", 0.0))


def snap_to_guides(point, guides, threshold):
    """Snap ``point`` to the closest guide within ``threshold``.

    Returns ``(point, kind)`` where ``kind`` is ``"guide_x"``, ``"guide_y"``
    or ``None`` when nothing is close enough. Only the dominant axis snaps.
    """
    best = None
    best_dist = float(threshold)
    kind = None
    for g in guides or ():
        try:
            d = _guide_step(point, g)
        except (TypeError, ValueError):
            continue
        if abs(d) <= best_dist:
            best_dist = abs(d)
            best = g
            kind = "guide_x" if g.get("axis") == "x" else "guide_y"
    if best is None:
        return point, None
    if best.get("axis") == "x":
        return (float(best["pos"]), point[1]), kind
    return (point[0], float(best["pos"])), kind


def snap_point(point, grid_size=None, guides=None, threshold=None,
               use_grid=False):
    """Snap a point to guides first, then the grid.

    Guides win because they are explicit user intent. Returns ``(point, kind)``
    with ``kind`` describing what snapped (``"guide_x"``, ``"guide_y"``,
    ``"grid"`` or ``None``).
    """
    if guides and threshold is not None:
        snapped, kind = snap_to_guides(point, guides, threshold)
        if kind:
            return snapped, kind
    if use_grid and grid_size and grid_size > 0:
        return snap_point_to_grid(point, grid_size, threshold=threshold), "grid"
    return point, None


def add_guide(guides, axis, pos):
    """Return a new guide list with one guide appended."""
    out = list(guides or ())
    out.append({"axis": "x" if axis == "x" else "y", "pos": float(pos)})
    return out


def move_guide(guides, index, pos):
    """Return a new guide list with guide ``index`` moved to ``pos``."""
    out = [dict(g) for g in (guides or ())]
    if 0 <= index < len(out):
        out[index]["pos"] = float(pos)
    return out


def remove_guide(guides, index):
    """Return a new guide list without guide ``index``."""
    out = list(guides or ())
    if 0 <= index < len(out):
        out.pop(index)
    return out


def hit_guide(point, guides, threshold):
    """Return the index of the guide closest to ``point`` within threshold."""
    best = None
    best_dist = float(threshold)
    for i, g in enumerate(guides or ()):
        try:
            d = abs(_guide_step(point, g))
        except (TypeError, ValueError):
            continue
        if d <= best_dist:
            best_dist = d
            best = i
    return best
