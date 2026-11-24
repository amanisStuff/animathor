"""Redraw-curve drag session."""

import pygame
from controllers.drag.session import DragSession


class RedrawDragSession(DragSession):
    name = "redraw"

    def begin(self, ctx, event):
        pass

    def move(self, ctx, event):
        rc = ctx.redrawing_curve
        if not (rc is not None and rc.get("started") and pygame.mouse.get_pressed()[0]):
            return False
        cpos = ctx.clamp_to_canvas(event.pos)
        pts = rc.get("points", [])
        fixed_start = rc.get("fixed_start")
        fixed_end = rc.get("fixed_end")
        if fixed_start is not None and pts:
            pts[0] = tuple(fixed_start)
        keys = pygame.key.get_pressed()
        straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        pts = ctx.advance_drawing_points(pts, cpos, ctx.strokes, ctx.snap_radius(), shift_held, straight_line, fixed_end=fixed_end)
        rc["points"] = pts
        return True

    def end(self, ctx, event):
        from controllers.commit.redraw_commit import commit_redraw_curve
        commit_redraw_curve(ctx, event)
        return True
