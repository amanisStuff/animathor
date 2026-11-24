"""Bezier pen drag session: begin/move/preview/end owned by the session."""

import math
import pygame
from controllers.drag.session import DragSession


class BezierPenSession(DragSession):
    name = "bezier"

    @staticmethod
    def applies(ctx):
        """Whether the active tool/interaction is a Bezier pen path."""
        return (getattr(ctx, "tool_mode", None) == "draw"
                and getattr(ctx, "draw_tool", None) == "pen"
                and getattr(ctx, "draw_shape", None) == "pen"
                and getattr(ctx, "bezier_pen", None) is not None)

    def begin(self, ctx, event):
        """Own Bezier pen pointer-down: snap, double-click/close detection,
        anchor placement or handle-drag setup (moved from tools/draw_mode)."""
        cpos = ctx.clamp_to_canvas(event.pos)
        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        pos = ctx.draw_snap_point(cpos, ctx.strokes, ctx.snap_radius(), shift_held)
        if pos is None:
            pos = ctx.snap_world(cpos)
        else:
            pos = ctx.snap_world(pos)
        now = pygame.time.get_ticks()
        is_double = (
            now - ctx._bezier_last_click.get("time", 0) < 400
            and math.hypot(
                pos[0] - ctx._bezier_last_click.get("pos", (1e9, 1e9))[0],
                pos[1] - ctx._bezier_last_click.get("pos", (1e9, 1e9))[1],
            ) < 8.0
        )
        if (ctx.bezier_pen and ctx._bezier_pen_near_first(
                pos, max(10.0, float(ctx.snap_radius() or 0)))
                and len(ctx.bezier_pen.get("anchors", [])) >= 3):
            # Close path: drag on first anchor adjusts handles; finalize on mouseup.
            first = ctx.bezier_pen["anchors"][0]
            ctx.bezier_pen["mouse_down"] = True
            ctx.bezier_pen["dragging"] = True
            ctx.bezier_pen["dragging_first"] = True
            ctx.bezier_pen["down_pos"] = first["pt"]
            ctx.bezier_pen["preview_pt"] = pos
        elif is_double and ctx.bezier_pen and len(ctx.bezier_pen.get("anchors", [])) >= 2:
            ctx._bezier_pen_finish(close_path=False)
        else:
            ctx._bezier_pen_add_anchor(pos)
        ctx._bezier_last_click["time"] = now
        ctx._bezier_last_click["pos"] = pos
        ctx.drawing = False
        ctx.current_points = []

    def move(self, ctx, event):
        if not self.applies(ctx):
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
