"""Controller: text entry commit (extracted from app_controller for SRP)."""


def commit(ctx):
    """Commit the active text buffer as an editable outline stroke."""
    if ctx.text_entry is None:
        return False
    content = str(ctx.text_entry.get("text", ""))
    edit_index = ctx.text_entry.get("edit_index")
    if content.strip():
        ctx.push_undo()
        col = ctx.hsv_to_rgb(ctx.picker_h, ctx.picker_s, ctx.picker_v)
        color = (col[0], col[1], col[2], 1.0)
        old_tp = None
        if edit_index is not None and 0 <= edit_index < len(ctx.strokes) and isinstance(ctx.strokes[edit_index], dict):
            old_tp = ctx.strokes[edit_index].get("text_path")
        if isinstance(old_tp, dict) and old_tp.get("segs"):
            st = ctx.new_text_stroke(content, ctx.text_entry["x"], ctx.text_entry["y"],
                                     ctx.text_entry["family"], ctx.text_entry["size"], color=color,
                                     path_segs=old_tp.get("segs"), path_offset=old_tp.get("offset", 0.0))
        else:
            st = ctx.new_text_stroke(content, ctx.text_entry["x"], ctx.text_entry["y"],
                                     ctx.text_entry["family"], ctx.text_entry["size"], color=color)
        if edit_index is not None and 0 <= edit_index < len(ctx.strokes):
            for _k in ("opacity", "blend_mode", "shadow", "hidden", "locked"):
                if _k in ctx.strokes[edit_index]:
                    st[_k] = ctx.strokes[edit_index][_k]
            ctx.strokes[edit_index] = st
            ctx.selected_strokes = {edit_index}
        else:
            ctx.strokes.append(st)
            ctx.selected_strokes = {len(ctx.strokes) - 1}
        ctx.selected_point = None
        ctx.selected_curve = None
        ctx.selected_curves.clear()
    ctx.text_entry = None
    return True
