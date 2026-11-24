"""Nodes selection submode handler."""

from models import *  # noqa: F401,F403
from views import *  # noqa: F401,F403
from controllers.coordinates import *  # noqa: F401,F403


def handle_nodes_mode(ctx, event):
    ctx.cpos = ctx.to_canvas(event.pos)
    # Nodes mode: point editing only for single selection
    if len(ctx.selected_strokes) == 1:
        ctx.only = next(iter(ctx.selected_strokes))
        if 0 <= ctx.only < len(ctx.strokes):
            try:
                disp_segs = stroke_display_segs(ctx.strokes[ctx.only]) if 'stroke_display_segs' in globals() else None
            except Exception:
                disp_segs = None
            # prefer model/view-provided stroke_display_segs from star imports
            try:
                from models.strokes import stroke_display_segs as _sds
                disp_segs = _sds(ctx.strokes[ctx.only])
            except Exception:
                pass
            pt_hit = hit_test_point(ctx.strokes[ctx.only], ctx.cpos, segs_override=disp_segs)
            if pt_hit is not None:
                ctx.push_undo()
                ctx.selected_point = pt_hit; ctx.drag_last = ctx.cpos
            else:
                hit = hit_test_stroke(ctx.cpos, ctx.strokes)
                if hit == ctx.only:
                    ctx.drag_last = ctx.cpos
                elif hit is not None:
                    if ctx.shift:
                        if hit in ctx.selected_strokes:
                            ctx.selected_strokes.discard(hit)
                        else:
                            ctx.selected_strokes.add(hit)
                    else:
                        ctx.selected_strokes = {hit}
                    if ctx.selected_strokes:
                        ctx.primary_i = sorted(ctx.selected_strokes)[0]
                        if 0 <= ctx.primary_i < len(ctx.strokes):
                            ctx.width_slider.value = int(round(ctx.strokes[ctx.primary_i].get("stroke_width", 3)))
                    ctx.drag_last = ctx.cpos if hit is not None else None
                else:
                    if not ctx.shift:
                        ctx.selected_strokes.clear()
                    ctx.drag_last = None
        else:
            ctx.selected_strokes.clear(); ctx.drag_last = None
    else:
        # multi or none: selection changes only
        hit = hit_test_stroke(ctx.cpos, ctx.strokes)
        if hit is not None:
            if ctx.shift:
                if hit in ctx.selected_strokes:
                    ctx.selected_strokes.discard(hit)
                else:
                    ctx.selected_strokes.add(hit)
            else:
                ctx.selected_strokes = {hit}
            if ctx.selected_strokes:
                ctx.primary_i = sorted(ctx.selected_strokes)[0]
                if 0 <= ctx.primary_i < len(ctx.strokes):
                    ctx.width_slider.value = int(round(ctx.strokes[ctx.primary_i].get("stroke_width", 3)))
            ctx.drag_last = ctx.cpos
        else:
            if not ctx.shift:
                ctx.selected_strokes.clear()
            ctx.drag_last = None
    return 'handled'
