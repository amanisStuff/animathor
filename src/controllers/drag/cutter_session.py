"""Cutter drag session."""

import math
from controllers.drag.session import DragSession


class CutterDragSession(DragSession):
    name = "cutter"

    def begin(self, ctx, event):
        pass

    def move(self, ctx, event):
        if not ctx.cutting:
            return False
        cpos = ctx.clamp_to_canvas(event.pos)
        if not ctx.cut_points or math.hypot(cpos[0] - ctx.cut_points[-1][0],
                                        cpos[1] - ctx.cut_points[-1][1]) >= 1.0:
            ctx.cut_points.append(cpos)
        return True

    def end(self, ctx, event):
        from controllers.commit.cutter_commit import commit_cutter
        result = commit_cutter(ctx, event)
        return result == 'continue' or result is True or ctx.cutting is False
