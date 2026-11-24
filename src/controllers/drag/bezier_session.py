"""Bezier pen move/preview session."""

import pygame
from controllers.drag.session import DragSession


class BezierPenSession(DragSession):
    name = "bezier"

    def begin(self, ctx, event):
        pass

    def move(self, ctx, event):
        if not (ctx.tool_mode == "draw" and ctx.draw_tool == "pen" and ctx.draw_shape == "pen" and ctx.bezier_pen is not None):
            return False
        cpos = ctx.clamp_to_canvas(event.pos)
        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        if ctx.bezier_pen.get("mouse_down") and ctx.bezier_pen.get("dragging"):
            cpos = ctx.snap_world(cpos)
            ctx._bezier_pen_update_drag(cpos)
        else:
            sp = ctx.draw_snap_point(cpos, ctx.strokes, ctx.snap_radius(), shift_held)
            pos = ctx.snap_world(sp if sp is not None else cpos)
            ctx.bezier_pen["preview_pt"] = pos
        return True

    def end(self, ctx, event):
        from controllers.commit.bezier_pen_commit import commit_bezier_pen_mouseup
        commit_bezier_pen_mouseup(ctx, event)
        return True
