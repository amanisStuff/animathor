"""Marquee selection drag session."""

from controllers.drag.session import DragSession


class MarqueeDragSession(DragSession):
    name = "marquee"

    def begin(self, ctx, event):
        pass  # ctx.marquee_select set by caller

    def move(self, ctx, event):
        if ctx.marquee_select is None:
            return False
        ctx.marquee_select["current"] = ctx.clamp_to_canvas(event.pos)
        return True

    def end(self, ctx, event):
        if ctx.marquee_select is None or ctx.tool_mode != "selection":
            return False
        from models import rects_intersect, expand_group_selection
        r = ctx.normalize_rect(ctx.marquee_select["start"], ctx.marquee_select.get("current", ctx.marquee_select["start"]))
        if abs(r[2] - r[0]) >= 3 or abs(r[3] - r[1]) >= 3:
            picked = {i for i, st in enumerate(ctx.strokes) if rects_intersect(r, ctx.stroke_bbox(st))}
            picked = expand_group_selection(ctx.strokes, picked)
            if ctx.marquee_select.get("add"):
                ctx.selected_strokes |= picked
            else:
                ctx.selected_strokes = picked
        elif not ctx.marquee_select.get("add"):
            ctx.selected_strokes.clear()
        ctx.marquee_select = None
        return True
