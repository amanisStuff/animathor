"""Controller: application state, event handling and the main loop."""

import math
import copy

import pygame

import config as cfg
from config import *

import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))
import views as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))

# Coordinate helpers (own controller submodule)
from controllers.coordinates import in_canvas, to_canvas, clamp_to_canvas, to_screen  # noqa: E402,F401
from controllers import history_controller as _history  # noqa: E402
from controllers import bezier_pen_controller as _bp  # noqa: E402
from controllers import transform_field_controller as _xform  # noqa: E402
from controllers import snap_controller as _snap  # noqa: E402
from controllers import text_entry_controller as _text_entry  # noqa: E402
from controllers import bucket_controller as _bucket  # noqa: E402
from controllers import menu_dispatch_controller as _menu_dispatch  # noqa: E402
from controllers import app_frame_controller as _frame  # noqa: E402
from controllers.shape_state_controller import (  # noqa: E402
    _stroke_kind_label, _capture_shape_state, _insert_shape_state, _delete_shape_state,
)
from models.geometry import bbox_handle_anchor_local, bbox_handle_local_positions, gradient_edit_handles, hit_test_gradient_handle, gradient_edit_bbox, get_fill_gradient, is_fill_gradient, normalize_gradient, clamp, default_linear_gradient, default_radial_gradient, default_shaped_gradient, get_stroke_obb
from models.strokes import scale_stroke_local, rotate_stroke_around, skew_stroke_local


def main():
    pygame.init()
    screen = pygame.display.set_mode((cfg.WIDTH, cfg.HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Cairo Vector Draw - strokes to Bezier curves")
    clock = pygame.time.Clock()

    cairo_surface = make_cairo_surface(cfg.CANVAS_W, cfg.canvas_viewport_height())
    panel_collapsed = False  # right sidebar hidden -> canvas grows to the window edge

    def relayout():
        """Recompute canvas/panel geometry after a resize or sidebar toggle."""
        nonlocal cairo_surface
        panel_w = 0 if panel_collapsed else PANEL_W
        cfg.CANVAS_X = LEFT_BAR_W
        cfg.CANVAS_W = max(200, cfg.WIDTH - LEFT_BAR_W - panel_w)
        cfg.PANEL_X = LEFT_BAR_W + cfg.CANVAS_W
        cairo_surface = make_cairo_surface(cfg.CANVAS_W, cfg.canvas_viewport_height())

    strokes = []
    undo_stack = []
    redo_stack = []
    MAX_UNDO = 100

    def push_undo():
        _history.push_undo(undo_stack, redo_stack, strokes, MAX_UNDO)

    def do_undo():
        return _history.do_undo(undo_stack, redo_stack, strokes)

    def do_redo():
        return _history.do_redo(undo_stack, redo_stack, strokes)

    current_points = []
    drawing = False
    tool_mode = "draw"
    selected_strokes = set()
    selected_point = None
    selected_curve = None  # (stroke_idx, comp_idx) in curve edit mode
    redrawing_curve = None  # {"stroke_idx", "comp_idx", "points", "started", "fixed_start", "fixed_end"}
    drag_last = None
    selection_submode = "transform"  # "transform", "nodes", or "curve"
    transform_handle_mode = "scale"  # "scale" or "rotate" (Inkscape-like toggle inside transform)
    transform_drag = None  # {"handle": name, "start_mouse": (x,y), "start_strokes": {i: copy}, "center": (cx,cy), "start_bbox": bbox, "mode": str}
    gradient_drag = None  # {"handle": name, "stroke_is": [int], "grad_type": str, "bbox": (x0,y0,x1,y1)}
    pivot_pos = None  # custom rotation/scale pivot (world coords); None = bbox center
    pivot_drag = None  # {"offset": (dx,dy)} while dragging pivot
    pending_transform_toggle = None  # click-on-selected-body candidate to toggle scale/rotate
    prev_selection_set = set()
    marquee_select = None  # {"start": (x,y), "current": (x,y), "add": bool}
    guides = []  # ruler guides: [{"axis": "x"|"y", "pos": world_coord}]
    guide_drag = None  # {"axis", "index"} while dragging a guide from a ruler
    smart_snap_guides = []  # transient alignment guides while dragging moves
    max_points_per_curve = 4
    boost_points = False
    NORMAL_MAX_POINTS = 5
    BOOST_MAX_POINTS = 100
    trace_algorithm = "fit"  # "fit", "catmull-rom", "single" (per new stroke)
    draw_shape = "freehand"  # "freehand" or standard shape key from DRAW_SHAPES
    triangle_variant = "isosceles"  # "isosceles", "right", "equilateral"
    rect_variant = "rect"  # "rect" or "square" (shared Rect toolbar button)
    ellipse_variant = "ellipse"  # "ellipse" or "circle" (shared Ellipse toolbar button)
    line_constrain = False  # snap line shapes to 45-degree directions
    line_arrow = False  # draw an arrowhead at the end of line shapes
    corner_radius = 0  # percent of the rect/square min side (0-50)
    ellipse_segments = 4  # bezier arcs used for ellipse/circle
    polygon_sides = 6  # sides for the polygon primitive (3-24)
    star_points = 5  # spikes for the star primitive (3-24)
    star_inner_ratio = 0.5  # inner radius as a fraction of outer
    draw_tool = "pen"  # "pen", "eraser", "bucket", "cutter", or "text"
    bezier_pen = None  # active Bezier pen path: {"anchors":[{"pt","h_in","h_out"}], "dragging", "mouse_down", "down_pos", "preview_pt", "closed"}
    text_entry = None  # active text placement: {"x","y","text","family","size"}
    text_family = "Sans"  # current text font family for new text
    text_size = 36.0  # current text font size for new text
    cutting = False  # razor swipe in progress
    cut_points = []  # canvas-space points of the swipe
    cut_gap = 0  # optional visible gap left by the razor (canvas px, total)
    curve_cut_mode = False  # Split curve toggle in selection Curve mode
    eyedropper_pick = False  # one-shot style picker in selection mode
    selected_curves = set()  # set of (stroke_idx, comp_idx) in curve mode

    fonts = make_fonts()
    font, font_small, font_title = fonts
    try:
        ruler_font = pygame.font.Font(None, 14)
    except Exception:
        ruler_font = font_small

    btn_undo = Button((8, TOP_BAR_H + 8, 40, 40), "")
    btn_redo = Button((8, TOP_BAR_H + 52, 40, 40), "")
    btn_draw = Button((8, TOP_BAR_H + 104, 40, 40), "")
    btn_select = Button((8, TOP_BAR_H + 152, 40, 40), "")
    btn_boost = Button((0, 0, PANEL_W - 40, 34), "Boost limit")
    buttons = {"boost": btn_boost, "actions": []}
    slider = Slider(cfg.PANEL_X + 20, 0, PANEL_W - 40, 2, NORMAL_MAX_POINTS, max_points_per_curve)
    width_slider = Slider(cfg.PANEL_X + 20, 0, PANEL_W - 40, 1, 20, 3)
    cut_gap_slider = Slider(cfg.PANEL_X + 20, 0, PANEL_W - 40, 0, 20, cut_gap)
    cut_gap_slider.track.width = 0  # shown only while the cutter/gap control is active

    # lexical bindings for nested nonlocal
    _shape_state_counter = _symbol_counter = active_artboard = artboards = bezier_pen = bucket_fill_color = bucket_picker_h = bucket_picker_s = bucket_picker_v = cairo_surface = clipboard_strokes = current_points = curve_cut_mode = cut_points = cutting = document_path = drag_last = draw_tool = drawing = export_dialog_format = export_dialog_open = eyedropper_pick = help_open = panel_collapsed = redrawing_curve = running = selected_curve = selected_curves = selected_point = selected_strokes = selection_submode = shape_states = snap_enabled = strokes = symbols = text_entry = text_family = text_size = tool_mode = transform_drag = workspace = xform_field_buffer = xform_field_focus = None
    _frame.init_ui_caches()
    _symbol_counter = 0
    shape_states = {}  # {state_id: {"name": str, "strokes": [stroke_dict,...], "origin": [x, y]}}
    _shape_state_counter = 0
    menu_open = None
    help_open = False
    workspace = "draw"  # "draw" (canvas drawing) or "library" (shape states browser)
    menu_bar_rects = {}
    menu_item_rects = {}
    swatch_rects_cache = {
        "stroke": [pygame.Rect(0, 0, 0, 0) for _ in STROKE_SWATCHES],
        "fill": [pygame.Rect(0, 0, 0, 0) for _ in STROKE_SWATCHES],  # presets sized to STROKE_SWATCHES in picker
    }

    SNAP_RADIUS = 22
    snap_enabled = True  # toggle with the Snap button or the S key

    def snap_radius():
        return _snap.snap_radius(snap_enabled, SNAP_RADIUS)

    def _alignment_guides_for_point(pt, other_strokes, sr):
        return _snap.alignment_guides_for_point(pt, other_strokes, sr, stroke_bbox)

    def _snap_move_delta(sel_indices, dx, dy):
        return _snap.snap_move_delta(strokes, sel_indices, dx, dy, snap_radius(), stroke_bbox, nearest_snap_point)

    def _bucket_ctx():
        import types as _types
        ctx = _types.SimpleNamespace()
        ctx.bucket_fill_color = bucket_fill_color
        ctx.bucket_picker_h = bucket_picker_h
        ctx.bucket_picker_s = bucket_picker_s
        ctx.bucket_picker_v = bucket_picker_v
        ctx.clamp = clamp
        ctx.hsv_to_rgb = hsv_to_rgb
        ctx.rgb_to_hsv = rgb_to_hsv
        ctx.state = state
        return ctx

    def _bucket_sync(ctx):
        nonlocal bucket_fill_color, bucket_picker_h, bucket_picker_s, bucket_picker_v
        bucket_fill_color = ctx.bucket_fill_color
        bucket_picker_h = ctx.bucket_picker_h
        bucket_picker_s = ctx.bucket_picker_s
        bucket_picker_v = ctx.bucket_picker_v

    def bucket_pick(rect, pos, kind):
        ctx = _bucket_ctx(); _bucket.pick(ctx, rect, pos, kind); _bucket_sync(ctx)

    def set_bucket_color(col):
        ctx = _bucket_ctx(); _bucket.set_color(ctx, col); _bucket_sync(ctx)

    def commit_text_entry():
        nonlocal text_entry, selected_strokes, selected_point, selected_curve, selected_curves
        import types as _types
        ctx = _types.SimpleNamespace()
        ctx.text_entry = text_entry
        ctx.strokes = strokes
        ctx.selected_strokes = selected_strokes
        ctx.selected_point = selected_point
        ctx.selected_curve = selected_curve
        ctx.selected_curves = selected_curves
        ctx.push_undo = push_undo
        ctx.hsv_to_rgb = hsv_to_rgb
        ctx.picker_h = picker_h
        ctx.picker_s = picker_s
        ctx.picker_v = picker_v
        ctx.new_text_stroke = new_text_stroke
        r = _text_entry.commit(ctx)
        text_entry = ctx.text_entry
        selected_strokes = ctx.selected_strokes
        selected_point = ctx.selected_point
        selected_curve = ctx.selected_curve
        selected_curves = ctx.selected_curves
        return r

    def _xform_ctx():
        import types as _types
        ctx = _types.SimpleNamespace()
        ctx.strokes = strokes
        ctx.selected_strokes = selected_strokes
        ctx.push_undo = push_undo
        ctx.combined_bbox = combined_bbox
        ctx.translate_stroke = translate_stroke
        ctx.transform_stroke = transform_stroke
        ctx.rotate_stroke_around = rotate_stroke_around
        ctx.xform_field_focus = xform_field_focus
        ctx.xform_field_buffer = xform_field_buffer
        ctx.state = state
        return ctx

    def _xform_sync(ctx):
        nonlocal xform_field_focus, xform_field_buffer
        xform_field_focus = ctx.xform_field_focus
        xform_field_buffer = ctx.xform_field_buffer

    def _xform_sel_bbox():
        ctx = _xform_ctx(); return _xform.sel_bbox(ctx)

    def _xform_current_value(field):
        ctx = _xform_ctx(); return _xform.current_value(ctx, field)

    def _apply_xform_field(field, target, relative=False):
        ctx = _xform_ctx(); r = _xform.apply_field(ctx, field, target, relative=relative); _xform_sync(ctx); return r

    def _commit_xform_field():
        ctx = _xform_ctx(); r = _xform.commit_field(ctx); _xform_sync(ctx); return r

    def _cancel_xform_field():
        ctx = _xform_ctx(); _xform.cancel_field(ctx); _xform_sync(ctx)

    # --- Bezier pen tool (click-to-place anchors, drag handles) ---
    _bezier_last_click = {"time": 0, "pos": (0.0, 0.0)}

    def _bp_ctx():
        import types as _types
        ctx = _types.SimpleNamespace()
        ctx.bezier_pen = bezier_pen
        ctx.strokes = strokes
        ctx.selected_strokes = selected_strokes
        ctx.selected_point = selected_point
        ctx.selected_curve = selected_curve
        ctx.selected_curves = selected_curves
        ctx.push_undo = push_undo
        ctx.new_stroke = new_stroke
        ctx.merge_connected_strokes = merge_connected_strokes
        ctx._close_path_if_needed = _close_path_if_needed
        return ctx

    def _bp_sync(ctx):
        nonlocal bezier_pen, strokes, selected_strokes, selected_point, selected_curve, selected_curves
        bezier_pen = ctx.bezier_pen
        strokes = ctx.strokes
        selected_strokes = ctx.selected_strokes
        selected_point = ctx.selected_point
        selected_curve = ctx.selected_curve
        selected_curves = ctx.selected_curves

    def _bezier_pen_cancel():
        ctx = _bp_ctx(); _bp.cancel(ctx); _bp_sync(ctx)

    def _bezier_pen_finish(close_path=False):
        ctx = _bp_ctx(); r = _bp.finish(ctx, close_path=close_path); _bp_sync(ctx); return r

    def _bezier_pen_add_anchor(pos):
        ctx = _bp_ctx(); _bp.add_anchor(ctx, pos); _bp_sync(ctx)

    def _bezier_pen_update_drag(pos):
        ctx = _bp_ctx(); _bp.update_drag(ctx, pos); _bp_sync(ctx)

    def _bezier_pen_near_first(pos, radius=10.0):
        ctx = _bp_ctx(); return _bp.near_first(ctx, pos, radius=radius)

    def _bezier_pen_commit_or_cancel():
        ctx = _bp_ctx(); r = _bp.commit_or_cancel(ctx); _bp_sync(ctx); return r



    def snap_world(pos, threshold_px=8.0):
        return _snap.snap_world(pos, guides, cfg, threshold_px=threshold_px)

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        _frame.compute_hover_snap()

        stroke_swatch_rects = list(swatch_rects_cache["stroke"])
        fill_swatch_rects = list(swatch_rects_cache["fill"])
        # sanitize selection indices
        selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
        sel_list = sorted(selected_strokes)
        primary = sel_list[0] if len(sel_list) == 1 else (sel_list[0] if sel_list else None)
        sel_obj = strokes[primary] if primary is not None else None
        bb = combined_bbox(strokes, sel_list) if sel_list else None
        # reset custom pivot and transform mode when selection is cleared or membership changes
        if not selected_strokes or selected_strokes != prev_selection_set:
            pivot_pos = None
            transform_handle_mode = "scale"
            xform_field_focus = None
            xform_field_buffer = ""
        prev_selection_set = set(selected_strokes)
        if selected_curve is not None:
            si, comp_i = selected_curve
            comps = _stroke_components(strokes[si]) if 0 <= si < len(strokes) else []
            if si not in selected_strokes or not (0 <= si < len(strokes)) or not (0 <= comp_i < len(comps)):
                selected_curve = None
                redrawing_curve = None
        if redrawing_curve is not None:
            rsi = redrawing_curve.get("stroke_idx")
            rcomp = redrawing_curve.get("comp_idx", redrawing_curve.get("seg_idx"))
            comps = _stroke_components(strokes[rsi]) if 0 <= rsi < len(strokes) else []
            if rsi not in selected_strokes or not (0 <= rsi < len(strokes)) or not (0 <= rcomp < len(comps)):
                redrawing_curve = None
        state_selected_curve = selected_curve
        state_selected_curves = set(selected_curves)
        state_redrawing_curve = redrawing_curve
        if draw_shape in ("rect", "square"):
            rect_variant = draw_shape
        if draw_shape in ("ellipse", "circle"):
            ellipse_variant = draw_shape
        state = {
            "tool_mode": tool_mode, "max_points": max_points_per_curve, "boost_points": boost_points,
            "workspace": workspace,
            "snap_enabled": snap_enabled,
            "show_grid": bool(getattr(cfg, "SHOW_GRID", False)),
            "show_rulers": bool(getattr(cfg, "SHOW_RULERS", False)),
            "snap_to_grid": bool(getattr(cfg, "SNAP_TO_GRID", False)),
            "guides": [dict(g) for g in guides],
            "guide_count": len(guides),
            "NORMAL_MAX_POINTS": NORMAL_MAX_POINTS, "BOOST_MAX_POINTS": BOOST_MAX_POINTS,
            "slider": slider, "width_slider": width_slider, "buttons": buttons,
            "stroke_count": len(strokes), "strokes": strokes, "selected_strokes": set(selected_strokes), "selected_obj": sel_obj,
            "text_edit_rect": text_edit_rect_cache,
            "text_font_rect": text_font_rect_cache,
            "text_size_minus_rect": text_size_minus_rect_cache,
            "text_size_plus_rect": text_size_plus_rect_cache,
            "text_on_path_rect": text_on_path_rect_cache,
            "text_off_path_rect": text_off_path_rect_cache,
            "text_font_families": FONT_FAMILIES,
            "text_entry_active": text_entry is not None,
            "text_entry_text": str(text_entry.get("text", "")) if text_entry else "",
            "stroke_swatch_rects": stroke_swatch_rects, "fill_swatch_rects": fill_swatch_rects,
            "color_target": color_target, "picker_h": picker_h, "picker_s": picker_s, "picker_v": picker_v,
            "picker_drag_sv": picker_drag_sv, "picker_drag_hue": picker_drag_hue, "picker_drag_alpha": picker_drag_alpha,
            "sv_rect": picker_rects["sv"], "hue_rect": picker_rects["hue"],
            "tab_stroke_rect": picker_rects["tab_stroke"], "tab_fill_rect": picker_rects["tab_fill"],
            "nofill_rect": picker_rects["nofill"], "alpha_rect": picker_rects["alpha"],
            "fill_type_prev_rect": fill_type_prev_rect_cache, "fill_type_next_rect": fill_type_next_rect_cache, "fill_stop_rects": dict(fill_stop_rects_cache),
            "fill_stop_add_rect": fill_stop_add_rect_cache, "fill_stop_remove_rect": fill_stop_remove_rect_cache,
            "fill_stop_pos_rect": fill_stop_pos_rect_cache, "fill_gradient_stop": fill_gradient_stop,
            "pattern_type_rect": pattern_type_rect_cache,
            "pattern_size_minus_rect": pattern_size_minus_rect_cache,
            "pattern_size_plus_rect": pattern_size_plus_rect_cache,
            "fill_stop_pos_drag": fill_stop_pos_drag,
            "selection_submode": selection_submode,
            "selection_bbox": bb,
            "nodes_mode_prev_rect": nodes_mode_prev_rect_cache,
            "nodes_mode_next_rect": nodes_mode_next_rect_cache,
            "elev_front_rect": elev_front_rect_cache,
            "elev_forward_rect": elev_forward_rect_cache,
            "elev_backward_rect": elev_backward_rect_cache,
            "elev_back_rect": elev_back_rect_cache,
            "bool_union_rect": bool_union_rect_cache,
            "bool_intersect_rect": bool_intersect_rect_cache,
            "bool_subtract_rect": bool_subtract_rect_cache,
            "bool_exclude_rect": bool_exclude_rect_cache,
            "distribute_h_rect": distribute_h_rect_cache,
            "distribute_v_rect": distribute_v_rect_cache,
            "path_close_rect": path_close_rect_cache,
            "path_reverse_rect": path_reverse_rect_cache,
            "path_add_rect": path_add_rect_cache,
            "path_delete_rect": path_delete_rect_cache,
            "path_smooth_rect": path_smooth_rect_cache,
            "path_corner_rect": path_corner_rect_cache,
            "path_expand_rect": path_expand_rect_cache,
            "obj_opacity_rect": obj_opacity_rect_cache,

            "shadow_toggle_rect": shadow_toggle_rect_cache,
            "shadow_blur_minus_rect": shadow_blur_minus_rect_cache,
            "shadow_blur_plus_rect": shadow_blur_plus_rect_cache,
            "cap_prev_rect": cap_prev_rect_cache,
            "cap_next_rect": cap_next_rect_cache,
            "join_prev_rect": join_prev_rect_cache,
            "join_next_rect": join_next_rect_cache,
            "dash_prev_rect": dash_prev_rect_cache,
            "dash_next_rect": dash_next_rect_cache,
            "marker_start_rect": marker_start_rect_cache,
            "marker_end_rect": marker_end_rect_cache,
            "marker_dropdown": marker_dropdown,
            "marker_dropdown_rect": marker_dropdown_rect,
            "marker_dropdown_item_rects": marker_dropdown_item_rects,
            "width_profile_prev_rect": width_profile_prev_rect_cache,
            "width_profile_next_rect": width_profile_next_rect_cache,
            "obj_opacity_drag": obj_opacity_drag,
            "xform_field_focus": xform_field_focus,
            "xform_field_buffer": xform_field_buffer,
            "xform_x_rect": xform_x_rect_cache,
            "xform_y_rect": xform_y_rect_cache,
            "xform_w_rect": xform_w_rect_cache,
            "xform_h_rect": xform_h_rect_cache,
            "xform_r_rect": xform_r_rect_cache,
            "xform_xm_rect": xform_xm_rect_cache,
            "xform_xp_rect": xform_xp_rect_cache,
            "xform_ym_rect": xform_ym_rect_cache,
            "xform_yp_rect": xform_yp_rect_cache,
            "xform_wm_rect": xform_wm_rect_cache,
            "xform_wp_rect": xform_wp_rect_cache,
            "xform_hm_rect": xform_hm_rect_cache,
            "xform_hp_rect": xform_hp_rect_cache,
            "xform_rm_rect": xform_rm_rect_cache,
            "xform_rp_rect": xform_rp_rect_cache,
            "mirror_h_rect": mirror_h_rect_cache,
            "mirror_v_rect": mirror_v_rect_cache,
            "align_left_rect": align_left_rect_cache,
            "align_hcenter_rect": align_hcenter_rect_cache,
            "align_right_rect": align_right_rect_cache,
            "align_top_rect": align_top_rect_cache,
            "align_vmiddle_rect": align_vmiddle_rect_cache,
            "align_bottom_rect": align_bottom_rect_cache,
            "trace_algorithm": trace_algorithm,
            "trace_algo_prev_rect": trace_algo_prev_rect_cache,
            "trace_algo_next_rect": trace_algo_next_rect_cache,
            "draw_tool_prev_rect": draw_tool_prev_rect_cache,
            "draw_tool_next_rect": draw_tool_next_rect_cache,
            "draw_shape": draw_shape,
            "draw_shape_rects": draw_shape_rects_cache,
            "draw_shape_variant": triangle_variant,
            "rect_variant": rect_variant,
            "ellipse_variant": ellipse_variant,
            "line_constrain": line_constrain,
            "line_arrow": line_arrow,
            "corner_radius": corner_radius,
            "ellipse_segments": ellipse_segments,
            "polygon_sides": polygon_sides,
            "star_points": star_points,
            "star_inner_ratio": star_inner_ratio,
            "shape_menu_key": shape_menu_key,
            "shape_menu_anchor": shape_menu_anchor,
            "shape_menu_rect": shape_menu_rect,
            "shape_menu_item_rects": shape_menu_item_rects,
            "panel_collapsed": panel_collapsed,
            "panel_toggle_rect": panel_toggle_rect_cache,
            "workspace_rect": pygame.Rect(0, 0, 0, 0),
            "draw_tool": draw_tool,
            "draw_tool_pen_rect": draw_tool_pen_rect_cache,
            "draw_tool_eraser_rect": draw_tool_eraser_rect_cache,
            "draw_tool_bucket_rect": draw_tool_bucket_rect_cache,
            "draw_tool_cutter_rect": draw_tool_cutter_rect_cache,
            "bezier_pen": bezier_pen,
            "bucket_fill_color": bucket_fill_color,
            "bucket_picker_h": bucket_picker_h,
            "bucket_picker_s": bucket_picker_s,
            "bucket_picker_v": bucket_picker_v,
            "bucket_picker_drag": bucket_picker_drag,
            "bucket_sv_rect": bucket_sv_rect_cache,
            "bucket_hue_rect": bucket_hue_rect_cache,
            "bucket_swatch_rects": bucket_swatch_rects_cache,
            "snap_toggle_rect": snap_toggle_rect_cache,
            "selected_curve": state_selected_curve,
            "selected_curves": state_selected_curves,
            "selected_point": selected_point,
            "redrawing_curve": state_redrawing_curve,
            "curve_hide_rect": curve_hide_rect_cache,
            "curve_redraw_rect": curve_redraw_rect_cache,
            "curve_cut_rect": curve_cut_rect_cache,
            "curve_join_rect": curve_join_rect_cache,
            "curve_cut_mode": curve_cut_mode,
            "eyedropper_pick": eyedropper_pick,
            "eyedropper_rect": eyedropper_rect_cache,
            "cut_gap": cut_gap,
            "cut_gap_slider": cut_gap_slider,
            "wave_toggle_rect": wave_toggle_rect_cache,
            "wave_add_rect": wave_add_rect_cache,
            "displacement_add_rect": displacement_add_rect_cache,
            "repeat_add_rect": repeat_add_rect_cache,
            "thickness_add_rect": thickness_add_rect_cache,
            "wave_remove_rect": wave_remove_rect_cache,
            "wave_bake_rect": wave_bake_rect_cache,
            "wave_shape_prev_rect": wave_shape_prev_rect_cache,
            "wave_shape_next_rect": wave_shape_next_rect_cache,
            "displacement_profile_rects": displacement_profile_rects_cache,
            "displacement_affect_rects": displacement_affect_rects_cache,
            "wave_formula_rect": wave_formula_rect_cache,
            "wave_formula_focus": wave_formula_focus,
            "wave_custom_draw": wave_custom_draw,
            "repeat_pick_mode": repeat_pick_mode,
            "repeat_pick_target": repeat_pick_target,
            "wave_custom_box_rect": wave_custom_box_rect_cache,
            "wave_smooth_rect": wave_smooth_rect_cache,
            "wave_clear_rect": wave_clear_rect_cache,
            "wave_done_rect": wave_done_rect_cache,
            "repeat_pick_curve_rect": repeat_pick_curve_rect_cache,
            "wave_reverse_rect": wave_reverse_rect_cache,
            "wave_clamp_rect": wave_clamp_rect_cache,
            "wave_custom_drag": wave_custom_drag,
            "wave_active_index": wave_active_index,
            "wave_row_rects": wave_row_rects_cache,
            "wave_custom_finished": wave_custom_finished,
            "panel_scroll": panel_scroll,
            "export_scale": export_scale,
            "export_dpi": export_dpi,
            "export_dialog_open": export_dialog_open,
            "export_dialog_format": export_dialog_format,
            "export_dialog_rects": export_dialog_rects,
            "wave_slider_rects": wave_slider_rects_cache,
            "strokes": strokes,
            "reference_image": reference_image,
            "reference_error": reference_error,
            "ref_load_rect": ref_load_rect_cache,
            "ref_vis_rect": ref_vis_rect_cache,
            "ref_clear_rect": ref_clear_rect_cache,
            "ref_opacity_rect": ref_opacity_rect_cache,
        }

        def run_menu_action(key):
            import types
            nonlocal _shape_state_counter, _symbol_counter, active_artboard, artboards, clipboard_strokes, current_points, curve_cut_mode, cut_points, cutting, document_path, drag_last, draw_tool, drawing, export_dialog_format, export_dialog_open, eyedropper_pick, help_open, panel_collapsed, redrawing_curve, running, selected_curve, selected_curves, selected_point, selected_strokes, selection_submode, shape_states, snap_enabled, symbols, text_entry, text_family, text_size, tool_mode, transform_drag, workspace
            s = types.SimpleNamespace(
                _shape_state_counter=_shape_state_counter, _symbol_counter=_symbol_counter,
                active_artboard=active_artboard, artboards=artboards, clipboard_strokes=clipboard_strokes,
                current_points=current_points, curve_cut_mode=curve_cut_mode, cut_points=cut_points,
                cutting=cutting, document_path=document_path, drag_last=drag_last, draw_tool=draw_tool,
                drawing=drawing, export_dialog_format=export_dialog_format, export_dialog_open=export_dialog_open,
                eyedropper_pick=eyedropper_pick, help_open=help_open, panel_collapsed=panel_collapsed,
                redrawing_curve=redrawing_curve, running=running, selected_curve=selected_curve,
                selected_curves=selected_curves, selected_point=selected_point, selected_strokes=selected_strokes,
                selection_submode=selection_submode, shape_states=shape_states, snap_enabled=snap_enabled,
                symbols=symbols, text_entry=text_entry, text_family=text_family, text_size=text_size,
                tool_mode=tool_mode, transform_drag=transform_drag, workspace=workspace,
                _bezier_pen_cancel=_bezier_pen_cancel, _bezier_pen_commit_or_cancel=_bezier_pen_commit_or_cancel,
                _capture_shape_state=_capture_shape_state, _copy_stroke=_copy_stroke,
                _delete_shape_state=_delete_shape_state, _insert_shape_state=_insert_shape_state,
                assign_group=assign_group, cfg=cfg, clear_group=clear_group, combined_bbox=combined_bbox,
                copy=copy, do_redo=do_redo, do_undo=do_undo, import_svg=import_svg,
                load_document_with_meta=load_document_with_meta, new_group_id=new_group_id,
                pick_import_svg_path=pick_import_svg_path, pick_open_document_path=pick_open_document_path,
                pick_save_document_path=pick_save_document_path, push_undo=push_undo, relayout=relayout,
                save_document=save_document, state=state, strokes=strokes, translate_stroke=translate_stroke,
            )
            result = _menu_dispatch.run_menu_action(key, s)
            _shape_state_counter = s._shape_state_counter; _symbol_counter = s._symbol_counter
            active_artboard = s.active_artboard; artboards = s.artboards; clipboard_strokes = s.clipboard_strokes
            current_points = s.current_points; curve_cut_mode = s.curve_cut_mode; cut_points = s.cut_points
            cutting = s.cutting; document_path = s.document_path; drag_last = s.drag_last
            draw_tool = s.draw_tool; drawing = s.drawing; export_dialog_format = s.export_dialog_format
            export_dialog_open = s.export_dialog_open; eyedropper_pick = s.eyedropper_pick
            help_open = s.help_open; panel_collapsed = s.panel_collapsed; redrawing_curve = s.redrawing_curve
            running = s.running; selected_curve = s.selected_curve; selected_curves = s.selected_curves
            selected_point = s.selected_point; selected_strokes = s.selected_strokes
            selection_submode = s.selection_submode; shape_states = s.shape_states; snap_enabled = s.snap_enabled
            symbols = s.symbols; text_entry = s.text_entry; text_family = s.text_family; text_size = s.text_size
            tool_mode = s.tool_mode; transform_drag = s.transform_drag; workspace = s.workspace
            return result

        # Event loop (extracted)
        _frame.process_event_frame()
        # Render frame (extracted)
        import types as _types
        _rf_ctx=_types.SimpleNamespace()
        _rf_ctx.__dict__.update({k:v for k,v in locals().items()})
        from controllers.render_frame import render_frame as _rf
        _rf(_rf_ctx)
        if hasattr(_rf_ctx,'_n'): _n=_rf_ctx._n
        if hasattr(_rf_ctx,'active'): active=_rf_ctx.active
        if hasattr(_rf_ctx,'align_bottom_rect_cache'): align_bottom_rect_cache=_rf_ctx.align_bottom_rect_cache
        if hasattr(_rf_ctx,'align_hcenter_rect_cache'): align_hcenter_rect_cache=_rf_ctx.align_hcenter_rect_cache
        if hasattr(_rf_ctx,'align_left_rect_cache'): align_left_rect_cache=_rf_ctx.align_left_rect_cache
        if hasattr(_rf_ctx,'align_right_rect_cache'): align_right_rect_cache=_rf_ctx.align_right_rect_cache
        if hasattr(_rf_ctx,'align_top_rect_cache'): align_top_rect_cache=_rf_ctx.align_top_rect_cache
        if hasattr(_rf_ctx,'align_vmiddle_rect_cache'): align_vmiddle_rect_cache=_rf_ctx.align_vmiddle_rect_cache
        if hasattr(_rf_ctx,'bool_exclude_rect_cache'): bool_exclude_rect_cache=_rf_ctx.bool_exclude_rect_cache
        if hasattr(_rf_ctx,'bool_intersect_rect_cache'): bool_intersect_rect_cache=_rf_ctx.bool_intersect_rect_cache
        if hasattr(_rf_ctx,'bool_subtract_rect_cache'): bool_subtract_rect_cache=_rf_ctx.bool_subtract_rect_cache
        if hasattr(_rf_ctx,'bool_union_rect_cache'): bool_union_rect_cache=_rf_ctx.bool_union_rect_cache
        if hasattr(_rf_ctx,'bucket_hue_rect_cache'): bucket_hue_rect_cache=_rf_ctx.bucket_hue_rect_cache
        if hasattr(_rf_ctx,'bucket_picker_h'): bucket_picker_h=_rf_ctx.bucket_picker_h
        if hasattr(_rf_ctx,'bucket_picker_s'): bucket_picker_s=_rf_ctx.bucket_picker_s
        if hasattr(_rf_ctx,'bucket_picker_v'): bucket_picker_v=_rf_ctx.bucket_picker_v
        if hasattr(_rf_ctx,'bucket_sv_rect_cache'): bucket_sv_rect_cache=_rf_ctx.bucket_sv_rect_cache
        if hasattr(_rf_ctx,'bucket_swatch_rects_cache'): bucket_swatch_rects_cache=_rf_ctx.bucket_swatch_rects_cache
        if hasattr(_rf_ctx,'cap_next_rect_cache'): cap_next_rect_cache=_rf_ctx.cap_next_rect_cache
        if hasattr(_rf_ctx,'cap_prev_rect_cache'): cap_prev_rect_cache=_rf_ctx.cap_prev_rect_cache
        if hasattr(_rf_ctx,'cfg'): cfg=_rf_ctx.cfg
        if hasattr(_rf_ctx,'clock'): clock=_rf_ctx.clock
        if hasattr(_rf_ctx,'color_target'): color_target=_rf_ctx.color_target
        if hasattr(_rf_ctx,'current_points'): current_points=_rf_ctx.current_points
        if hasattr(_rf_ctx,'curve_cut_rect_cache'): curve_cut_rect_cache=_rf_ctx.curve_cut_rect_cache
        if hasattr(_rf_ctx,'curve_hide_rect_cache'): curve_hide_rect_cache=_rf_ctx.curve_hide_rect_cache
        if hasattr(_rf_ctx,'curve_join_rect_cache'): curve_join_rect_cache=_rf_ctx.curve_join_rect_cache
        if hasattr(_rf_ctx,'curve_redraw_rect_cache'): curve_redraw_rect_cache=_rf_ctx.curve_redraw_rect_cache
        if hasattr(_rf_ctx,'dash_next_rect_cache'): dash_next_rect_cache=_rf_ctx.dash_next_rect_cache
        if hasattr(_rf_ctx,'dash_prev_rect_cache'): dash_prev_rect_cache=_rf_ctx.dash_prev_rect_cache
        if hasattr(_rf_ctx,'displacement_add_rect_cache'): displacement_add_rect_cache=_rf_ctx.displacement_add_rect_cache
        if hasattr(_rf_ctx,'displacement_affect_rects_cache'): displacement_affect_rects_cache=_rf_ctx.displacement_affect_rects_cache
        if hasattr(_rf_ctx,'displacement_profile_rects_cache'): displacement_profile_rects_cache=_rf_ctx.displacement_profile_rects_cache
        if hasattr(_rf_ctx,'distribute_h_rect_cache'): distribute_h_rect_cache=_rf_ctx.distribute_h_rect_cache
        if hasattr(_rf_ctx,'distribute_v_rect_cache'): distribute_v_rect_cache=_rf_ctx.distribute_v_rect_cache
        if hasattr(_rf_ctx,'draw_shape_rects_cache'): draw_shape_rects_cache=_rf_ctx.draw_shape_rects_cache
        if hasattr(_rf_ctx,'draw_tool_bucket_rect_cache'): draw_tool_bucket_rect_cache=_rf_ctx.draw_tool_bucket_rect_cache
        if hasattr(_rf_ctx,'draw_tool_cutter_rect_cache'): draw_tool_cutter_rect_cache=_rf_ctx.draw_tool_cutter_rect_cache
        if hasattr(_rf_ctx,'draw_tool_eraser_rect_cache'): draw_tool_eraser_rect_cache=_rf_ctx.draw_tool_eraser_rect_cache
        if hasattr(_rf_ctx,'draw_tool_next_rect_cache'): draw_tool_next_rect_cache=_rf_ctx.draw_tool_next_rect_cache
        if hasattr(_rf_ctx,'draw_tool_pen_rect_cache'): draw_tool_pen_rect_cache=_rf_ctx.draw_tool_pen_rect_cache
        if hasattr(_rf_ctx,'draw_tool_prev_rect_cache'): draw_tool_prev_rect_cache=_rf_ctx.draw_tool_prev_rect_cache
        if hasattr(_rf_ctx,'drawing'): drawing=_rf_ctx.drawing
        if hasattr(_rf_ctx,'elev_back_rect_cache'): elev_back_rect_cache=_rf_ctx.elev_back_rect_cache
        if hasattr(_rf_ctx,'elev_backward_rect_cache'): elev_backward_rect_cache=_rf_ctx.elev_backward_rect_cache
        if hasattr(_rf_ctx,'elev_forward_rect_cache'): elev_forward_rect_cache=_rf_ctx.elev_forward_rect_cache
        if hasattr(_rf_ctx,'elev_front_rect_cache'): elev_front_rect_cache=_rf_ctx.elev_front_rect_cache
        if hasattr(_rf_ctx,'export_dialog_rects'): export_dialog_rects=_rf_ctx.export_dialog_rects
        if hasattr(_rf_ctx,'export_dpi'): export_dpi=_rf_ctx.export_dpi
        if hasattr(_rf_ctx,'export_scale'): export_scale=_rf_ctx.export_scale
        if hasattr(_rf_ctx,'eyedropper_rect_cache'): eyedropper_rect_cache=_rf_ctx.eyedropper_rect_cache
        if hasattr(_rf_ctx,'fill_gradient_stop'): fill_gradient_stop=_rf_ctx.fill_gradient_stop
        if hasattr(_rf_ctx,'fill_stop_add_rect_cache'): fill_stop_add_rect_cache=_rf_ctx.fill_stop_add_rect_cache
        if hasattr(_rf_ctx,'fill_stop_pos_drag'): fill_stop_pos_drag=_rf_ctx.fill_stop_pos_drag
        if hasattr(_rf_ctx,'fill_stop_pos_rect_cache'): fill_stop_pos_rect_cache=_rf_ctx.fill_stop_pos_rect_cache
        if hasattr(_rf_ctx,'fill_stop_rects_cache'): fill_stop_rects_cache=_rf_ctx.fill_stop_rects_cache
        if hasattr(_rf_ctx,'fill_stop_remove_rect_cache'): fill_stop_remove_rect_cache=_rf_ctx.fill_stop_remove_rect_cache
        if hasattr(_rf_ctx,'fill_type_next_rect_cache'): fill_type_next_rect_cache=_rf_ctx.fill_type_next_rect_cache
        if hasattr(_rf_ctx,'fill_type_prev_rect_cache'): fill_type_prev_rect_cache=_rf_ctx.fill_type_prev_rect_cache
        if hasattr(_rf_ctx,'frame'): frame=_rf_ctx.frame
        if hasattr(_rf_ctx,'guides'): guides=_rf_ctx.guides
        if hasattr(_rf_ctx,'join_next_rect_cache'): join_next_rect_cache=_rf_ctx.join_next_rect_cache
        if hasattr(_rf_ctx,'join_prev_rect_cache'): join_prev_rect_cache=_rf_ctx.join_prev_rect_cache
        if hasattr(_rf_ctx,'marker_dropdown'): marker_dropdown=_rf_ctx.marker_dropdown
        if hasattr(_rf_ctx,'marker_dropdown_item_rects'): marker_dropdown_item_rects=_rf_ctx.marker_dropdown_item_rects
        if hasattr(_rf_ctx,'marker_dropdown_rect'): marker_dropdown_rect=_rf_ctx.marker_dropdown_rect
        if hasattr(_rf_ctx,'marker_end_rect_cache'): marker_end_rect_cache=_rf_ctx.marker_end_rect_cache
        if hasattr(_rf_ctx,'marker_start_rect_cache'): marker_start_rect_cache=_rf_ctx.marker_start_rect_cache
        if hasattr(_rf_ctx,'menu_bar_rects'): menu_bar_rects=_rf_ctx.menu_bar_rects
        if hasattr(_rf_ctx,'menu_item_rects'): menu_item_rects=_rf_ctx.menu_item_rects
        if hasattr(_rf_ctx,'mirror_h_rect_cache'): mirror_h_rect_cache=_rf_ctx.mirror_h_rect_cache
        if hasattr(_rf_ctx,'mirror_v_rect_cache'): mirror_v_rect_cache=_rf_ctx.mirror_v_rect_cache
        if hasattr(_rf_ctx,'nodes_mode_next_rect_cache'): nodes_mode_next_rect_cache=_rf_ctx.nodes_mode_next_rect_cache
        if hasattr(_rf_ctx,'nodes_mode_prev_rect_cache'): nodes_mode_prev_rect_cache=_rf_ctx.nodes_mode_prev_rect_cache
        if hasattr(_rf_ctx,'obj_opacity_drag'): obj_opacity_drag=_rf_ctx.obj_opacity_drag
        if hasattr(_rf_ctx,'obj_opacity_rect_cache'): obj_opacity_rect_cache=_rf_ctx.obj_opacity_rect_cache
        if hasattr(_rf_ctx,'p'): p=_rf_ctx.p
        if hasattr(_rf_ctx,'panel_collapsed'): panel_collapsed=_rf_ctx.panel_collapsed
        if hasattr(_rf_ctx,'panel_scroll'): panel_scroll=_rf_ctx.panel_scroll
        if hasattr(_rf_ctx,'panel_toggle_rect_cache'): panel_toggle_rect_cache=_rf_ctx.panel_toggle_rect_cache
        if hasattr(_rf_ctx,'path_add_rect_cache'): path_add_rect_cache=_rf_ctx.path_add_rect_cache
        if hasattr(_rf_ctx,'path_close_rect_cache'): path_close_rect_cache=_rf_ctx.path_close_rect_cache
        if hasattr(_rf_ctx,'path_corner_rect_cache'): path_corner_rect_cache=_rf_ctx.path_corner_rect_cache
        if hasattr(_rf_ctx,'path_delete_rect_cache'): path_delete_rect_cache=_rf_ctx.path_delete_rect_cache
        if hasattr(_rf_ctx,'path_expand_rect_cache'): path_expand_rect_cache=_rf_ctx.path_expand_rect_cache
        if hasattr(_rf_ctx,'path_reverse_rect_cache'): path_reverse_rect_cache=_rf_ctx.path_reverse_rect_cache
        if hasattr(_rf_ctx,'path_smooth_rect_cache'): path_smooth_rect_cache=_rf_ctx.path_smooth_rect_cache
        if hasattr(_rf_ctx,'pattern_size_minus_rect_cache'): pattern_size_minus_rect_cache=_rf_ctx.pattern_size_minus_rect_cache
        if hasattr(_rf_ctx,'pattern_size_plus_rect_cache'): pattern_size_plus_rect_cache=_rf_ctx.pattern_size_plus_rect_cache
        if hasattr(_rf_ctx,'pattern_type_rect_cache'): pattern_type_rect_cache=_rf_ctx.pattern_type_rect_cache
        if hasattr(_rf_ctx,'picker_h'): picker_h=_rf_ctx.picker_h
        if hasattr(_rf_ctx,'picker_s'): picker_s=_rf_ctx.picker_s
        if hasattr(_rf_ctx,'picker_v'): picker_v=_rf_ctx.picker_v
        if hasattr(_rf_ctx,'pivot_pos'): pivot_pos=_rf_ctx.pivot_pos
        if hasattr(_rf_ctx,'primary_i'): primary_i=_rf_ctx.primary_i
        if hasattr(_rf_ctx,'pts'): pts=_rf_ctx.pts
        if hasattr(_rf_ctx,'r'): r=_rf_ctx.r
        if hasattr(_rf_ctx,'rect'): rect=_rf_ctx.rect
        if hasattr(_rf_ctx,'redrawing_curve'): redrawing_curve=_rf_ctx.redrawing_curve
        if hasattr(_rf_ctx,'ref_clear_rect_cache'): ref_clear_rect_cache=_rf_ctx.ref_clear_rect_cache
        if hasattr(_rf_ctx,'ref_load_rect_cache'): ref_load_rect_cache=_rf_ctx.ref_load_rect_cache
        if hasattr(_rf_ctx,'ref_opacity_rect_cache'): ref_opacity_rect_cache=_rf_ctx.ref_opacity_rect_cache
        if hasattr(_rf_ctx,'ref_vis_rect_cache'): ref_vis_rect_cache=_rf_ctx.ref_vis_rect_cache
        if hasattr(_rf_ctx,'repeat_add_rect_cache'): repeat_add_rect_cache=_rf_ctx.repeat_add_rect_cache
        if hasattr(_rf_ctx,'repeat_pick_curve_rect_cache'): repeat_pick_curve_rect_cache=_rf_ctx.repeat_pick_curve_rect_cache
        if hasattr(_rf_ctx,'repeat_pick_mode'): repeat_pick_mode=_rf_ctx.repeat_pick_mode
        if hasattr(_rf_ctx,'repeat_pick_target'): repeat_pick_target=_rf_ctx.repeat_pick_target
        if hasattr(_rf_ctx,'running'): running=_rf_ctx.running
        if hasattr(_rf_ctx,'s1'): s1=_rf_ctx.s1
        if hasattr(_rf_ctx,'screen'): screen=_rf_ctx.screen
        if hasattr(_rf_ctx,'selected_curve'): selected_curve=_rf_ctx.selected_curve
        if hasattr(_rf_ctx,'selected_curves'): selected_curves=_rf_ctx.selected_curves
        if hasattr(_rf_ctx,'selected_point'): selected_point=_rf_ctx.selected_point
        if hasattr(_rf_ctx,'selected_strokes'): selected_strokes=_rf_ctx.selected_strokes
        if hasattr(_rf_ctx,'selection_submode'): selection_submode=_rf_ctx.selection_submode
        if hasattr(_rf_ctx,'shadow_blur_minus_rect_cache'): shadow_blur_minus_rect_cache=_rf_ctx.shadow_blur_minus_rect_cache
        if hasattr(_rf_ctx,'shadow_blur_plus_rect_cache'): shadow_blur_plus_rect_cache=_rf_ctx.shadow_blur_plus_rect_cache
        if hasattr(_rf_ctx,'shadow_toggle_rect_cache'): shadow_toggle_rect_cache=_rf_ctx.shadow_toggle_rect_cache
        if hasattr(_rf_ctx,'shape_menu_anchor'): shape_menu_anchor=_rf_ctx.shape_menu_anchor
        if hasattr(_rf_ctx,'shape_menu_item_rects'): shape_menu_item_rects=_rf_ctx.shape_menu_item_rects
        if hasattr(_rf_ctx,'shape_menu_key'): shape_menu_key=_rf_ctx.shape_menu_key
        if hasattr(_rf_ctx,'shape_menu_rect'): shape_menu_rect=_rf_ctx.shape_menu_rect
        if hasattr(_rf_ctx,'shape_states'): shape_states=_rf_ctx.shape_states
        if hasattr(_rf_ctx,'smart_snap_guides'): smart_snap_guides=_rf_ctx.smart_snap_guides
        if hasattr(_rf_ctx,'snap_toggle_rect_cache'): snap_toggle_rect_cache=_rf_ctx.snap_toggle_rect_cache
        if hasattr(_rf_ctx,'state'): state=_rf_ctx.state
        if hasattr(_rf_ctx,'strokes'): strokes=_rf_ctx.strokes
        if hasattr(_rf_ctx,'text_edit_rect_cache'): text_edit_rect_cache=_rf_ctx.text_edit_rect_cache
        if hasattr(_rf_ctx,'text_entry'): text_entry=_rf_ctx.text_entry
        if hasattr(_rf_ctx,'text_font_rect_cache'): text_font_rect_cache=_rf_ctx.text_font_rect_cache
        if hasattr(_rf_ctx,'text_off_path_rect_cache'): text_off_path_rect_cache=_rf_ctx.text_off_path_rect_cache
        if hasattr(_rf_ctx,'text_on_path_rect_cache'): text_on_path_rect_cache=_rf_ctx.text_on_path_rect_cache
        if hasattr(_rf_ctx,'text_size_minus_rect_cache'): text_size_minus_rect_cache=_rf_ctx.text_size_minus_rect_cache
        if hasattr(_rf_ctx,'text_size_plus_rect_cache'): text_size_plus_rect_cache=_rf_ctx.text_size_plus_rect_cache
        if hasattr(_rf_ctx,'thickness_add_rect_cache'): thickness_add_rect_cache=_rf_ctx.thickness_add_rect_cache
        if hasattr(_rf_ctx,'tool_mode'): tool_mode=_rf_ctx.tool_mode
        if hasattr(_rf_ctx,'trace_algo_next_rect_cache'): trace_algo_next_rect_cache=_rf_ctx.trace_algo_next_rect_cache
        if hasattr(_rf_ctx,'trace_algo_prev_rect_cache'): trace_algo_prev_rect_cache=_rf_ctx.trace_algo_prev_rect_cache
        if hasattr(_rf_ctx,'wave_active_index'): wave_active_index=_rf_ctx.wave_active_index
        if hasattr(_rf_ctx,'wave_add_rect_cache'): wave_add_rect_cache=_rf_ctx.wave_add_rect_cache
        if hasattr(_rf_ctx,'wave_bake_rect_cache'): wave_bake_rect_cache=_rf_ctx.wave_bake_rect_cache
        if hasattr(_rf_ctx,'wave_clamp_rect_cache'): wave_clamp_rect_cache=_rf_ctx.wave_clamp_rect_cache
        if hasattr(_rf_ctx,'wave_clear_rect_cache'): wave_clear_rect_cache=_rf_ctx.wave_clear_rect_cache
        if hasattr(_rf_ctx,'wave_custom_box_rect_cache'): wave_custom_box_rect_cache=_rf_ctx.wave_custom_box_rect_cache
        if hasattr(_rf_ctx,'wave_custom_drag'): wave_custom_drag=_rf_ctx.wave_custom_drag
        if hasattr(_rf_ctx,'wave_custom_draw'): wave_custom_draw=_rf_ctx.wave_custom_draw
        if hasattr(_rf_ctx,'wave_custom_finished'): wave_custom_finished=_rf_ctx.wave_custom_finished
        if hasattr(_rf_ctx,'wave_done_rect_cache'): wave_done_rect_cache=_rf_ctx.wave_done_rect_cache
        if hasattr(_rf_ctx,'wave_formula_focus'): wave_formula_focus=_rf_ctx.wave_formula_focus
        if hasattr(_rf_ctx,'wave_formula_rect_cache'): wave_formula_rect_cache=_rf_ctx.wave_formula_rect_cache
        if hasattr(_rf_ctx,'wave_remove_rect_cache'): wave_remove_rect_cache=_rf_ctx.wave_remove_rect_cache
        if hasattr(_rf_ctx,'wave_reverse_rect_cache'): wave_reverse_rect_cache=_rf_ctx.wave_reverse_rect_cache
        if hasattr(_rf_ctx,'wave_row_rects_cache'): wave_row_rects_cache=_rf_ctx.wave_row_rects_cache
        if hasattr(_rf_ctx,'wave_shape_next_rect_cache'): wave_shape_next_rect_cache=_rf_ctx.wave_shape_next_rect_cache
        if hasattr(_rf_ctx,'wave_shape_prev_rect_cache'): wave_shape_prev_rect_cache=_rf_ctx.wave_shape_prev_rect_cache
        if hasattr(_rf_ctx,'wave_slider_rects_cache'): wave_slider_rects_cache=_rf_ctx.wave_slider_rects_cache
        if hasattr(_rf_ctx,'wave_smooth_rect_cache'): wave_smooth_rect_cache=_rf_ctx.wave_smooth_rect_cache
        if hasattr(_rf_ctx,'wave_toggle_rect_cache'): wave_toggle_rect_cache=_rf_ctx.wave_toggle_rect_cache
        if hasattr(_rf_ctx,'width_profile_next_rect_cache'): width_profile_next_rect_cache=_rf_ctx.width_profile_next_rect_cache
        if hasattr(_rf_ctx,'width_profile_prev_rect_cache'): width_profile_prev_rect_cache=_rf_ctx.width_profile_prev_rect_cache
        if hasattr(_rf_ctx,'workspace'): workspace=_rf_ctx.workspace
        if hasattr(_rf_ctx,'xform_field_buffer'): xform_field_buffer=_rf_ctx.xform_field_buffer
        if hasattr(_rf_ctx,'xform_field_focus'): xform_field_focus=_rf_ctx.xform_field_focus
        if hasattr(_rf_ctx,'xform_h_rect_cache'): xform_h_rect_cache=_rf_ctx.xform_h_rect_cache
        if hasattr(_rf_ctx,'xform_hm_rect_cache'): xform_hm_rect_cache=_rf_ctx.xform_hm_rect_cache
        if hasattr(_rf_ctx,'xform_hp_rect_cache'): xform_hp_rect_cache=_rf_ctx.xform_hp_rect_cache
        if hasattr(_rf_ctx,'xform_r_rect_cache'): xform_r_rect_cache=_rf_ctx.xform_r_rect_cache
        if hasattr(_rf_ctx,'xform_rm_rect_cache'): xform_rm_rect_cache=_rf_ctx.xform_rm_rect_cache
        if hasattr(_rf_ctx,'xform_rp_rect_cache'): xform_rp_rect_cache=_rf_ctx.xform_rp_rect_cache
        if hasattr(_rf_ctx,'xform_w_rect_cache'): xform_w_rect_cache=_rf_ctx.xform_w_rect_cache
        if hasattr(_rf_ctx,'xform_wm_rect_cache'): xform_wm_rect_cache=_rf_ctx.xform_wm_rect_cache
        if hasattr(_rf_ctx,'xform_wp_rect_cache'): xform_wp_rect_cache=_rf_ctx.xform_wp_rect_cache
        if hasattr(_rf_ctx,'xform_x_rect_cache'): xform_x_rect_cache=_rf_ctx.xform_x_rect_cache
        if hasattr(_rf_ctx,'xform_xm_rect_cache'): xform_xm_rect_cache=_rf_ctx.xform_xm_rect_cache
        if hasattr(_rf_ctx,'xform_xp_rect_cache'): xform_xp_rect_cache=_rf_ctx.xform_xp_rect_cache
        if hasattr(_rf_ctx,'xform_y_rect_cache'): xform_y_rect_cache=_rf_ctx.xform_y_rect_cache
        if hasattr(_rf_ctx,'xform_ym_rect_cache'): xform_ym_rect_cache=_rf_ctx.xform_ym_rect_cache
        if hasattr(_rf_ctx,'xform_yp_rect_cache'): xform_yp_rect_cache=_rf_ctx.xform_yp_rect_cache
