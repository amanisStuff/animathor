"""Draw-mode tool dispatch (pen/eraser/bucket/cutter/text/bezier/shape)."""

import math
import pygame
from models import draw_snap_point, erase_curve_at, hit_test_stroke  # noqa: F401


def handle_draw_mode(ctx, event):
    ctx.cpos = ctx.to_canvas(event.pos)
    if ctx.tool_mode != "draw":
        return None
    ctx.mods = pygame.key.get_mods()
    if (ctx.mods & pygame.KMOD_ALT) and ctx.reference_image and ctx.reference_image.get("visible", True):
        ctx.ref_drag = {"offset": (ctx.cpos[0] - ctx.reference_image.get("x", 0), ctx.cpos[1] - ctx.reference_image.get("y", 0))}
        dm = getattr(ctx, 'drag_manager', None)
        if dm is not None:
            from controllers.drag.ref_session import RefDragSession
            dm.begin(RefDragSession(), ctx, event)
        ctx.drawing = False
        return 'handled'

    if ctx.draw_tool == "eraser":
        hit_e = hit_test_stroke(ctx.cpos, ctx.strokes)
        if hit_e is not None:
            ctx.push_undo()
            ctx.strokes, _ = erase_curve_at(ctx.strokes, ctx.cpos)
        ctx.drawing = False
        ctx.current_points = []
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
        return 'handled'

    if ctx.draw_tool == "bucket":
        # Geometric bucket fill (ray-casting/planar-face inspired): create a filled
        # vector shape for the enclosed region under the click, without a stroke.
        try:
            from models.fill import bucket_fill_to_beziers
            segs_fill = bucket_fill_to_beziers(ctx.strokes, ctx.cpos, simplify_epsilon=1.5, max_points=100)
            if segs_fill:
                ctx.push_undo()
                ctx.fill_color = (ctx.bucket_fill_color[0], ctx.bucket_fill_color[1],
                              ctx.bucket_fill_color[2], 1.0)
                new_st = ctx.new_stroke(
                    segs_fill,
                    stroke_color=(0.0, 0.0, 0.0, 0.0),
                    stroke_width=0.0,
                    fill_color=ctx.fill_color,
                    algorithm="fit",
                )
                ctx.strokes.append(new_st)
        except Exception:
            pass
        ctx.drawing = False
        ctx.current_points = []
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
        return 'handled'

    if ctx.draw_tool == "cutter":
        # Razor: collect the swipe; curves are split on release.
        ctx.cutting = True
        ctx.cut_points = [ctx.cpos]
        dm = getattr(ctx, 'drag_manager', None)
        if dm is not None:
            from controllers.drag.cutter_session import CutterDragSession
            dm.begin(CutterDragSession(), ctx, event)
        ctx.drawing = False
        ctx.current_points = []
        return 'handled'

    if ctx.draw_tool == "text":
        # Place a text insertion caret at the clicked point.
        if ctx.text_entry is not None:
            ctx.commit_text_entry()
        ctx.text_entry = {"x": ctx.cpos[0], "y": ctx.cpos[1], "text": "",
                      "family": ctx.text_family, "size": ctx.text_size}
        ctx.drawing = False
        ctx.current_points = []
        ctx.selected_strokes.clear(); ctx.selected_point = None
        ctx.selected_curve = None; ctx.selected_curves.clear()
        return 'handled'

    if ctx.draw_tool == "pen" and ctx.draw_shape == "pen":
        # Bezier pen pointer-down is owned by BezierPenSession (Phase 4).
        from controllers.drag.bezier_session import BezierPenSession
        session = BezierPenSession()
        dm = getattr(ctx, 'drag_manager', None)
        if dm is not None:
            dm.begin(session, ctx, event)
        else:
            session.begin(ctx, event)
        return 'handled'

    # If starting a non-bezier drawing gesture, cancel unfinished bezier path.
    if ctx.bezier_pen is not None:
        ctx._bezier_pen_cancel()
    ctx.drawing = True
    dm = getattr(ctx, 'drag_manager', None)
    if dm is not None:
        from controllers.drag.draw_session import DrawDragSession
        dm.begin(DrawDragSession(), ctx, event)
    ctx.shift_held = bool(ctx.mods & pygame.KMOD_SHIFT)
    start_pos = draw_snap_point(ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held)
    if start_pos is None:
        start_pos = ctx.snap_world(ctx.cpos)
    ctx.current_points = [start_pos]
    return 'handled'
