"""Pivot drag session."""

from controllers.drag.session import DragSession


class PivotDragSession(DragSession):
    name = "pivot"

    def begin(self, ctx, event):
        pass

    def move(self, ctx, event):
        if ctx.pivot_drag is None:
            return False
        sp0 = ctx.pivot_drag.get("start_pivot", ctx.to_canvas(event.pos))
        sm = ctx.pivot_drag.get("start", ctx.to_canvas(event.pos))
        cp = ctx.to_canvas(event.pos)
        ctx.pivot_pos = (sp0[0] + (cp[0] - sm[0]), sp0[1] + (cp[1] - sm[1]))
        return True

    def end(self, ctx, event):
        ctx.pivot_drag = None
        return True
