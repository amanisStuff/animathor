"""Controller: main-loop frame orchestration helpers (extracted from app_controller for SRP).

Uses frame-locals sync to keep app_controller.main thin; behavior-preserving.
"""
import types as _types


EVENT_SYNC_KEYS = ["_", "_bezier_last_click", "a", "algo_name", "alpha", "anchors", "b", "bar", "base", "bb", "best_d", "bezier_pen", "boost_points", "boxes", "bucket_fill_color", "bucket_picker_drag", "c1", "c2", "cfg", "clock", "col", "color_target", "comp_i", "comps", "corner_radius", "cpos", "current_points", "curve_cut_mode", "cut_gap", "cut_points", "cutting", "cx", "cy", "d", "drag_last", "draw_shape", "draw_tool", "drawing", "dx", "dy", "ellipse_segments", "ellipse_variant", "end", "event", "export_dialog_format", "export_dialog_open", "export_dpi", "export_scale", "eyedropper_pick", "field", "fill_color", "fill_stop_pos_drag", "first", "fixed_end", "fixed_start", "gradient_drag", "guide_drag", "guides", "h", "help_open", "i", "idxs", "items", "k", "key", "keys", "limit", "line_arrow", "line_constrain", "marker_dropdown", "marquee_select", "max_points_per_curve", "menu_open", "mode", "n", "new_h", "new_w", "obj_opacity_drag", "only", "opacity", "p", "p0", "p3", "pan_drag", "panel_collapsed", "panel_scroll", "path", "pending_transform_toggle", "picker_drag_alpha", "picker_drag_hue", "picker_drag_sv", "picker_h", "picker_s", "picker_v", "pivot_drag", "pivot_pos", "polygon_sides", "pos", "primary", "primary_i", "pts", "r", "rect_variant", "redrawing_curve", "ref_drag", "ref_opacity_drag", "reference_error", "reference_image", "repeat_pick_mode", "repeat_pick_target", "result", "running", "s", "s1", "screen", "scx", "scy", "segs", "sel", "sel_list", "selected_curve", "selected_curves", "selected_point", "selected_strokes", "selection_submode", "shadow", "shape_menu_anchor", "shape_menu_key", "shift_held", "si", "smart_snap_guides", "snap", "snap_enabled", "sp", "space_panning", "st", "star_inner_ratio", "star_points", "start_strokes", "state", "strokes", "sv", "sx1", "sy1", "tcx", "tcy", "text_entry", "text_family", "text_size", "tool_mode", "trace_algorithm", "transform_drag", "transform_handle_mode", "triangle_variant", "tx1", "ty1", "v", "val", "w", "wave_custom_drag", "wave_formula_focus", "wave_slider_drag", "workspace", "xform_field_buffer", "xform_field_focus"]


RENDER_SYNC_KEYS = ["_n", "active", "align_bottom_rect_cache", "align_hcenter_rect_cache", "align_left_rect_cache", "align_right_rect_cache", "align_top_rect_cache", "align_vmiddle_rect_cache", "bool_exclude_rect_cache", "bool_intersect_rect_cache", "bool_subtract_rect_cache", "bool_union_rect_cache", "bucket_hue_rect_cache", "bucket_picker_h", "bucket_picker_s", "bucket_picker_v", "bucket_sv_rect_cache", "bucket_swatch_rects_cache", "cap_next_rect_cache", "cap_prev_rect_cache", "cfg", "clock", "color_target", "current_points", "curve_cut_rect_cache", "curve_hide_rect_cache", "curve_join_rect_cache", "curve_redraw_rect_cache", "dash_next_rect_cache", "dash_prev_rect_cache", "displacement_add_rect_cache", "displacement_affect_rects_cache", "displacement_profile_rects_cache", "distribute_h_rect_cache", "distribute_v_rect_cache", "draw_shape_rects_cache", "draw_tool_bucket_rect_cache", "draw_tool_cutter_rect_cache", "draw_tool_eraser_rect_cache", "draw_tool_next_rect_cache", "draw_tool_pen_rect_cache", "draw_tool_prev_rect_cache", "drawing", "elev_back_rect_cache", "elev_backward_rect_cache", "elev_forward_rect_cache", "elev_front_rect_cache", "export_dialog_rects", "export_dpi", "export_scale", "eyedropper_rect_cache", "fill_gradient_stop", "fill_stop_add_rect_cache", "fill_stop_pos_drag", "fill_stop_pos_rect_cache", "fill_stop_rects_cache", "fill_stop_remove_rect_cache", "fill_type_next_rect_cache", "fill_type_prev_rect_cache", "frame", "guides", "join_next_rect_cache", "join_prev_rect_cache", "marker_dropdown", "marker_dropdown_item_rects", "marker_dropdown_rect", "marker_end_rect_cache", "marker_start_rect_cache", "menu_bar_rects", "menu_item_rects", "mirror_h_rect_cache", "mirror_v_rect_cache", "nodes_mode_next_rect_cache", "nodes_mode_prev_rect_cache", "obj_opacity_drag", "obj_opacity_rect_cache", "p", "panel_collapsed", "panel_scroll", "panel_toggle_rect_cache", "path_add_rect_cache", "path_close_rect_cache", "path_corner_rect_cache", "path_delete_rect_cache", "path_expand_rect_cache", "path_reverse_rect_cache", "path_smooth_rect_cache", "pattern_size_minus_rect_cache", "pattern_size_plus_rect_cache", "pattern_type_rect_cache", "picker_h", "picker_s", "picker_v", "pivot_pos", "primary_i", "pts", "r", "rect", "redrawing_curve", "ref_clear_rect_cache", "ref_load_rect_cache", "ref_opacity_rect_cache", "ref_vis_rect_cache", "repeat_add_rect_cache", "repeat_pick_curve_rect_cache", "repeat_pick_mode", "repeat_pick_target", "running", "s1", "screen", "selected_curve", "selected_curves", "selected_point", "selected_strokes", "selection_submode", "shadow_blur_minus_rect_cache", "shadow_blur_plus_rect_cache", "shadow_toggle_rect_cache", "shape_menu_anchor", "shape_menu_item_rects", "shape_menu_key", "shape_menu_rect", "shape_states", "smart_snap_guides", "snap_toggle_rect_cache", "state", "strokes", "text_edit_rect_cache", "text_entry", "text_font_rect_cache", "text_off_path_rect_cache", "text_on_path_rect_cache", "text_size_minus_rect_cache", "text_size_plus_rect_cache", "thickness_add_rect_cache", "tool_mode", "trace_algo_next_rect_cache", "trace_algo_prev_rect_cache", "wave_active_index", "wave_add_rect_cache", "wave_bake_rect_cache", "wave_clamp_rect_cache", "wave_clear_rect_cache", "wave_custom_box_rect_cache", "wave_custom_drag", "wave_custom_draw", "wave_custom_finished", "wave_done_rect_cache", "wave_formula_focus", "wave_formula_rect_cache", "wave_remove_rect_cache", "wave_reverse_rect_cache", "wave_row_rects_cache", "wave_shape_next_rect_cache", "wave_shape_prev_rect_cache", "wave_slider_rects_cache", "wave_smooth_rect_cache", "wave_toggle_rect_cache", "width_profile_next_rect_cache", "width_profile_prev_rect_cache", "workspace", "xform_field_buffer", "xform_field_focus", "xform_h_rect_cache", "xform_hm_rect_cache", "xform_hp_rect_cache", "xform_r_rect_cache", "xform_rm_rect_cache", "xform_rp_rect_cache", "xform_w_rect_cache", "xform_wm_rect_cache", "xform_wp_rect_cache", "xform_x_rect_cache", "xform_xm_rect_cache", "xform_xp_rect_cache", "xform_y_rect_cache", "xform_ym_rect_cache", "xform_yp_rect_cache"]



import sys


def _sync_back(ctx, frame_locals, keys):
    changed = False
    for k in keys:
        if hasattr(ctx, k):
            v = getattr(ctx, k)
            if frame_locals.get(k) is not v:
                frame_locals[k] = v
                changed = True
    return changed


def _write_back(frame):
    # CPython: push f_locals changes to fast locals.
    try:
        import ctypes
        ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(0))
    except Exception:
        pass


def process_event_frame(frame_locals=None):
    frame = sys._getframe(1)
    loc = frame.f_locals if frame_locals is None else frame_locals
    ctx = _types.SimpleNamespace()
    ctx.__dict__.update(loc)
    from controllers.event_loop import process_events as _pe
    _pe(ctx)
    if _sync_back(ctx, loc, EVENT_SYNC_KEYS) and frame_locals is None:
        _write_back(frame)


def render_frame_frame(frame_locals=None):
    frame = sys._getframe(1)
    loc = frame.f_locals if frame_locals is None else frame_locals
    ctx = _types.SimpleNamespace()
    ctx.__dict__.update(loc)
    from controllers.render_frame import render_frame as _rf
    _rf(ctx)
    if _sync_back(ctx, loc, RENDER_SYNC_KEYS) and frame_locals is None:
        _write_back(frame)


def compute_hover_snap(frame_locals=None):
    """Compute hover snap for current mouse frame (extracted from app_controller.main)."""
    frame = sys._getframe(1)
    loc = frame.f_locals if frame_locals is None else frame_locals
    g = frame.f_globals
    in_canvas = loc.get("in_canvas") or g.get("in_canvas")
    to_canvas = loc.get("to_canvas") or g.get("to_canvas")
    draw_snap_info = loc.get("draw_snap_info") or g.get("draw_snap_info")
    nearest_endpoint = loc.get("nearest_endpoint") or g.get("nearest_endpoint")
    mouse_pos = loc.get("mouse_pos")
    tool_mode = loc.get("tool_mode")
    redrawing_curve = loc.get("redrawing_curve")
    strokes = loc.get("strokes")
    snap_radius = loc.get("snap_radius")
    draw_tool = loc.get("draw_tool")
    draw_shape = loc.get("draw_shape")
    bezier_pen = loc.get("bezier_pen")
    drawing = loc.get("drawing")
    current_points = loc.get("current_points")
    pygame = loc.get("pygame") or g.get("pygame")
    hover_snap = None
    hover_snap_kind = "connect"
    if in_canvas(mouse_pos) and (tool_mode == "draw" or redrawing_curve is not None):
        cpos = to_canvas(mouse_pos)
        if redrawing_curve is not None:
            rpts = redrawing_curve.get("points", [])
            fixed_start = redrawing_curve.get("fixed_start")
            fixed_end = redrawing_curve.get("fixed_end")
            if not redrawing_curve.get("started") and fixed_start is not None:
                hover_snap = tuple(fixed_start)
                hover_snap_kind = "connect"
            elif redrawing_curve.get("started") and fixed_end is not None:
                hover_snap = tuple(fixed_end)
                hover_snap_kind = "connect"
            else:
                extras = [rpts[0]] if rpts else None
                shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                hover_snap, hover_snap_kind = draw_snap_info(cpos, strokes, snap_radius(), shift_held, extra_points=extras)
        elif tool_mode == "draw":
            if draw_tool == "pen" and draw_shape == "pen" and bezier_pen is not None:
                if not bezier_pen.get("mouse_down", False):
                    extras = [bezier_pen["anchors"][0]["pt"]] if (bezier_pen.get("anchors") and len(bezier_pen["anchors"]) >= 3) else None
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    hover_snap, hover_snap_kind = draw_snap_info(cpos, strokes, snap_radius(), shift_held, extra_points=extras)
                else:
                    hover_snap = None
                    hover_snap_kind = "connect"
            else:
                extras = [current_points[0]] if (drawing and current_points) else None
                if drawing:
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    hover_snap, hover_snap_kind = draw_snap_info(cpos, strokes, snap_radius(), shift_held, extra_points=extras)
                else:
                    hover_snap = nearest_endpoint(cpos, strokes, snap_radius(), extra_points=extras)
                    hover_snap_kind = "connect" if hover_snap is not None else "connect"
    loc["hover_snap"] = hover_snap
    loc["hover_snap_kind"] = hover_snap_kind
    if frame_locals is None:
        _write_back(frame)


def init_ui_caches(frame_locals=None):
    """Initialize UI rect caches/drag flags in main() locals for SRP."""
    frame = sys._getframe(1)
    loc = frame.f_locals if frame_locals is None else frame_locals
    pg = loc.get("pygame")
    R = pg.Rect
    DS = loc.get("DRAW_SHAPES") or frame.f_globals.get("DRAW_SHAPES") or []
    BT = loc.get("BOTTOM_TOOLS") or frame.f_globals.get("BOTTOM_TOOLS") or []
    updates = dict(
        color_target="stroke",
        picker_h=0.0, picker_s=0.0, picker_v=0.1,
        picker_drag_sv=False, picker_drag_hue=False, picker_drag_alpha=False, ref_opacity_drag=False,
        picker_rects={"sv":R(0,0,0,0),"hue":R(0,0,0,0),"tab_stroke":R(0,0,0,0),"tab_fill":R(0,0,0,0),"nofill":R(0,0,0,0),"alpha":R(0,0,0,0)},
        fill_type_prev_rect_cache=R(0,0,0,0), fill_type_next_rect_cache=R(0,0,0,0),
        fill_stop_rects_cache={}, fill_stop_add_rect_cache=R(0,0,0,0), fill_stop_remove_rect_cache=R(0,0,0,0), fill_stop_pos_rect_cache=R(0,0,0,0),
        pattern_type_rect_cache=R(0,0,0,0), pattern_size_minus_rect_cache=R(0,0,0,0), pattern_size_plus_rect_cache=R(0,0,0,0),
        fill_gradient_stop=0, fill_stop_pos_drag=False,
        trace_algo_prev_rect_cache=R(0,0,0,0), trace_algo_next_rect_cache=R(0,0,0,0),
        draw_tool_prev_rect_cache=R(0,0,0,0), draw_tool_next_rect_cache=R(0,0,0,0),
        draw_shape_rects_cache={k: R(0,0,0,0) for k, _ in list(DS)+list(BT)},
        panel_toggle_rect_cache=R(0,0,0,0),
        shape_menu_key=None, shape_menu_anchor=R(0,0,0,0), shape_menu_rect=R(0,0,0,0), shape_menu_item_rects={},
        draw_tool_pen_rect_cache=R(0,0,0,0), draw_tool_eraser_rect_cache=R(0,0,0,0),
        draw_tool_bucket_rect_cache=R(0,0,0,0), draw_tool_cutter_rect_cache=R(0,0,0,0),
        snap_toggle_rect_cache=R(0,0,0,0),
        nodes_mode_prev_rect_cache=R(0,0,0,0), nodes_mode_next_rect_cache=R(0,0,0,0),
        elev_front_rect_cache=R(0,0,0,0), elev_forward_rect_cache=R(0,0,0,0), elev_backward_rect_cache=R(0,0,0,0), elev_back_rect_cache=R(0,0,0,0),
        bool_union_rect_cache=R(0,0,0,0), bool_intersect_rect_cache=R(0,0,0,0), bool_subtract_rect_cache=R(0,0,0,0), bool_exclude_rect_cache=R(0,0,0,0),
        distribute_h_rect_cache=R(0,0,0,0), distribute_v_rect_cache=R(0,0,0,0),
        export_dialog_rects={},
        path_close_rect_cache=R(0,0,0,0), path_reverse_rect_cache=R(0,0,0,0), path_add_rect_cache=R(0,0,0,0), path_delete_rect_cache=R(0,0,0,0),
        path_smooth_rect_cache=R(0,0,0,0), path_corner_rect_cache=R(0,0,0,0), path_expand_rect_cache=R(0,0,0,0),
        obj_opacity_rect_cache=R(0,0,0,0), shadow_toggle_rect_cache=R(0,0,0,0), shadow_blur_minus_rect_cache=R(0,0,0,0), shadow_blur_plus_rect_cache=R(0,0,0,0),
        cap_prev_rect_cache=R(0,0,0,0), cap_next_rect_cache=R(0,0,0,0),
        join_prev_rect_cache=R(0,0,0,0), join_next_rect_cache=R(0,0,0,0),
        dash_prev_rect_cache=R(0,0,0,0), dash_next_rect_cache=R(0,0,0,0),
        marker_start_rect_cache=R(0,0,0,0), marker_end_rect_cache=R(0,0,0,0),
        marker_dropdown=None, marker_dropdown_rect=R(0,0,0,0), marker_dropdown_item_rects={},
        obj_opacity_drag=False,
        xform_field_focus=None, xform_field_buffer="",
        xform_x_rect_cache=R(0,0,0,0), xform_y_rect_cache=R(0,0,0,0), xform_w_rect_cache=R(0,0,0,0), xform_h_rect_cache=R(0,0,0,0), xform_r_rect_cache=R(0,0,0,0),
        xform_xm_rect_cache=R(0,0,0,0), xform_xp_rect_cache=R(0,0,0,0), xform_ym_rect_cache=R(0,0,0,0), xform_yp_rect_cache=R(0,0,0,0),
        xform_wm_rect_cache=R(0,0,0,0), xform_wp_rect_cache=R(0,0,0,0), xform_hm_rect_cache=R(0,0,0,0), xform_hp_rect_cache=R(0,0,0,0),
        xform_rm_rect_cache=R(0,0,0,0), xform_rp_rect_cache=R(0,0,0,0),
        text_edit_rect_cache=R(0,0,0,0), text_font_rect_cache=R(0,0,0,0), text_size_minus_rect_cache=R(0,0,0,0), text_size_plus_rect_cache=R(0,0,0,0),
        text_on_path_rect_cache=R(0,0,0,0), text_off_path_rect_cache=R(0,0,0,0),
        mirror_h_rect_cache=R(0,0,0,0), mirror_v_rect_cache=R(0,0,0,0),
        align_left_rect_cache=R(0,0,0,0), align_hcenter_rect_cache=R(0,0,0,0), align_right_rect_cache=R(0,0,0,0),
        align_top_rect_cache=R(0,0,0,0), align_vmiddle_rect_cache=R(0,0,0,0), align_bottom_rect_cache=R(0,0,0,0),
        curve_hide_rect_cache=R(0,0,0,0), curve_redraw_rect_cache=R(0,0,0,0), curve_cut_rect_cache=R(0,0,0,0), curve_join_rect_cache=R(0,0,0,0),
        eyedropper_rect_cache=R(0,0,0,0),
        wave_toggle_rect_cache=R(0,0,0,0), wave_add_rect_cache=R(0,0,0,0), displacement_add_rect_cache=R(0,0,0,0), repeat_add_rect_cache=R(0,0,0,0), thickness_add_rect_cache=R(0,0,0,0),
        wave_remove_rect_cache=R(0,0,0,0), wave_bake_rect_cache=R(0,0,0,0),
        wave_shape_prev_rect_cache=R(0,0,0,0), wave_shape_next_rect_cache=R(0,0,0,0),
        displacement_profile_rects_cache={}, width_profile_prev_rect_cache=R(0,0,0,0), width_profile_next_rect_cache=R(0,0,0,0), displacement_affect_rects_cache={},
        wave_formula_rect_cache=R(0,0,0,0), wave_formula_focus=False, wave_custom_draw=False,
        repeat_pick_mode=False, repeat_pick_target=None,
        wave_custom_box_rect_cache=R(0,0,0,0), wave_smooth_rect_cache=R(0,0,0,0), wave_clear_rect_cache=R(0,0,0,0), wave_done_rect_cache=R(0,0,0,0),
        repeat_pick_curve_rect_cache=R(0,0,0,0), wave_reverse_rect_cache=R(0,0,0,0), wave_clamp_rect_cache=R(0,0,0,0),
        wave_custom_drag=None, wave_active_index=0, wave_row_rects_cache=[], wave_custom_finished=False, wave_slider_rects_cache={}, wave_slider_drag=None,
        panel_scroll=0,
        export_scale=1.0, export_dpi=300, export_dialog_open=False, export_dialog_format="png",
        ref_load_rect_cache=R(0,0,0,0), ref_vis_rect_cache=R(0,0,0,0), ref_clear_rect_cache=R(0,0,0,0), ref_opacity_rect_cache=R(0,0,0,0),
        bucket_fill_color=(0.45, 0.72, 1.0),
        bucket_picker_drag=None, bucket_sv_rect_cache=R(0,0,0,0), bucket_hue_rect_cache=R(0,0,0,0),
        bucket_swatch_rects_cache=[R(0,0,0,0) for _ in loc.get("BUCKET_SWATCHES", [])],
        reference_image=None, reference_error=None, ref_drag=None, space_panning=False, pan_drag=None,
        document_path=None, clipboard_strokes=[], artboards=[], active_artboard=-1, symbols={},
    )
    # bucket picker hsv depends on bucket_fill_color
    _rgb2hsv = loc.get("rgb_to_hsv") or frame.f_globals.get("rgb_to_hsv")
    if _rgb2hsv:
        updates["bucket_picker_h"], updates["bucket_picker_s"], updates["bucket_picker_v"] = _rgb2hsv(*updates["bucket_fill_color"])
    _bs = loc.get("BUCKET_SWATCHES") or frame.f_globals.get("BUCKET_SWATCHES") or []
    updates["bucket_swatch_rects_cache"] = [R(0,0,0,0) for _ in _bs]
    loc.update(updates)
    if frame_locals is None:
        _write_back(frame)
