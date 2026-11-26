"""Draw tool options panel click dispatch."""
from controllers.panel.rects import hit_rect, rects_from_state  # noqa: E402
from controllers.panel.reference_image_actions import reference_image_click
from controllers.panel.elevation_actions import elevation_click
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

def tool_options_typed(tools, selection, document, drag, ui, state, event,
                       push_undo, new_stroke, clamp, bucket_pick,
                       set_bucket_color, bezier_commit_or_cancel,
                       commit_xform_field, btn_boost, slider,
                       boost_max_points, normal_max_points,
                       bucket_swatches, globals_map):
    rects = rects_from_state(state)
    _matched = False
    # Right panel interactions
    if ui.xform_field_focus is not None and tools.tool_mode == "selection" and selection.selection_submode == "transform":
        _matched = True
        _xform_all = ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                      "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                      "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                      "xform_rm_rect", "xform_rp_rect")
        if not any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) for k in _xform_all):
            commit_xform_field()
    if btn_boost.hit(event.pos) and tools.tool_mode == "draw":
        _matched = True
        tools.boost_points = not tools.boost_points
        slider.max_v = boost_max_points if tools.boost_points else normal_max_points
        if not tools.boost_points:
            tools.max_points_per_curve = min(tools.max_points_per_curve, normal_max_points)
        slider.value = tools.max_points_per_curve
    elif tools.tool_mode == "draw":
        _matched = True
        handled_draw_panel = reference_image_click(
            rects, state, document, ui, event,
            pick_reference_image_path, load_reference_image, clamp)
        if not handled_draw_panel:
            if rects.get("snap_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                tools.snap_enabled = not tools.snap_enabled
            elif rects.get("bucket_sv_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                bucket_pick(state["bucket_sv_rect"], event.pos, "sv")
                ui.bucket_picker_drag = "sv"
            elif rects.get("bucket_hue_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                bucket_pick(state["bucket_hue_rect"], event.pos, "hue")
                ui.bucket_picker_drag = "hue"
            elif any(r.collidepoint(event.pos) for r in state.get("bucket_swatch_rects", [])):
                for _i, _r in enumerate(state.get("bucket_swatch_rects", [])):
                    if _r.collidepoint(event.pos) and _i < len(bucket_swatches):
                        set_bucket_color(bucket_swatches[_i])
                        break
            elif any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                     for k in ("draw_tool_prev_rect", "draw_tool_next_rect")):
                _dtdir = -1 if rects.get("draw_tool_prev_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else 1
                _dtools = ["pen", "eraser", "bucket", "cutter"]
                _cur_dt = tools.draw_tool if tools.draw_tool in _dtools else "pen"
                tools.draw_tool = _dtools[(_dtools.index(_cur_dt) + _dtdir) % len(_dtools)]
                if tools.draw_tool != "pen" and tools.bezier_pen is not None:
                    bezier_commit_or_cancel()
                if tools.draw_tool == "cutter":
                    drag.cutting = False; drag.cut_points = []
            else:
                picked_shape = False
                for key, r in state.get("draw_shape_rects", {}).items():
                    if r.collidepoint(event.pos):
                        if tools.bezier_pen is not None and not (tools.draw_tool == "pen" and key == "pen"):
                            bezier_commit_or_cancel()
                        if key == "rect":
                            tools.draw_shape = tools.rect_variant
                        elif key == "ellipse":
                            tools.draw_shape = tools.ellipse_variant
                        else:
                            tools.draw_shape = key
                        picked_shape = True
                        break
                if not picked_shape:
                    if any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                           for k in ("trace_algo_prev_rect", "trace_algo_next_rect")):
                        _adir = -1 if rects.get("trace_algo_prev_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else 1
                        _algos = [k for k, _ in TRACE_ALGORITHMS]
                        _cur = tools.trace_algorithm if tools.trace_algorithm in _algos else _algos[0]
                        tools.trace_algorithm = _algos[(_algos.index(_cur) + _adir) % len(_algos)]
    elif tools.tool_mode == "selection" and any(
        state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for k in ("nodes_mode_prev_rect", "nodes_mode_next_rect")
    ):
        _matched = True
        _mdir = -1 if rects.get("nodes_mode_prev_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else 1
        _modes = ["transform", "nodes", "curve"]
        _cur = selection.selection_submode if selection.selection_submode in _modes else "transform"
        selection.selection_submode = _modes[(_modes.index(_cur) + _mdir) % len(_modes)]
        selection.selected_point = None; selection.selected_curve = None; selection.selected_curves.clear(); drag.transform_drag = None; drag.drag_last = None; drag.redrawing_curve = None
        tools.curve_cut_mode = False
    elif elevation_click(tools, selection, document, drag, rects, event, push_undo):
        _matched = True
    elif tools.tool_mode == "selection" and selection.selection_submode == "transform" and len(selection.selected_strokes) >= 2 and (
        rects.get("bool_union_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        rects.get("bool_intersect_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        rects.get("bool_subtract_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        rects.get("bool_exclude_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        sel = sorted(i for i in selection.selected_strokes if 0 <= i < len(document.strokes))
        if len(sel) >= 2:
            bool_key = next(
                k for k in ("bool_union_rect", "bool_intersect_rect",
                            "bool_subtract_rect", "bool_exclude_rect")
                if state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
            )
            op = {
                "bool_union_rect": "union",
                "bool_intersect_rect": "intersection",
                "bool_subtract_rect": "difference",
                "bool_exclude_rect": "exclude",
            }[bool_key]
            try:
                from models.boolean import boolean_result
                result = boolean_result([document.strokes[i] for i in sel], op=op)
            except Exception:
                result = None
            if result:
                result_segs, result_comps, result_corners = result
                push_undo()
                primary = document.strokes[sel[0]]
                fill_col = primary.get("fill_color") if isinstance(primary, dict) else None
                fill_grad = copy.deepcopy(primary.get("fill_gradient")) if isinstance(primary, dict) and primary.get("fill_gradient") is not None else None
                if fill_col is None and fill_grad is None:
                    fill_col = (0.45, 0.72, 1.0, 1.0)
                new_st = new_stroke(
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
                for i in reversed(sel):
                    del document.strokes[i]
                document.strokes.append(new_st)
                selection.selected_strokes = {len(document.strokes) - 1}
                selection.selected_point = None; selection.selected_curve = None; selection.selected_curves.clear(); drag.transform_drag = None; drag.drag_last = None; drag.pending_transform_toggle = None
    return 'continue' if _matched else None


def _handle_panel_click_a_p1(ctx, event):
    """Compat wrapper for the typed tool-options handler."""
    s = getattr(ctx, '_app_state', None)
    if s is None:
        from controllers.app_state import AppState
        s = AppState()
        for obj, names in (
            (s.tools, ('tool_mode', 'draw_tool', 'draw_shape', 'rect_variant',
                       'ellipse_variant', 'max_points_per_curve', 'boost_points',
                       'snap_enabled', 'curve_cut_mode', 'trace_algorithm',
                       'bezier_pen')),
            (s.selection, ('selected_strokes', 'selected_point', 'selected_curve',
                           'selected_curves', 'selection_submode')),
            (s.document, ('strokes', 'reference_image', 'reference_error')),
            (s.drag, ('drag_last', 'pending_transform_toggle', 'cut_points',
                      'cutting', 'transform_drag', 'redrawing_curve')),
            (s.ui, ('xform_field_focus', 'bucket_picker_drag', 'ref_opacity_drag',
                    'bucket_picker_h', 'bucket_picker_s', 'bucket_picker_v')),
        ):
            for name in names:
                if hasattr(ctx, name):
                    setattr(obj, name, getattr(ctx, name))
    return tool_options_typed(
        s.tools, s.selection, s.document, s.drag, s.ui, ctx.state, event,
        getattr(ctx, 'push_undo', None), getattr(ctx, 'new_stroke', None),
        getattr(ctx, 'clamp', None), getattr(ctx, 'bucket_pick', None),
        getattr(ctx, 'set_bucket_color', None),
        getattr(ctx, '_bezier_pen_commit_or_cancel', None),
        getattr(ctx, '_commit_xform_field', None),
        getattr(ctx, 'btn_boost', None), getattr(ctx, 'slider', None),
        getattr(ctx, 'BOOST_MAX_POINTS', 100), getattr(ctx, 'NORMAL_MAX_POINTS', 5),
        getattr(ctx, 'BUCKET_SWATCHES', []),
        globals(),
    )

def tool_options_hit(tools, document, selection, ui, state, event, ctx, handlers):
    """Typed entry point for this panel domain.

    Handlers consume the live typed dispatch context supplied by the caller;
    domain boundaries are typed while handler bodies migrate incrementally.
    """
    for handler in handlers:
        if handler(ctx, event):
            return True
    return False
