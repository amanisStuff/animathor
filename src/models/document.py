"""Model: document serialization (save/load) and export helpers.

The native format is a JSON payload (optionally wrapped in an XML ``.athors``
file). Two details matter for round-trip fidelity:

* strokes carry ``set`` fields (``corner_anchors``, ``hidden_segs``) whose
  elements are ``(segment_index, anchor_name)`` tuples; JSON has neither sets
  nor tuple keys, so they use an explicit tagged representation.
* ``meta.view`` records the camera and is restored on open.
"""
import ast
import json
import os
import xml.etree.ElementTree as ET

_SET_MARKER = "__animathor_set__"
_SET_FIELDS = ("corner_anchors", "hidden_segs")


def _to_jsonable(obj):
    if isinstance(obj, (set, frozenset)):
        # Stable order keeps serialization deterministic.
        return {_SET_MARKER: [_to_jsonable(x) for x in sorted(obj, key=repr)]}
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


def _doc_payload(strokes, meta=None):
    return {
        "format": "animathor-document",
        "version": 2,
        "meta": _to_jsonable(meta or {}),
        "strokes": _to_jsonable(strokes),
    }


def serialize_document(strokes, meta=None):
    return json.dumps(_doc_payload(strokes, meta), indent=2)


def serialize_document_xml(strokes, meta=None):
    root = ET.Element("athor", {"format": "animathor-document", "version": "2"})
    payload = ET.SubElement(root, "payload")
    # store full document payload as JSON text inside XML for fidelity
    payload.text = json.dumps(_doc_payload(strokes, meta), ensure_ascii=False)
    try:
        ET.indent(root, space="  ", level=0)
    except Exception:
        pass
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _freeze(obj):
    """Turn JSON lists back into hashable tuples (for set elements)."""
    if isinstance(obj, list):
        return tuple(_freeze(x) for x in obj)
    if isinstance(obj, dict):
        return {k: _freeze(v) for k, v in obj.items()}
    return obj


def _legacy_set(value):
    """Recover a set written by older versions as ``str(a_set)``."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return value
    try:
        parsed = ast.literal_eval(text)
    except Exception:
        return value
    if isinstance(parsed, (set, frozenset)):
        return set(_freeze(x) for x in parsed)
    return value


def _keyify(obj):
    """Convert JSON-loaded corner/width keys back to ``(i, name)`` tuples."""
    if isinstance(obj, list):
        return [_keyify(x) for x in obj]
    if isinstance(obj, dict):
        if _SET_MARKER in obj:
            values = obj[_SET_MARKER]
            if isinstance(values, list):
                return set(_freeze(_keyify(x)) for x in values)
        out = {}
        for k, v in obj.items():
            nk = k
            # stroke-level maps use "seg_i,anchor_name" string keys (or str(tuple) legacy)
            if isinstance(k, str) and "," in k:
                s = k.strip()
                if s.startswith("(") and s.endswith(")"):
                    s = s[1:-1]
                parts = [p.strip().strip("'\"") for p in s.split(",", 1)]
                if len(parts) == 2:
                    try:
                        nk = (int(parts[0]), parts[1])
                    except Exception:
                        nk = k
            value = _keyify(v)
            if k in _SET_FIELDS:
                value = _legacy_set(value)
            out[nk] = value
        return out
    return obj


def _restore_stroke_like(obj):
    """Reconstruct a stroke dict (or nested structure) from JSON-loaded form."""
    def tuples(o):
        if isinstance(o, list):
            # point or seg: [[x,y],[x,y],[x,y],[x,y]] or [x,y]
            if len(o) == 2 and all(isinstance(x, (int, float)) for x in o):
                return (float(o[0]), float(o[1]))
            return tuple(tuples(x) for x in o)
        if isinstance(o, dict):
            return {k: tuples(v) for k, v in o.items()}
        return o
    if isinstance(obj, dict):
        return tuples(_keyify(obj))
    return obj


def _strokes_from_data(data):
    if isinstance(data, list):
        strokes = data
    elif isinstance(data, dict):
        strokes = data.get("strokes", [])
    else:
        strokes = []

    # Keyify first (set markers are JSON lists), then rebuild point tuples.
    return [_restore_stroke_like(s) if isinstance(s, dict) else s for s in strokes]


def _meta_from_data(data):
    if isinstance(data, dict):
        meta = data.get("meta") or {}
        if not isinstance(meta, dict):
            return {}
        meta = dict(meta)
        # Restore stroke-like data stored in meta (e.g. symbol/component definitions).
        try:
            syms = meta.get("symbols")
            if isinstance(syms, dict):
                out_syms = {}
                for sid, sdef in syms.items():
                    if not isinstance(sdef, dict):
                        continue
                    nd = dict(sdef)
                    sstrokes = nd.get("strokes")
                    if isinstance(sstrokes, list):
                        nd["strokes"] = [_restore_stroke_like(s) for s in sstrokes]
                    out_syms[str(sid)] = nd
                meta["symbols"] = out_syms
        except Exception:
            pass
        return meta
    return {}


def deserialize_document_with_meta(text):
    data = json.loads(text)
    return _strokes_from_data(data), _meta_from_data(data)


def deserialize_document_xml_with_meta(text):
    root = ET.fromstring(text)
    payload = root.find("payload")
    if payload is None or payload.text is None:
        # fallback: try legacy/nested forms
        strokes_el = root.find("strokes")
        if strokes_el is not None and strokes_el.text:
            data = json.loads(strokes_el.text)
            return _strokes_from_data(data), _meta_from_data(data)
        return [], {}
    data = json.loads(payload.text)
    return _strokes_from_data(data), _meta_from_data(data)


def deserialize_document(text):
    return deserialize_document_with_meta(text)[0]


def deserialize_document_xml(text):
    return deserialize_document_xml_with_meta(text)[0]


def _is_athors_path(path):
    return str(path).lower().endswith(".athors")


def save_document(path, strokes, meta=None):
    if _is_athors_path(path):
        text = serialize_document_xml(strokes, meta)
    else:
        text = serialize_document(strokes, meta)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_document_with_meta(path):
    """Return ``(strokes, meta)`` so callers can restore camera state."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if _is_athors_path(path):
        try:
            return deserialize_document_xml_with_meta(text)
        except Exception:
            # fallback in case content format differs
            return deserialize_document_with_meta(text)
    # auto-detect XML vs JSON
    stripped = text.lstrip()
    if stripped.startswith("<"):
        try:
            return deserialize_document_xml_with_meta(text)
        except Exception:
            pass
    return deserialize_document_with_meta(text)


def load_document(path):
    return load_document_with_meta(path)[0]
