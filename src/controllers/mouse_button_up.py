"""Extracted handler: handle_mousebuttonup1."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

def handle_mousebuttonup1(ctx, event=None):
    if ctx.guide_drag is not None:
        ctx._rs = int(ctx.RULER_SIZE)
        _on_ruler = (event.pos[1] <= ctx.TOP_BAR_H + ctx._rs) or (event.pos[0] <= cfg.CANVAS_X + ctx._rs)
        if _on_ruler:
            ctx.guides = remove_guide(ctx.guides, ctx.guide_drag.get("index", 0))
        ctx.guide_drag = None
        return 'continue'
    ctx.smart_snap_guides = []
    # Bezier pen: commit handle drag or close path on first-anchor release.
    if ctx.tool_mode == "draw" and ctx.draw_tool == "pen" and ctx.draw_shape == "pen" and ctx.bezier_pen is not None and ctx.bezier_pen.get("mouse_down"):
        if ctx.bezier_pen.get("dragging_first"):
            ctx._bezier_pen_finish(close_path=True)
            return 'continue'
        else:
            ctx.bezier_pen["mouse_down"] = False
            ctx.bezier_pen["dragging"] = False
            return 'continue'
    if ctx.cutting:
        ctx.cutting = False
        ctx.cpos = ctx.clamp_to_canvas(event.pos)
        if not ctx.cut_points or math.hypot(ctx.cpos[0] - ctx.cut_points[-1][0],
                                        ctx.cpos[1] - ctx.cut_points[-1][1]) >= 1.0:
            ctx.cut_points.append(ctx.cpos)
        if len(ctx.cut_points) >= 2:
            ctx.only = None
            if (ctx.tool_mode == "selection" and ctx.selection_submode == "curve"
                    and ctx.selected_strokes):
                ctx.only = set(ctx.selected_strokes)
            new_strokes, cut_idx = cut_strokes_with_path(
                ctx.strokes, ctx.cut_points, only_indices=ctx.only,
                gap=ctx.cut_gap / 2.0)
            if cut_idx:
                ctx.push_undo()
                ctx.strokes[:] = new_strokes
                if ctx.tool_mode == "selection":
                    # For single-piece replacements (gap 0) indices are
                    # preserved; for multi-piece splits, select affected
                    # strokes best-effort by mapping original indices.
                    sel_after = set()
                    ctx.base = 0
                    cut_set = set(cut_idx)
                    for oi in range(len(ctx.strokes) - 0):  # placeholder, recompute below
                        pass
                    # Recompute mapping from original stroke index to new indices.
                    # We need original count; infer by reversing: iterate over
                    # original strokes isn't directly available, so approximate:
                    # if every cut produced exactly 1 piece total count matches
                    # original; otherwise fall back to selecting all new strokes
                    # in positions of cut regions is complex. Simpler: when in
                    # curve mode (single-stroke selection typical) select same
                    # indices as cut_idx; else leave selection cleared.
                    if ctx.selection_submode == "curve":
                        ctx.selected_strokes = set(ctx.i for ctx.i in cut_idx if 0 <= ctx.i < len(ctx.strokes))
                    else:
                        ctx.selected_strokes = set(ctx.i for ctx.i in cut_idx if 0 <= ctx.i < len(ctx.strokes))
                    ctx.selected_curve = None
                    ctx.selected_curves.clear()
                    if ctx.selection_submode == "curve":
                        # One-shot action: turn the razor off so the
                        # new curve halves can be clicked/selected.
                        ctx.curve_cut_mode = False
                        ctx.state["curve_cut_mode"] = False
                ctx.selected_point = None
                ctx.transform_drag = None
        ctx.cut_points = []
        return 'continue'
    if ctx.pan_drag is not None and ctx.space_panning:
        ctx.pan_drag = None
    ctx.pivot_drag = None
    if ctx.pending_transform_toggle is not None and ctx.tool_mode == "selection" and ctx.selection_submode == "transform":
        if not ctx.pending_transform_toggle.get("moved") and ctx.selected_strokes:
            ctx.transform_handle_mode = "rotate" if ctx.transform_handle_mode == "scale" else "scale"
        ctx.pending_transform_toggle = None
    ctx.transform_drag = None
    ctx.gradient_drag = None
    if ctx.marquee_select is not None and ctx.tool_mode == "selection":
        ctx.r = ctx.normalize_rect(ctx.marquee_select["start"], ctx.marquee_select.get("current", ctx.marquee_select["start"]))
        if abs(ctx.r[2]-ctx.r[0]) >= 3 or abs(ctx.r[3]-ctx.r[1]) >= 3:
            ctx.picked = {ctx.i for ctx.i, ctx.st in enumerate(ctx.strokes) if rects_intersect(ctx.r, ctx.stroke_bbox(ctx.st))}
            ctx.picked = expand_group_selection(ctx.strokes, ctx.picked)
            if ctx.marquee_select.get("add"):
                ctx.selected_strokes |= ctx.picked
            else:
                ctx.selected_strokes = ctx.picked
        elif not ctx.marquee_select.get("add"):
            ctx.selected_strokes.clear()
        ctx.marquee_select = None
    elif ctx.redrawing_curve is not None:
        if ctx.redrawing_curve.get("started"):
            ctx.si = ctx.redrawing_curve.get("stroke_idx")
            ctx.comp_i = ctx.redrawing_curve.get("comp_idx", ctx.redrawing_curve.get("seg_idx"))
            ctx.pts = list(ctx.redrawing_curve.get("points", []))
            ctx.fixed_start = ctx.redrawing_curve.get("fixed_start")
            ctx.fixed_end = ctx.redrawing_curve.get("fixed_end")
            if ctx.fixed_start is not None and ctx.pts:
                ctx.pts[0] = tuple(ctx.fixed_start)
            ctx.cpos = ctx.clamp_to_canvas(event.pos)
            ctx.shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            ctx.keys = pygame.key.get_pressed()
            straight_line = bool(ctx.keys[pygame.K_LSHIFT] or ctx.keys[pygame.K_RSHIFT]) if ctx.keys else False
            ctx.pts = finalize_drawing_points(ctx.pts, ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held, straight_line, fixed_end=ctx.fixed_end)
            if ctx.fixed_start is not None:
                if ctx.pts:
                    ctx.pts[0] = tuple(ctx.fixed_start)
                else:
                    ctx.pts = [tuple(ctx.fixed_start)]
            if ctx.fixed_end is not None:
                if len(ctx.pts) == 1:
                    ctx.pts.append(tuple(ctx.fixed_end))
                elif ctx.pts:
                    ctx.pts[-1] = tuple(ctx.fixed_end)
            if ctx.si is not None and ctx.comp_i is not None and 0 <= ctx.si < len(ctx.strokes) and len(ctx.pts) >= 2:
                ctx.push_undo()
                ctx.strokes[ctx.si] = redraw_stroke_component(ctx.strokes[ctx.si], ctx.comp_i, ctx.pts)
            ctx.redrawing_curve = None
        else:
            # Redraw mode armed but drawing not started yet (e.g. released on button); wait for canvas drag
            pass
    elif ctx.drawing and ctx.tool_mode == "draw" and ctx.draw_tool == "pen":
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
    elif ctx.drawing and ctx.tool_mode == "draw" and ctx.draw_tool == "eraser":
        ctx.drawing = False
        ctx.current_points = []
    ctx.drag_last = None; ctx.selected_point = None; ctx.transform_drag = None; ctx.gradient_drag = None; ctx.pivot_drag = None
    ctx.picker_drag_sv = False; ctx.picker_drag_hue = False; ctx.picker_drag_alpha = False; ctx.ref_opacity_drag = False; ctx.fill_stop_pos_drag = False
    ctx.obj_opacity_drag = False
    ctx.state["obj_opacity_drag"] = False
    ctx.bucket_picker_drag = None
    ctx.wave_slider_drag = None
    ctx.wave_custom_drag = None
    ctx.state["wave_custom_drag"] = None
    ctx.state["picker_drag_sv"] = False; ctx.state["picker_drag_hue"] = False; ctx.state["picker_drag_alpha"] = False; ctx.state["fill_stop_pos_drag"] = False
    ctx.ref_drag = None
    ctx.max_points_per_curve = ctx.slider.value

    return None
