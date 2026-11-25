"""Elevation (z-order) clicks in the properties panel."""
import pygame


def elevation_click(tools, selection, document, drag, rects, event, push_undo):
        if tools.tool_mode == "selection" and selection.selection_submode == "transform" and selection.selected_strokes and (
            rects.get("elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
            rects.get("elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
            rects.get("elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
            rects.get("elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        ):
            push_undo()
            sel = sorted(i for i in selection.selected_strokes if 0 <= i < len(document.strokes))
            if sel:
                sel_set_local = set(sel)
                if rects.get("elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    picked = [document.strokes[i] for i in sel]
                    remaining = [st for i, st in enumerate(document.strokes) if i not in sel_set_local]
                    document.strokes[:] = remaining + picked
                    selection.selected_strokes = set(range(len(remaining), len(document.strokes)))
                elif rects.get("elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    picked = [document.strokes[i] for i in sel]
                    remaining = [st for i, st in enumerate(document.strokes) if i not in sel_set_local]
                    document.strokes[:] = picked + remaining
                    selection.selected_strokes = set(range(len(picked)))
                elif rects.get("elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    for i in range(len(document.strokes) - 2, -1, -1):
                        if i in selection.selected_strokes and (i + 1) not in selection.selected_strokes:
                            document.strokes[i], document.strokes[i + 1] = document.strokes[i + 1], document.strokes[i]
                            selection.selected_strokes.discard(i); selection.selected_strokes.add(i + 1)
                elif rects.get("elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    for i in range(1, len(document.strokes)):
                        if i in selection.selected_strokes and (i - 1) not in selection.selected_strokes:
                            document.strokes[i], document.strokes[i - 1] = document.strokes[i - 1], document.strokes[i]
                            selection.selected_strokes.discard(i); selection.selected_strokes.add(i - 1)
            selection.selected_point = None; selection.selected_curve = None; selection.selected_curves.clear(); drag.transform_drag = None; drag.drag_last = None; drag.pending_transform_toggle = None
        return False
