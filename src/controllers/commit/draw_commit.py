"""Draw/eraser mouse-up commit.

Core logic is a typed contract over AppState substates with explicit services;
``commit_draw`` is a compat wrapper for extracted ctx-based callers.
"""

import pygame
from models import finalize_drawing_points, shape_from_doodle, stroke_to_beziers  # noqa: F401


def commit_draw_typed(drag, document, selection, tools, event,
                      clamp_to_canvas, snap_radius, push_undo, new_stroke,
                      merge_connected_strokes, close_path_if_needed):
    """Convert a freehand/shape gesture into committed document strokes."""
    if drag.drawing and tools.tool_mode == "draw" and tools.draw_tool == "pen":
        drag.drawing = False
        cpos = clamp_to_canvas(event.pos)
        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        keys = pygame.key.get_pressed()
        straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
        points = finalize_drawing_points(
            drag.current_points, cpos, document.strokes, snap_radius(),
            shift_held, straight_line)
        if len(points) >= 2:
            raw = list(points)
            shape_segs = shape_raw = None
            if tools.draw_shape != "freehand":
                shape_segs, shape_raw = shape_from_doodle(
                    points, tools.draw_shape,
                    variant=tools.triangle_variant if tools.draw_shape == "triangle" else None,
                    corner_radius=tools.corner_radius if tools.draw_shape in ("rect", "square") else None,
                    segments=tools.ellipse_segments if tools.draw_shape in ("ellipse", "circle") else None,
                    constrain=tools.line_constrain if tools.draw_shape == "line" else False,
                    sides=tools.polygon_sides if tools.draw_shape == "polygon" else None,
                    star_points=tools.star_points if tools.draw_shape == "star" else None,
                    star_inner_ratio=tools.star_inner_ratio if tools.draw_shape == "star" else None,
                )
            if shape_segs:
                push_undo()
                algo_name = f"shape:{tools.draw_shape}"
                new_strokes = []
                for seg in shape_segs:
                    st = new_stroke([seg], algorithm=algo_name)
                    st["components"] = [{
                        "raw_points": [tuple(seg[0]), tuple(seg[3])],
                        "draw_max_points": int(tools.max_points_per_curve),
                        "algorithm": algo_name,
                        "segs": [seg],
                    }]
                    new_strokes.append(st)
                if new_strokes:
                    shape_stroke = new_strokes[0]
                    for extra in new_strokes[1:]:
                        shape_stroke = merge_connected_strokes([shape_stroke, extra])[0]
                    shape_stroke = close_path_if_needed(shape_stroke)
                    if tools.draw_shape == "line" and tools.line_arrow:
                        shape_stroke["arrow_end"] = True
                    document.strokes.append(shape_stroke)
                    document.strokes = merge_connected_strokes(document.strokes)
                    if (tools.draw_shape == "line" and tools.line_arrow and document.strokes
                            and not any(isinstance(s, dict) and s.get("arrow_end")
                                        for s in document.strokes)):
                        document.strokes[-1]["arrow_end"] = True
            elif straight_line:
                push_undo()
                p0 = tuple(points[0]); p3 = tuple(points[-1])
                c1 = (p0[0] + (p3[0] - p0[0]) / 3.0, p0[1] + (p3[1] - p0[1]) / 3.0)
                c2 = (p0[0] + 2.0 * (p3[0] - p0[0]) / 3.0, p0[1] + 2.0 * (p3[1] - p0[1]) / 3.0)
                beziers = [(p0, c1, c2, p3)]
                raw = [p0, p3]
                st = new_stroke(beziers, algorithm=tools.trace_algorithm)
                st["components"] = [{
                    "raw_points": [tuple(p) for p in raw],
                    "draw_max_points": int(tools.max_points_per_curve),
                    "algorithm": tools.trace_algorithm,
                    "segs": list(beziers),
                }]
                st = close_path_if_needed(st)
                document.strokes.append(st)
                document.strokes = merge_connected_strokes(document.strokes)
            else:
                beziers = stroke_to_beziers(
                    points, simplify_epsilon=2.5, tension=0.0,
                    max_points=tools.max_points_per_curve, algorithm=tools.trace_algorithm)
                if beziers:
                    push_undo()
                    st = new_stroke(beziers, algorithm=tools.trace_algorithm)
                    st["components"] = [{
                        "raw_points": [tuple(p) for p in raw],
                        "draw_max_points": int(tools.max_points_per_curve),
                        "algorithm": tools.trace_algorithm,
                        "segs": list(beziers),
                    }]
                    st = close_path_if_needed(st)
                    document.strokes.append(st)
                    document.strokes = merge_connected_strokes(document.strokes)
            selection.selected_strokes.clear()
            selection.selected_point = None
            selection.selected_curve = None
            selection.selected_curves.clear()
            drag.redrawing_curve = None
        drag.current_points = []
        return 'handled'
    if drag.drawing and tools.tool_mode == "draw" and tools.draw_tool == "eraser":
        drag.drawing = False
        drag.current_points = []
        return 'handled'
    return None


def commit_draw(ctx, event):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        return None
    result = commit_draw_typed(
        app_state.drag, app_state.document, app_state.selection, app_state.tools,
        event, ctx.clamp_to_canvas, ctx.snap_radius, ctx.push_undo,
        ctx.new_stroke, ctx.merge_connected_strokes, ctx._close_path_if_needed,
    )
    if result == 'handled':
        ctx.drawing = app_state.drag.drawing
        ctx.current_points = app_state.drag.current_points
        ctx.strokes = app_state.document.strokes
        ctx.selected_strokes = app_state.selection.selected_strokes
    return result
