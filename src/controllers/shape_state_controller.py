"""Controller: shape-state/library helpers (extracted from app_controller for SRP)."""
import copy

from models.geometry import combined_bbox
from models.strokes import translate_stroke


def _stroke_kind_label(stroke):
    """Short human-readable kind for a stroke, used in the layer list."""
    if not isinstance(stroke, dict):
        return "Path"
    if stroke.get("is_group"):
        return "Group"
    if stroke.get("shape_kind"):
        return str(stroke["shape_kind"]).capitalize()
    if stroke.get("text"):
        return "Text"
    if stroke.get("fill_color") is not None and stroke.get("stroke_width", 3.0) == 0:
        return "Shape"
    return "Path"


def _capture_shape_state(strokes, sel, shape_states, counter):
    """Save the selected strokes as a new shape state in the library.

    Geometry is normalized to the selection bbox top-left so instances can be
    placed by translation alone. Returns ``(state_id, next_counter)``.
    """
    counter = int(counter) + 1
    sid = f"shape{counter}"
    def_strokes = []
    idxs = [i for i in sel if 0 <= i < len(strokes) and isinstance(strokes[i], dict)]
    for i in idxs:
        st = copy.deepcopy(strokes[i])
        for k in ("symbol_id", "symbol_is_master", "symbol_instance_id",
                  "shape_state_id", "shape_state_is_master", "shape_state_instance_id"):
            st.pop(k, None)
        def_strokes.append(st)
    bb = combined_bbox(strokes, idxs) if idxs else None
    ox, oy = (float(bb[0]), float(bb[1])) if bb else (0.0, 0.0)
    norm_def = []
    for st in def_strokes:
        norm_def.append(translate_stroke(st, -ox, -oy))
    shape_states[sid] = {"name": f"Shape State {counter}", "strokes": norm_def, "origin": [ox, oy]}
    for i in idxs:
        strokes[i]["shape_state_id"] = sid
        strokes[i]["shape_state_is_master"] = True
        strokes[i]["shape_state_instance_id"] = f"{sid}:master"
    return sid, counter


def _insert_shape_state(strokes, shape_states, counter, sel):
    """Insert a library shape state as new asset strokes. Returns ``(indices, counter)``."""
    sid = None
    for i in sorted(sel):
        if 0 <= i < len(strokes) and isinstance(strokes[i], dict) and strokes[i].get("shape_state_id"):
            sid = strokes[i].get("shape_state_id")
            break
    if sid is None and shape_states:
        sid = list(shape_states.keys())[-1]
    sdef = shape_states.get(sid) if sid else None
    def_strokes = (sdef or {}).get("strokes") if isinstance(sdef, dict) else None
    indices = []
    if not (sid and isinstance(def_strokes, list) and def_strokes):
        return indices, counter
    counter = int(counter) + 1
    inst_id = f"{sid}:i{counter}"
    base = len(strokes)
    offx = offy = 24.0
    idxs = [i for i in sel if 0 <= i < len(strokes)]
    if idxs:
        bb = combined_bbox(strokes, idxs)
        if bb:
            offx = (bb[2] - bb[0]) * 0.2 + 24.0
            offy = (bb[3] - bb[1]) * 0.2 + 24.0
    origin = sdef.get("origin") if isinstance(sdef, dict) else None
    try:
        ox = float(origin[0]) if isinstance(origin, (list, tuple)) and len(origin) > 0 else 0.0
        oy = float(origin[1]) if isinstance(origin, (list, tuple)) and len(origin) > 1 else 0.0
    except Exception:
        ox = oy = 0.0
    for st in copy.deepcopy(def_strokes):
        if not isinstance(st, dict):
            continue
        nst = translate_stroke(st, ox + offx, oy + offy)
        nst["shape_state_id"] = sid
        nst["shape_state_is_master"] = False
        nst["shape_state_instance_id"] = inst_id
        strokes.append(nst)
        indices.append(base)
        base += 1
    return indices, counter


def _delete_shape_state(shape_states, sid, strokes):
    """Remove a library state and detach strokes that reference it."""
    if sid and sid in shape_states:
        del shape_states[sid]
    touched = False
    for i in range(len(strokes)):
        st = strokes[i]
        if isinstance(st, dict) and st.get("shape_state_id") == sid:
            for k in ("shape_state_id", "shape_state_is_master", "shape_state_instance_id"):
                st.pop(k, None)
            touched = True
    return touched
