"""Draw tool options panel click dispatch."""
from controllers.panel.rects import hit_rect  # noqa: E402
import copy, math, pygame
import config as cfg
from config import TRACE_ALGORITHMS

from views.canvas_extra2 import load_reference_image
from views.dialogs import pick_reference_image_path
from controllers.panel.transform_inspector import _handle_panel_click_a_p2, _handle_panel_click_a_p3

def _handle_panel_click_a(ctx, event):
    """Semantic panel dispatch: draw options -> transform align -> transform nudge."""
    for handler in (_handle_panel_click_a_p1, _handle_panel_click_a_p2, _handle_panel_click_a_p3):
        _r = handler(ctx, event)
        if _r == 'continue':
            return 'continue'
        if _r == 'break':
            return 'break'
    return None

def _handle_panel_click_a_p1(ctx, event):
    _matched = False
    # Right panel interactions
    if ctx.xform_field_focus is not None and ctx.tool_mode == "selection" and ctx.selection_submode == "transform":
        _matched = True
        _xform_all = ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                      "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                      "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                      "xform_rm_rect", "xform_rp_rect")
        if not any(ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) for ctx.k in _xform_all):
            ctx._commit_xform_field()
    if ctx.btn_boost.hit(event.pos) and ctx.tool_mode == "draw":
        _matched = True
        ctx.boost_points = not ctx.boost_points
        ctx.slider.max_v = ctx.BOOST_MAX_POINTS if ctx.boost_points else ctx.NORMAL_MAX_POINTS
        if not ctx.boost_points:
            ctx.max_points_per_curve = min(ctx.max_points_per_curve, ctx.NORMAL_MAX_POINTS)
        ctx.slider.value = ctx.max_points_per_curve
    elif ctx.tool_mode == "draw":
        _matched = True
        handled_draw_panel = False
        if hit_rect(ctx, "ref_load_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            ctx.path = pick_reference_image_path()
            if ctx.path:
                ref = load_reference_image(ctx.path)
                if ref is not None:
                    ctx.reference_image = ref
                    ctx.reference_error = None
                else:
                    ctx.reference_error = "Could not load reference image (unsupported or corrupt file)."
            handled_draw_panel = True
        elif hit_rect(ctx, "ref_vis_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            if ctx.reference_image:
                ctx.reference_image["visible"] = not ctx.reference_image.get("visible", True)
            handled_draw_panel = True
        elif hit_rect(ctx, "ref_clear_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            ctx.reference_image = None
            ctx.reference_error = None
            handled_draw_panel = True
        elif ctx.reference_image and hit_rect(ctx, "ref_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            ctx.bar = ctx.state["ref_opacity_rect"]
            ctx.reference_image["opacity"] = ctx.clamp((event.pos[0] - ctx.bar.x) / max(1, ctx.bar.w - 1), 0.0, 1.0)
            ctx.ref_opacity_drag = True
            handled_draw_panel = True
        if not handled_draw_panel:
            if hit_rect(ctx, "snap_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.snap_enabled = not ctx.snap_enabled
            elif hit_rect(ctx, "bucket_sv_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.bucket_pick(ctx.state["bucket_sv_rect"], event.pos, "sv")
                ctx.bucket_picker_drag = "sv"
            elif hit_rect(ctx, "bucket_hue_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.bucket_pick(ctx.state["bucket_hue_rect"], event.pos, "hue")
                ctx.bucket_picker_drag = "hue"
            elif any(ctx.r.collidepoint(event.pos) for ctx.r in ctx.state.get("bucket_swatch_rects", [])):
                for _i, _r in enumerate(ctx.state.get("bucket_swatch_rects", [])):
                    if _r.collidepoint(event.pos) and _i < len(ctx.BUCKET_SWATCHES):
                        ctx.set_bucket_color(ctx.BUCKET_SWATCHES[_i])
                        break
            elif any(ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                     for ctx.k in ("draw_tool_prev_rect", "draw_tool_next_rect")):
                _dtdir = -1 if hit_rect(ctx, "draw_tool_prev_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else 1
                _dtools = ["pen", "eraser", "bucket", "cutter"]
                _cur_dt = ctx.draw_tool if ctx.draw_tool in _dtools else "pen"
                ctx.draw_tool = _dtools[(_dtools.index(_cur_dt) + _dtdir) % len(_dtools)]
                if ctx.draw_tool != "pen" and ctx.bezier_pen is not None:
                    ctx._bezier_pen_commit_or_cancel()
                if ctx.draw_tool == "cutter":
                    ctx.cutting = False; ctx.cut_points = []
            else:
                picked_shape = False
                for ctx.key, ctx.r in ctx.state.get("draw_shape_rects", {}).items():
                    if ctx.r.collidepoint(event.pos):
                        if ctx.bezier_pen is not None and not (ctx.draw_tool == "pen" and ctx.key == "pen"):
                            ctx._bezier_pen_commit_or_cancel()
                        if ctx.key == "rect":
                            ctx.draw_shape = ctx.rect_variant
                        elif ctx.key == "ellipse":
                            ctx.draw_shape = ctx.ellipse_variant
                        else:
                            ctx.draw_shape = ctx.key
                        picked_shape = True
                        break
                if not picked_shape:
                    if any(ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                           for ctx.k in ("trace_algo_prev_rect", "trace_algo_next_rect")):
                        _adir = -1 if hit_rect(ctx, "trace_algo_prev_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else 1
                        _algos = [ctx.k for ctx.k, _ in TRACE_ALGORITHMS]
                        _cur = ctx.trace_algorithm if ctx.trace_algorithm in _algos else _algos[0]
                        ctx.trace_algorithm = _algos[(_algos.index(_cur) + _adir) % len(_algos)]
    elif ctx.tool_mode == "selection" and any(
        ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for ctx.k in ("nodes_mode_prev_rect", "nodes_mode_next_rect")
    ):
        _matched = True
        _mdir = -1 if hit_rect(ctx, "nodes_mode_prev_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else 1
        _modes = ["transform", "nodes", "curve"]
        _cur = ctx.selection_submode if ctx.selection_submode in _modes else "transform"
        ctx.selection_submode = _modes[(_modes.index(_cur) + _mdir) % len(_modes)]
        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.redrawing_curve = None
        ctx.curve_cut_mode = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and (
        hit_rect(ctx, "elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        hit_rect(ctx, "elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        hit_rect(ctx, "elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        hit_rect(ctx, "elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        ctx.push_undo()
        ctx.sel = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
        if ctx.sel:
            sel_set_local = set(ctx.sel)
            if hit_rect(ctx, "elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.picked = [ctx.strokes[ctx.i] for ctx.i in ctx.sel]
                remaining = [ctx.st for ctx.i, ctx.st in enumerate(ctx.strokes) if ctx.i not in sel_set_local]
                ctx.strokes[:] = remaining + ctx.picked
                ctx.selected_strokes = set(range(len(remaining), len(ctx.strokes)))
            elif hit_rect(ctx, "elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.picked = [ctx.strokes[ctx.i] for ctx.i in ctx.sel]
                remaining = [ctx.st for ctx.i, ctx.st in enumerate(ctx.strokes) if ctx.i not in sel_set_local]
                ctx.strokes[:] = ctx.picked + remaining
                ctx.selected_strokes = set(range(len(ctx.picked)))
            elif hit_rect(ctx, "elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                for ctx.i in range(len(ctx.strokes) - 2, -1, -1):
                    if ctx.i in ctx.selected_strokes and (ctx.i + 1) not in ctx.selected_strokes:
                        ctx.strokes[ctx.i], ctx.strokes[ctx.i + 1] = ctx.strokes[ctx.i + 1], ctx.strokes[ctx.i]
                        ctx.selected_strokes.discard(ctx.i); ctx.selected_strokes.add(ctx.i + 1)
            elif hit_rect(ctx, "elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                for ctx.i in range(1, len(ctx.strokes)):
                    if ctx.i in ctx.selected_strokes and (ctx.i - 1) not in ctx.selected_strokes:
                        ctx.strokes[ctx.i], ctx.strokes[ctx.i - 1] = ctx.strokes[ctx.i - 1], ctx.strokes[ctx.i]
                        ctx.selected_strokes.discard(ctx.i); ctx.selected_strokes.add(ctx.i - 1)
        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.pending_transform_toggle = None
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and len(ctx.selected_strokes) >= 2 and (
        hit_rect(ctx, "bool_union_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        hit_rect(ctx, "bool_intersect_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        hit_rect(ctx, "bool_subtract_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        hit_rect(ctx, "bool_exclude_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        ctx.sel = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
        if len(ctx.sel) >= 2:
            bool_key = next(
                ctx.k for ctx.k in ("bool_union_rect", "bool_intersect_rect",
                            "bool_subtract_rect", "bool_exclude_rect")
                if ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
            )
            op = {
                "bool_union_rect": "union",
                "bool_intersect_rect": "intersection",
                "bool_subtract_rect": "difference",
                "bool_exclude_rect": "exclude",
            }[bool_key]
            try:
                from models.boolean import boolean_result
                ctx.result = boolean_result([ctx.strokes[ctx.i] for ctx.i in ctx.sel], op=op)
            except Exception:
                ctx.result = None
            if ctx.result:
                result_segs, result_comps, result_corners = ctx.result
                ctx.push_undo()
                ctx.primary = ctx.strokes[ctx.sel[0]]
                fill_col = ctx.primary.get("fill_color") if isinstance(ctx.primary, dict) else None
                fill_grad = copy.deepcopy(ctx.primary.get("fill_gradient")) if isinstance(ctx.primary, dict) and ctx.primary.get("fill_gradient") is not None else None
                if fill_col is None and fill_grad is None:
                    fill_col = (0.45, 0.72, 1.0, 1.0)
                new_st = ctx.new_stroke(
                    result_segs,
                    stroke_color=(0.0, 0.0, 0.0, 0.0),
                    stroke_width=0.0,
                    fill_color=fill_col,
                    corner_anchors=result_corners,
                    algorithm="fit",
                )
                if fill_grad is not None:
                    new_st["fill_gradient"] = fill_grad
                    if fill_col is None:
                        new_st["fill_color"] = None
                if result_comps:
                    new_st["components"] = result_comps
                for ctx.i in reversed(ctx.sel):
                    del ctx.strokes[ctx.i]
                ctx.strokes.append(new_st)
                ctx.selected_strokes = {len(ctx.strokes) - 1}
                ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.pending_transform_toggle = None
    return None



