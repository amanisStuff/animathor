"""Text size / text-on-path actions in the selection panel."""
import pygame
from models.text import update_text_stroke


def text_actions_click(tools, selection, document, state, event, push_undo):
    if tools.tool_mode == "selection" and selection.selected_strokes and any(
        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for k in ("text_size_minus_rect", "text_size_plus_rect")):
        _ti = next(iter(sorted(selection.selected_strokes)), None)
        _key = "text_size_plus_rect" if state.get(
            "text_size_plus_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) \
            else "text_size_minus_rect"
        if _ti is not None and 0 <= _ti < len(document.strokes) and \
                isinstance(document.strokes[_ti], dict) and document.strokes[_ti].get("is_text"):
            push_undo()
            _sz = float(document.strokes[_ti].get("font_size", 36.0))
            _sz = max(4.0, min(400.0, _sz + (2.0 if _key == "text_size_plus_rect" else -2.0)))
            document.strokes[_ti] = update_text_stroke(document.strokes[_ti], font_size=_sz)
            tools.text_size = _sz
    elif tools.tool_mode == "selection" and state.get("text_on_path_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        sel = [i for i in sorted(selection.selected_strokes) if 0 <= i < len(document.strokes)]
        if len(sel) == 2:
            a, b = document.strokes[sel[0]], document.strokes[sel[1]]
            text_i = path_i = None
            if isinstance(a, dict) and a.get("is_text") and not (isinstance(b, dict) and b.get("is_text")):
                text_i, path_i = sel[0], sel[1]
            elif isinstance(b, dict) and b.get("is_text") and not (isinstance(a, dict) and a.get("is_text")):
                text_i, path_i = sel[1], sel[0]
            if text_i is not None and path_i is not None:
                try:
                    from models.strokes import segs_of as _segs_of_tp
                    psegs = list(_segs_of_tp(document.strokes[path_i]) or [])
                except Exception:
                    psegs = list((document.strokes[path_i] or {}).get("segs") or [])
                if psegs:
                    try:
                        from models.text import set_text_path as _set_text_path
                        push_undo()
                        document.strokes[text_i] = _set_text_path(document.strokes[text_i], psegs, 0.0)
                        selection.selected_strokes = {text_i}
                        selection.selected_point = None; selection.selected_curve = None; selection.selected_curves.clear()
                    except Exception:
                        pass
    elif tools.tool_mode == "selection" and state.get("text_off_path_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        if len(selection.selected_strokes) == 1:
            _ti = next(iter(selection.selected_strokes))
            if 0 <= _ti < len(document.strokes) and isinstance(document.strokes[_ti], dict) and document.strokes[_ti].get("is_text") and document.strokes[_ti].get("text_path"):
                try:
                    from models.text import clear_text_path as _clear_text_path
                    push_undo()
                    document.strokes[_ti] = _clear_text_path(document.strokes[_ti])
                except Exception:
                    pass
    return False
