"""Mirror / align clicks in the transform panel."""
import pygame
from models.geometry import mirror_stroke


def transform_align_click(tools, selection, document, drag, state, event,
                          push_undo, combined_obb, combined_bbox,
                          stroke_bbox, translate_stroke):
    if tools.tool_mode == "selection" and selection.selection_submode == "transform" and selection.selected_strokes and (
        state.get("mirror_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("mirror_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("align_left_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("align_hcenter_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("align_right_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("align_top_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("align_vmiddle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("align_bottom_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        sel = sorted(i for i in selection.selected_strokes if 0 <= i < len(document.strokes))
        if sel:
            obb = combined_obb(document.strokes, sel)
            bb = combined_bbox(document.strokes, sel)
            if obb and bb:
                if drag.pivot_pos is not None:
                    cx, cy = drag.pivot_pos
                else:
                    cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
                push_undo()
                if state.get("mirror_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    for si in sel:
                        document.strokes[si] = mirror_stroke(document.strokes[si], cx, cy, "h")
                elif state.get("mirror_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    for si in sel:
                        document.strokes[si] = mirror_stroke(document.strokes[si], cx, cy, "v")
                else:
                    tx1, ty1, tx2, ty2 = bb
                    tcx, tcy = (tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0
                    for si in sel:
                        sbb = stroke_bbox(document.strokes[si])
                        if not sbb:
                            continue
                        sx1, sy1, sx2, sy2 = sbb
                        scx, scy = (sx1 + sx2) / 2.0, (sy1 + sy2) / 2.0
                        dx = dy = 0.0
                        if state.get("align_left_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            dx = tx1 - sx1
                        elif state.get("align_hcenter_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            dx = tcx - scx
                        elif state.get("align_right_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            dx = tx2 - sx2
                        elif state.get("align_top_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            dy = ty1 - sy1
                        elif state.get("align_vmiddle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            dy = tcy - scy
                        elif state.get("align_bottom_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            dy = ty2 - sy2
                        if dx != 0.0 or dy != 0.0:
                            document.strokes[si] = translate_stroke(document.strokes[si], dx, dy)
        selection.selected_point = None; selection.selected_curve = None; selection.selected_curves.clear(); drag.transform_drag = None; drag.drag_last = None; drag.pending_transform_toggle = None
    return False
