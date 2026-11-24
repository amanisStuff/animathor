"""Draw drag session."""

import pygame
from controllers.drag.session import DragSession


class DrawDragSession(DragSession):
    name = "draw"

    def begin(self, ctx, event):
        pass

    def move(self, ctx, event):
        if not (ctx.drawing and ctx.tool_mode == "draw" and ctx.draw_tool == "pen"):
            return False
        cpos = ctx.clamp_to_canvas(event.pos)
        cpos = ctx.snap_world(cpos)
        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        keys = pygame.key.get_pressed()
        straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
        ctx.current_points = ctx.advance_drawing_points(ctx.current_points, cpos, ctx.strokes, ctx.snap_radius(), shift_held, straight_line)
        return True

    def end(self, ctx, event):
        from controllers.commit.draw_commit import commit_draw
        commit_draw(ctx, event)
        return True
