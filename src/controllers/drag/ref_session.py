"""Reference image drag session."""

from controllers.drag.session import DragSession


class RefDragSession(DragSession):
    name = "ref"

    def begin(self, ctx, event):
        pass

    def move(self, ctx, event):
        if ctx.ref_drag is None or ctx.reference_image is None:
            return False
        cp = ctx.to_canvas(event.pos)
        off = ctx.ref_drag.get("offset", (0, 0))
        ctx.reference_image["x"] = cp[0] - off[0]
        ctx.reference_image["y"] = cp[1] - off[1]
        return True

    def end(self, ctx, event):
        ctx.ref_drag = None
        return True
