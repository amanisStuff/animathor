"""Model: document serialization (save/load) and export helpers."""
import json
import os
import xml.etree.ElementTree as ET


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


def _doc_payload(strokes, meta=None):
    return {
        "format": "animathor-document",
        "version": 1,
        "meta": meta or {},
        "strokes": _to_jsonable(strokes),
    }


def serialize_document(strokes, meta=None):
    return json.dumps(_doc_payload(strokes, meta), indent=2)


def serialize_document_xml(strokes, meta=None):
    root = ET.Element("athor", {"format": "animathor-document", "version": "1"})
    payload = ET.SubElement(root, "payload")
    # store full document payload as JSON text inside XML for fidelity
    payload.text = json.dumps(_doc_payload(strokes, meta), ensure_ascii=False)
    try:
        ET.indent(root, space="  ", level=0)
    except Exception:
        pass
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _keyify(obj):
    """Convert JSON-loaded corner/width keys back to (i, name) tuples where needed."""
    if isinstance(obj, list):
        return [_keyify(x) for x in obj]
    if isinstance(obj, dict):
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
            out[nk] = _keyify(v)
        return out
    return obj


def _strokes_from_data(data):
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

    return [_keyify(tuples(s)) if isinstance(s, dict) else s for s in strokes]


def deserialize_document(text):
    data = json.loads(text)
    return _strokes_from_data(data)


def deserialize_document_xml(text):
    root = ET.fromstring(text)
    payload = root.find("payload")
    if payload is None or payload.text is None:
        # fallback: try legacy/nested forms
        strokes_el = root.find("strokes")
        if strokes_el is not None and strokes_el.text:
            return _strokes_from_data(json.loads(strokes_el.text))
        return _strokes_from_data({})
    data = json.loads(payload.text)
    return _strokes_from_data(data)


def _is_athors_path(path):
    return str(path).lower().endswith(".athors")


def save_document(path, strokes, meta=None):
    if _is_athors_path(path):
        text = serialize_document_xml(strokes, meta)
    else:
        text = serialize_document(strokes, meta)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_document(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if _is_athors_path(path):
        try:
            return deserialize_document_xml(text)
        except Exception:
            # fallback in case content format differs
            return deserialize_document(text)
    # auto-detect XML vs JSON
    stripped = text.lstrip()
    if stripped.startswith("<"):
        try:
            return deserialize_document_xml(text)
        except Exception:
            pass
    return deserialize_document(text)
