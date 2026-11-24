"""Draw/eraser mouse-up commit."""

import pygame
from models import *  # noqa: F401,F403
from views import *  # noqa: F401,F403
from controllers.coordinates import *  # noqa: F401,F403


def commit_draw(ctx, event):
    if ctx.drawing and ctx.tool_mode == "draw" and ctx.draw_tool == "pen":
        ctx.drawing = False
        ctx.cpos = ctx.clamp_to_canvas(event.pos)
        ctx.shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        ctx.keys = pygame.key.get_pressed()
        straight_line = bool(ctx.keys[pygame.K_LSHIFT] or ctx.keys[pygame.K_RSHIFT]) if ctx.keys else False
        ctx.current_points = finalize_drawing_points(ctx.current_points, ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held, straight_line)
        if len(ctx.current_points) >= 2:
            raw = list(ctx.current_points)
            shape_segs = None
            shape_raw = None
            if ctx.draw_shape != "freehand":
                shape_segs, shape_raw = shape_from_doodle(
                    ctx.current_points, ctx.draw_shape,
                    variant=ctx.triangle_variant if ctx.draw_shape == "triangle" else None,
                    corner_radius=ctx.corner_radius if ctx.draw_shape in ("rect", "square") else None,
                    segments=ctx.ellipse_segments if ctx.draw_shape in ("ellipse", "circle") else None,
                    constrain=ctx.line_constrain if ctx.draw_shape == "line" else False,
                    sides=ctx.polygon_sides if ctx.draw_shape == "polygon" else None,
                    star_points=ctx.star_points if ctx.draw_shape == "star" else None,
                    star_inner_ratio=ctx.star_inner_ratio if ctx.draw_shape == "star" else None,
                )
            if shape_segs:
                # Create a collection of connected curves/strokes (one per edge/segment) when possible
                ctx.push_undo()
                ctx.algo_name = f"shape:{ctx.draw_shape}"
                base_raw = shape_raw if shape_raw is not None else list(ctx.current_points)
                new_strokes = []
                for seg in shape_segs:
                    ctx.st = ctx.new_stroke([seg], algorithm=ctx.algo_name)
                    ctx.comp = {
                        "raw_points": [tuple(seg[0]), tuple(seg[3])],
                        "draw_max_points": int(ctx.max_points_per_curve),
                        "algorithm": ctx.algo_name,
                        "segs": [seg],
                    }
                    ctx.st["components"] = [ctx.comp]
                    new_strokes.append(ctx.st)
                if new_strokes:
                    # connect edges together so they form one shape with sharp corners at joins
                    shape_stroke = new_strokes[0]
                    for extra in new_strokes[1:]:
                        shape_stroke = ctx.merge_connected_strokes([shape_stroke, extra])[0]
                    shape_stroke = ctx._close_path_if_needed(shape_stroke)
                    if ctx.draw_shape == "line" and ctx.line_arrow:
                        shape_stroke["arrow_end"] = True
                    ctx.strokes.append(shape_stroke)
                    ctx.strokes = ctx.merge_connected_strokes(ctx.strokes)
                    if (ctx.draw_shape == "line" and ctx.line_arrow and ctx.strokes
                            and not any(isinstance(ctx.s, dict) and ctx.s.get("arrow_end")
                                        for ctx.s in ctx.strokes)):
                        # merging rebuilt the stroke dict; keep the arrowhead
                        ctx.strokes[-1]["arrow_end"] = True
                ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
            elif straight_line:
                ctx.push_undo()
                ctx.p0 = tuple(ctx.current_points[0])
                ctx.p3 = tuple(ctx.current_points[-1])
                ctx.c1 = (ctx.p0[0] + (ctx.p3[0] - ctx.p0[0]) / 3.0, ctx.p0[1] + (ctx.p3[1] - ctx.p0[1]) / 3.0)
                ctx.c2 = (ctx.p0[0] + 2.0 * (ctx.p3[0] - ctx.p0[0]) / 3.0, ctx.p0[1] + 2.0 * (ctx.p3[1] - ctx.p0[1]) / 3.0)
                beziers = [(ctx.p0, ctx.c1, ctx.c2, ctx.p3)]
                raw = [ctx.p0, ctx.p3]
                ctx.algo_name = ctx.trace_algorithm
                ctx.st = ctx.new_stroke(beziers, algorithm=ctx.algo_name)
                ctx.comp = {
                    "raw_points": [tuple(ctx.p) for ctx.p in raw],
                    "draw_max_points": int(ctx.max_points_per_curve),
                    "algorithm": ctx.algo_name,
                    "segs": list(beziers),
                }
                ctx.st["components"] = [ctx.comp]
                ctx.st = ctx._close_path_if_needed(ctx.st)
                ctx.strokes.append(ctx.st)
                ctx.strokes = ctx.merge_connected_strokes(ctx.strokes)
                ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
            else:
                beziers = stroke_to_beziers(
                    ctx.current_points, simplify_epsilon=2.5, tension=0.0,
                    max_points=ctx.max_points_per_curve, algorithm=ctx.trace_algorithm,
                )
                ctx.algo_name = ctx.trace_algorithm
                if beziers:
                    ctx.push_undo()
                    ctx.st = ctx.new_stroke(beziers, algorithm=ctx.algo_name)
                    ctx.comp = {
                        "raw_points": [tuple(ctx.p) for ctx.p in raw],
                        "draw_max_points": int(ctx.max_points_per_curve),
                        "algorithm": ctx.algo_name,
                        "segs": list(beziers),
                    }
                    ctx.st["components"] = [ctx.comp]
                    ctx.st = ctx._close_path_if_needed(ctx.st)
                    ctx.strokes.append(ctx.st)
                    ctx.strokes = ctx.merge_connected_strokes(ctx.strokes)
                    ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
        ctx.current_points = []
        return 'handled'
    if ctx.drawing and ctx.tool_mode == "draw" and ctx.draw_tool == "eraser":
        ctx.drawing = False
        ctx.current_points = []
        return 'handled'
    return None
