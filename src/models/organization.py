"""Model: organization helpers - per-object visibility and locking.

``hidden`` objects are not rendered or hit-tested. ``locked`` objects render
normally but cannot be selected/edited on the canvas. Defaults (both False)
leave existing artwork and deterministic previews unchanged. Stacking order
(list position) and grouping are handled by the controller/document model.
"""


def is_hidden(stroke):
    """True when ``stroke`` is marked hidden."""
    return bool(isinstance(stroke, dict) and stroke.get("hidden", False))


def is_locked(stroke):
    """True when ``stroke`` is marked locked."""
    return bool(isinstance(stroke, dict) and stroke.get("locked", False))


def is_selectable(stroke):
    """True when ``stroke`` may be selected on the canvas."""
    return not is_hidden(stroke) and not is_locked(stroke)


def set_hidden(stroke, hidden):
    """Return a shallow copy of ``stroke`` with its hidden flag set."""
    out = dict(stroke) if isinstance(stroke, dict) else {}
    out["hidden"] = bool(hidden)
    return out


def set_locked(stroke, locked):
    """Return a shallow copy of ``stroke`` with its locked flag set."""
    out = dict(stroke) if isinstance(stroke, dict) else {}
    out["locked"] = bool(locked)
    return out


def toggle_hidden(stroke):
    """Return a copy of ``stroke`` with its hidden flag inverted."""
    return set_hidden(stroke, not is_hidden(stroke))


def toggle_locked(stroke):
    """Return a copy of ``stroke`` with its locked flag inverted."""
    return set_locked(stroke, not is_locked(stroke))


def filter_selectable(strokes, indices):
    """Return sorted ``indices`` excluding hidden/locked strokes."""
    out = []
    for i in indices:
        if 0 <= i < len(strokes) and is_selectable(strokes[i]):
            out.append(i)
    return out


def visible_indices(strokes):
    """Return indices of strokes that are not hidden, topmost last."""
    return [i for i, s in enumerate(strokes) if not is_hidden(s)]


# --- Grouping -------------------------------------------------------------
#
# Groups use a flat, non-destructive model: every member stroke stores a
# shared ``group_id`` string. Nothing is nested or reordered, so rendering,
# hit-testing and export keep operating on the same flat stroke list. Group
# membership is purely a selection/editing convenience.

_group_counter = 0


def is_grouped(stroke):
    """True when ``stroke`` belongs to a group."""
    return bool(isinstance(stroke, dict) and stroke.get("group_id"))


def group_id_of(stroke):
    """Return the stroke's group id, or ``None``."""
    if not isinstance(stroke, dict):
        return None
    gid = stroke.get("group_id")
    return str(gid) if gid else None


def new_group_id():
    """Return a fresh, process-unique group id."""
    global _group_counter
    _group_counter += 1
    return "grp-%d" % _group_counter


def assign_group(stroke, group_id):
    """Return a copy of ``stroke`` belonging to ``group_id``."""
    out = dict(stroke) if isinstance(stroke, dict) else {}
    out["group_id"] = str(group_id)
    return out


def clear_group(stroke):
    """Return a copy of ``stroke`` with no group membership."""
    out = dict(stroke) if isinstance(stroke, dict) else {}
    out.pop("group_id", None)
    return out


def group_members(strokes, group_id):
    """Return sorted indices of strokes in ``group_id``."""
    if not group_id:
        return []
    gid = str(group_id)
    return [i for i, s in enumerate(strokes) if group_id_of(s) == gid]


def expand_group_selection(strokes, indices):
    """Grow ``indices`` so that touching any member selects the whole group."""
    out = set()
    for i in indices:
        out.add(i)
        if 0 <= i < len(strokes):
            gid = group_id_of(strokes[i])
            if gid:
                out.update(group_members(strokes, gid))
    return out


def group_selection(strokes, indices, group_id=None):
    """Return new ``strokes`` with ``indices`` sharing a fresh group id.

    Returns ``(strokes, group_id)``; ``group_id`` is ``None`` when fewer than
    two valid indices are supplied (a group needs at least two members).
    """
    valid = [i for i in indices if 0 <= i < len(strokes)]
    if len(valid) < 2:
        return strokes, None
    gid = str(group_id) if group_id else new_group_id()
    out = list(strokes)
    for i in valid:
        out[i] = assign_group(out[i], gid)
    return out, gid


def ungroup_selection(strokes, indices):
    """Return new ``strokes`` with group membership removed from ``indices``."""
    out = list(strokes)
    for i in indices:
        if 0 <= i < len(out):
            out[i] = clear_group(out[i])
    return out
