"""Guide drag session."""

import pygame
from controllers.drag.session import DragSession


class GuideDragSession(DragSession):
    name = "guide"

    def begin(self, ctx, event):
        pass  # ctx.guide_drag already set by caller

    def move(self, ctx, event):
        if ctx.guide_drag is None:
            return False
        _gp = ctx.to_canvas(event.pos)
        _gval = _gp[0] if ctx.guide_drag.get("axis") == "x" else _gp[1]
        ctx.guides = ctx.move_guide(ctx.guides, ctx.guide_drag.get("index", 0), _gval)
        return True

    def end(self, ctx, event):
        from controllers.commit.guide_commit import commit_guide_drag
        commit_guide_drag(ctx, event)
        return True
