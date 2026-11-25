"""Text-edit clicks in the transform/selection panel."""
import pygame
from models.text import update_text_stroke


def transform_text_click(tools, selection, document, drag, ui, state, event,
                         push_undo, font_families):
    if tools.tool_mode == "selection" and selection.selected_strokes and state.get(
        "text_edit_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _ti = next(iter(sorted(selection.selected_strokes)), None)
        if _ti is not None and 0 <= _ti < len(document.strokes) and \
                isinstance(document.strokes[_ti], dict) and document.strokes[_ti].get("is_text"):
            _ts = document.strokes[_ti]
            # Re-open the text editor seeded with existing content.
            tools.tool_mode = "draw"; tools.draw_tool = "text"
            drag.drawing = False; drag.current_points = []
            tools.text_family = _ts.get("font_family", tools.text_family)
            tools.text_size = float(_ts.get("font_size", tools.text_size))
            ui.text_entry = {"x": float(_ts.get("text_x", 0.0)),
                          "y": float(_ts.get("text_y", 0.0)),
                          "text": str(_ts.get("text_content", "")),
                          "family": tools.text_family, "size": tools.text_size,
                          "edit_index": _ti}
            selection.selected_strokes.clear()
    elif tools.tool_mode == "selection" and selection.selected_strokes and state.get(
        "text_font_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _ti = next(iter(sorted(selection.selected_strokes)), None)
        if _ti is not None and 0 <= _ti < len(document.strokes) and \
                isinstance(document.strokes[_ti], dict) and document.strokes[_ti].get("is_text"):
            push_undo()
            _fams = tuple(font_families)
            _cur = document.strokes[_ti].get("font_family", tools.text_family)
            _next = _fams[(_fams.index(_cur) + 1) % len(_fams)] if _cur in _fams else _fams[0]
            document.strokes[_ti] = update_text_stroke(document.strokes[_ti], font_family=_next)
            tools.text_family = _next
    return False
