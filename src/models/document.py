"""Model: document serialization (save/load) and export helpers."""
import json


def _to_jsonable(obj):
    if isinstance(obj, tuple):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # numpy scalars etc
    try:
        return float(obj)
    except Exception:
        return str(obj)


def serialize_document(strokes, meta=None):
    doc = {
        "format": "animathor-document",
        "version": 1,
        "meta": meta or {},
        "strokes": _to_jsonable(strokes),
    }
    return json.dumps(doc, indent=2)


def _keyify(obj):
    """Convert JSON-loaded corner/width keys 'i,name' back to (i, name) tuples where needed."""
    if isinstance(obj, list):
        return [_keyify(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            nk = k
            # stroke-level maps use "seg_i,anchor_name" string keys
            if "," in k:
                parts = k.split(",")
                if len(parts) == 2:
                    try:
                        nk = (int(parts[0]), parts[1])
                    except Exception:
                        nk = k
            out[nk] = _keyify(v)
        return out
    return obj


def deserialize_document(text):
    data = json.loads(text)
    if isinstance(data, list):
        strokes = data
    elif isinstance(data, dict):
        strokes = data.get("strokes", [])
    else:
        strokes = []
    # convert seg point lists back to tuples for consistency
    def tuples(obj):
        if isinstance(obj, list):
            # point or seg: [[x,y],[x,y],[x,y],[x,y]] or [x,y]
            if len(obj) == 2 and all(isinstance(x, (int, float)) for x in obj):
                return (float(obj[0]), float(obj[1]))
            return tuple(tuples(x) for x in obj)
        if isinstance(obj, dict):
            return {k: tuples(v) for k, v in obj.items()}
        return obj
    strokes = [_keyify(tuples(s)) if isinstance(s, dict) else s for s in strokes]
    return strokes


def save_document(path, strokes, meta=None):
    with open(path, "w", encoding="utf-8") as f:
        f.write(serialize_document(strokes, meta))


def load_document(path):
    with open(path, "r", encoding="utf-8") as f:
        return deserialize_document(f.read())
