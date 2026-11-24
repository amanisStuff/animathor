"""Pan drag session."""

import config as cfg
from controllers.drag.session import DragSession


class PanDragSession(DragSession):
    name = "pan"

    def begin(self, ctx, event):
        ctx.pan_drag = {
            "start_mouse": event.pos,
            "start_pan": (getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0)),
        }

    def move(self, ctx, event):
        pan = ctx.pan_drag
        if not pan:
            return False
        sx, sy = pan["start_mouse"]
        spx, spy = pan["start_pan"]
        cfg.VIEW_PAN_X = spx + (event.pos[0] - sx)
        cfg.VIEW_PAN_Y = spy + (event.pos[1] - sy)
        return True

    def end(self, ctx, event):
        if ctx.pan_drag is not None and not ctx.space_panning:
            ctx.pan_drag = None
            return True
        return False

    def cancel(self, ctx):
        ctx.pan_drag = None
