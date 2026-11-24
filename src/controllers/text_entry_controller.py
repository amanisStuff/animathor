"""Controller: text entry commit (extracted from app_controller for SRP).

Operates directly on typed AppState substates (Phase 1: no ctx bag). Services
(``push_undo``, ``hsv_to_rgb``, ``new_text_stroke``) are passed explicitly.
"""


def commit(selection, document, ui, push_undo, hsv_to_rgb, new_text_stroke):
    """Commit the active text buffer as an editable outline stroke."""
    text_entry = ui.text_entry
    if text_entry is None:
        return False
    content = str(text_entry.get("text", ""))
    edit_index = text_entry.get("edit_index")
    strokes = document.strokes
    if content.strip():
        push_undo()
        col = hsv_to_rgb(ui.picker_h, ui.picker_s, ui.picker_v)
        color = (col[0], col[1], col[2], 1.0)
        old_tp = None
        if edit_index is not None and 0 <= edit_index < len(strokes) and isinstance(strokes[edit_index], dict):
            old_tp = strokes[edit_index].get("text_path")
        if isinstance(old_tp, dict) and old_tp.get("segs"):
            st = new_text_stroke(content, text_entry["x"], text_entry["y"],
                                 text_entry["family"], text_entry["size"], color=color,
                                 path_segs=old_tp.get("segs"), path_offset=old_tp.get("offset", 0.0))
        else:
            st = new_text_stroke(content, text_entry["x"], text_entry["y"],
                                 text_entry["family"], text_entry["size"], color=color)
        if edit_index is not None and 0 <= edit_index < len(strokes):
            for _k in ("opacity", "blend_mode", "shadow", "hidden", "locked"):
                if _k in strokes[edit_index]:
                    st[_k] = strokes[edit_index][_k]
            strokes[edit_index] = st
            selection.selected_strokes = {edit_index}
        else:
            strokes.append(st)
            selection.selected_strokes = {len(strokes) - 1}
        selection.selected_point = None
        selection.selected_curve = None
        selection.selected_curves.clear()
    ui.text_entry = None
    return True
