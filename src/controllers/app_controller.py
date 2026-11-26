"""Controller: application state, event handling and the main loop."""

import math
import copy
import types

import pygame

import config as cfg
from config import (
    ACCENT, ACTIVE_COLOR, BG_COLOR, BOTTOM_BAR_H, BOTTOM_TOOLS, BUCKET_SWATCHES, BUTTON_BG, BUTTON_BORDER,
    BUTTON_HOVER, DRAW_SHAPES, FILL_SWATCHES, LEFT_BAR_W, MUTED_COLOR, PANEL_BG, PANEL_BORDER, PANEL_W,
    STROKE_SWATCHES, TEXT_COLOR, TOOLBAR_BG, TOP_BAR_H, TOOL_ACTIVE, TRACE_ALGORITHMS, TRIANGLE_VARIANTS, SURFACE,
    SURFACE_SUBTLE, SURFACE_ALT, SURFACE_SUNKEN, SURFACE_DISABLED, SHADOW_COLOR, BORDER_SUBTLE, BORDER_STRONG, BORDER_DISABLED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED, TEXT_ON_ACCENT, TEXT_DANGER, TEXT_WARNING, HOVER_BG, ACTIVE_BG,
    PRIMARY, PRIMARY_HOVER, PRIMARY_SOFT, DANGER, DISABLED, PLOT_BG, PLOT_BG_DISABLED, PLOT_GRID,
    PLOT_LINE_DISABLED, TOOLTIP_BG, TOOLTIP_BORDER, TOOLTIP_TEXT, CANVAS_BACKDROP, SELECTION_FILL, SELECTION_BORDER, CUT_COLOR,
    CUT_HANDLE_RADIUS, NO_SWATCH_COLOR, CUSTOM_CURVE_COLOR, HANDLE_OUTLINE, SAMPLE_PLACEHOLDER, EDITOR_SELECTION_RGB, EDITOR_ACCENT_RGB, EDITOR_ROTATION_RGB,
    EDITOR_HANDLE_FILL_RGB, EDITOR_SELECTION, EDITOR_ACCENT, EDITOR_ROTATION, EDITOR_HANDLE_FILL, EDITOR_GUIDE, EDITOR_TEMPLATE, EDITOR_HANDLE_RADIUS,
    EDITOR_HANDLE_HALF, EDITOR_SKEW_RADIUS, EDITOR_PIVOT_RADIUS, EDITOR_PIVOT_INNER_RADIUS, EDITOR_SNAP_RADIUS, EDITOR_SNAP_INNER, EDITOR_LINE_WIDTH, EDITOR_LINE_WIDTH_BOLD,
    EDITOR_LINE_WIDTH_SUBTLE, DEFAULT_STROKE_RGBA, DEFAULT_FILL_RGBA, cairo_rgb, RADIUS_XS, RADIUS_SM, RADIUS_MD, RADIUS_LG,
    RADIUS_XL, SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, BORDER_WIDTH, BORDER_WIDTH_ACTIVE,
    SHADOW_OFFSET, CONTROL_H, ICON_SIZE, MENU_WIDTH, MENU_SEPARATOR_H, PICKER_HANDLE_RADIUS, SLIDER_KNOB_RADIUS, FONT_SIZE_BODY,
    FONT_SIZE_SMALL, FONT_SIZE_TITLE, FONT_SIZE_TOOLTIP,
)  # noqa: F401

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
from controllers.commands.context import CommandContext  # noqa: E402
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
    # Shared holder survives the ctx/local sync boundary. relayout() mutates the
    # holder, so every frame renders into the current canvas even when a stale
    # flat `cairo_surface` field is copied back by _sync_back().
    cairo_surface_holder = types.SimpleNamespace(surface=cairo_surface)
    panel_collapsed = False  # right sidebar hidden -> canvas grows to the window edge

    def relayout():
        """Recompute canvas/panel geometry after a resize or sidebar toggle."""
        nonlocal cairo_surface
        panel_w = 0 if panel_collapsed else PANEL_W
        cfg.CANVAS_X = LEFT_BAR_W
        cfg.CANVAS_W = max(200, cfg.WIDTH - LEFT_BAR_W - panel_w)
        cfg.PANEL_X = LEFT_BAR_W + cfg.CANVAS_W
        cairo_surface = make_cairo_surface(cfg.CANVAS_W, cfg.canvas_viewport_height())
        cairo_surface_holder.surface = cairo_surface
        # Phase 1 (semantic split plan): typed viewport state is the source of
        # truth for this layout group; cfg module attrs remain live mirrors for
        # legacy readers until the full typed-state migration completes.
        app_state.viewport.width = cfg.WIDTH
        app_state.viewport.height = cfg.HEIGHT
        app_state.viewport.canvas_x = cfg.CANVAS_X
        app_state.viewport.canvas_w = cfg.CANVAS_W
        app_state.viewport.panel_x = cfg.PANEL_X
        app_state.viewport.panel_collapsed = panel_collapsed
        return cairo_surface

    strokes = []
    undo_stack = []
    redo_stack = []
    max_undo = 100

    def push_undo():
        _history.push_undo(app_state.document.undo_stack, app_state.document.redo_stack, app_state.document.strokes, app_state.document.max_undo)

    def do_undo():
        return _history.do_undo(app_state.document.undo_stack, app_state.document.redo_stack, app_state.document.strokes)

    def do_redo():
        return _history.do_redo(app_state.document.undo_stack, app_state.document.redo_stack, app_state.document.strokes)

    selected_strokes = set()
    selected_point = None
    from controllers.drag import DragManager
    from controllers.app_state import AppState
    drag_manager = DragManager()  # semantic drag session manager (incremental migration)
    app_state = AppState()  # typed state contract (incremental migration target)
    app_state.drag.drag_manager = drag_manager
    max_points_per_curve = 4
    NORMAL_MAX_POINTS = 5
    BOOST_MAX_POINTS = 100
    draw_shape = "freehand"  # "freehand" or standard shape key from DRAW_SHAPES
    bezier_pen = None  # active Bezier pen path: {"anchors":[{"pt","h_in","h_out"}], "dragging", "mouse_down", "down_pos", "preview_pt", "closed"}
    text_entry = None  # active text placement: {"x","y","text","family","size"}
    cut_gap = 0  # optional visible gap left by the razor (canvas px, total)

    fonts = make_fonts()
    font, font_small, font_title = fonts
    try:
        ruler_font = pygame.font.Font(None, 14)
    except Exception:
        ruler_font = font_small

    btn_undo = Button((8, TOP_BAR_H + 8, 40, 40), "")
    btn_redo = Button((8, TOP_BAR_H + 56, 40, 40), "")
    btn_draw = Button((8, TOP_BAR_H + 104, 40, 40), "")
    btn_select = Button((8, TOP_BAR_H + 152, 40, 40), "")
    btn_boost = Button((0, 0, PANEL_W - 40, 34), "Boost limit")
    buttons = {"boost": btn_boost, "actions": []}
    slider = Slider(cfg.PANEL_X + 20, 0, PANEL_W - 40, 2, NORMAL_MAX_POINTS, max_points_per_curve)
    width_slider = Slider(cfg.PANEL_X + 20, 0, PANEL_W - 40, 1, 20, 3)
    cut_gap_slider = Slider(cfg.PANEL_X + 20, 0, PANEL_W - 40, 0, 20, cut_gap)
    cut_gap_slider.track.width = 0  # shown only while the cutter/gap control is active

    # lexical bindings for nested nonlocal
    xform_field_buffer = ""
    xform_field_focus = None

    # UI cache / state locals injected by _frame.init_ui_caches() (real locals required).
    ref_opacity_drag = False
    wave_slider_drag = None
    space_panning = False
    hover_snap = None
    hover_snap_kind = "connect"
    _frame.init_ui_caches()
    menu_open = None

    SNAP_RADIUS = 22

    def snap_radius():
        return _snap.snap_radius(app_state.tools.snap_enabled, SNAP_RADIUS)

    def _alignment_guides_for_point(pt, other_strokes, sr):
        return _snap.alignment_guides_for_point(pt, other_strokes, sr, stroke_bbox)

    def _snap_move_delta(sel_indices, dx, dy):
        return _snap.snap_move_delta(app_state.document.strokes, sel_indices, dx, dy, snap_radius(), stroke_bbox, nearest_snap_point)

    def bucket_pick(rect, pos, kind):
        # Typed ToolState is passed directly; no SimpleNamespace ctx bag.
        _bucket.pick(app_state.tools, rect, pos, kind, state, clamp, hsv_to_rgb)

    def set_bucket_color(col):
        _bucket.set_color(app_state.tools, col, state, rgb_to_hsv)

    def commit_text_entry():
        # Typed substates are passed directly; no SimpleNamespace ctx bag.
        nonlocal text_entry, selected_strokes, selected_point
        r = _text_entry.commit(
            app_state.selection, app_state.document, app_state.ui,
            push_undo, hsv_to_rgb, new_text_stroke,
        )
        # Mirror typed results into legacy locals for same-frame readers.
        text_entry = app_state.ui.text_entry
        selected_strokes = app_state.selection.selected_strokes
        selected_point = app_state.selection.selected_point
        return r

    def _xform_sel_bbox():
        return _xform.sel_bbox(app_state.selection, app_state.document, combined_bbox)

    def _xform_current_value(field):
        return _xform.current_value(app_state.selection, app_state.document, field, combined_bbox)

    def _xform_services():
        return (combined_bbox, push_undo, translate_stroke, transform_stroke, rotate_stroke_around)

    def _apply_xform_field(field, target, relative=False):
        return _xform.apply_field(app_state.selection, app_state.document, field, target,
                                  *_xform_services(), relative=relative)

    def _commit_xform_field():
        nonlocal xform_field_focus, xform_field_buffer
        result = _xform.commit_field(app_state.ui, state, app_state.selection,
                                     app_state.document, *_xform_services())
        xform_field_focus = app_state.ui.xform_field_focus
        xform_field_buffer = app_state.ui.xform_field_buffer
        return result

    def _cancel_xform_field():
        nonlocal xform_field_focus, xform_field_buffer
        _xform.cancel_field(app_state.ui, state)
        xform_field_focus = app_state.ui.xform_field_focus
        xform_field_buffer = app_state.ui.xform_field_buffer

    # --- Bezier pen tool (click-to-place anchors, drag handles) ---
    _bezier_last_click = {"time": 0, "pos": (0.0, 0.0)}

    def _bp_services():
        return (push_undo, new_stroke, _close_path_if_needed, merge_connected_strokes)

    def _bezier_pen_cancel():
        _bp.cancel(app_state.tools)

    def _bezier_pen_finish(close_path=False):
        r = _bp.finish(app_state.tools, app_state.document, app_state.selection,
                       *_bp_services(), close_path=close_path)
        return r

    def _bezier_pen_add_anchor(pos):
        _bp.add_anchor(app_state.tools, pos)

    def _bezier_pen_update_drag(pos):
        _bp.update_drag(app_state.tools, pos)

    def _bezier_pen_near_first(pos, radius=10.0):
        return _bp.near_first(app_state.tools, pos, radius=radius)

    def _bezier_pen_commit_or_cancel():
        r = _bp.commit_or_cancel(app_state.tools, app_state.document,
                                 app_state.selection, *_bp_services())
        return r



    def snap_world(pos, threshold_px=8.0):
        return _snap.snap_world(pos, app_state.drag.guides, cfg, threshold_px=threshold_px)

    # Seed AppState from initialized locals (AppState becomes primary for its slice).
    try:
        app_state.sync_from_locals(locals())
    except Exception:
        pass
    while app_state.ui.running:
        # No frame-start locals->typed bridge: main() writes typed state at
        # each mutation site above; handlers mirror theirs via frame helpers.
        mouse_pos = pygame.mouse.get_pos()
        _frame.compute_hover_snap()

        stroke_swatch_rects = list(app_state.ui.swatch_rects_cache["stroke"])
        fill_swatch_rects = list(app_state.ui.swatch_rects_cache["fill"])
        # sanitize selection indices in typed state (sole owner), then mirror
        selected_strokes = {i for i in app_state.selection.selected_strokes if 0 <= i < len(strokes)}
        app_state.selection.selected_strokes = selected_strokes
        sel_list = sorted(selected_strokes)
        primary = sel_list[0] if len(sel_list) == 1 else (sel_list[0] if sel_list else None)
        sel_obj = strokes[primary] if primary is not None else None
        bb = combined_bbox(strokes, sel_list) if sel_list else None
        # reset custom pivot and transform mode when selection is cleared or membership changes
        if not selected_strokes or selected_strokes != app_state.selection.prev_selection_set:
            app_state.drag.pivot_pos = None
            app_state.selection.transform_handle_mode = "scale"
            app_state.ui.xform_field_focus = None
            app_state.ui.xform_field_buffer = ""
            pivot_pos = None
            transform_handle_mode = "scale"
            xform_field_focus = None
            xform_field_buffer = ""
        app_state.selection.prev_selection_set = set(selected_strokes)
        prev_selection_set = app_state.selection.prev_selection_set
        # Sanitize curve selection in typed AppState (sole owner; no mirrors).
        if app_state.selection.selected_curve is not None:
            si, comp_i = app_state.selection.selected_curve
            comps = _stroke_components(app_state.document.strokes[si]) if 0 <= si < len(app_state.document.strokes) else []
            if (si not in selected_strokes or not (0 <= si < len(app_state.document.strokes))
                    or not (0 <= comp_i < len(comps))):
                app_state.selection.selected_curve = None
                app_state.drag.redrawing_curve = None
        if app_state.drag.redrawing_curve is not None:
            rsi = app_state.drag.redrawing_curve.get("stroke_idx")
            rcomp = app_state.drag.redrawing_curve.get("comp_idx", app_state.drag.redrawing_curve.get("seg_idx"))
            comps = _stroke_components(app_state.document.strokes[rsi]) if 0 <= rsi < len(app_state.document.strokes) else []
            if (rsi not in selected_strokes or not (0 <= rsi < len(app_state.document.strokes))
                    or not (0 <= rcomp < len(comps))):
                app_state.drag.redrawing_curve = None
        if app_state.tools.draw_shape in ("rect", "square"):
            app_state.tools.rect_variant = draw_shape
            rect_variant = draw_shape
        if app_state.tools.draw_shape in ("ellipse", "circle"):
            app_state.tools.ellipse_variant = draw_shape
            ellipse_variant = draw_shape
        state = {
            "tool_mode": app_state.tools.tool_mode, "max_points": app_state.tools.max_points_per_curve, "boost_points": app_state.tools.boost_points,
            "workspace": app_state.ui.workspace,
            "snap_enabled": app_state.tools.snap_enabled,
            "show_grid": bool(getattr(cfg, "SHOW_GRID", False)),
            "show_rulers": bool(getattr(cfg, "SHOW_RULERS", False)),
            "snap_to_grid": bool(getattr(cfg, "SNAP_TO_GRID", False)),
            "guides": [dict(g) for g in app_state.drag.guides],
            "guide_count": len(app_state.drag.guides),
            "NORMAL_MAX_POINTS": NORMAL_MAX_POINTS, "BOOST_MAX_POINTS": BOOST_MAX_POINTS,
            "slider": slider, "width_slider": width_slider, "buttons": buttons,
            "stroke_count": len(strokes), "strokes": app_state.document.strokes, "selected_strokes": set(app_state.selection.selected_strokes), "selected_obj": sel_obj,
            "text_edit_rect": app_state.ui.text_edit_rect_cache,
            "text_font_rect": app_state.ui.text_font_rect_cache,
            "text_size_minus_rect": app_state.ui.text_size_minus_rect_cache,
            "text_size_plus_rect": app_state.ui.text_size_plus_rect_cache,
            "text_on_path_rect": app_state.ui.text_on_path_rect_cache,
            "text_off_path_rect": app_state.ui.text_off_path_rect_cache,
            "text_font_families": FONT_FAMILIES,
            "text_entry_active": app_state.ui.text_entry is not None,
            "text_entry_text": str(app_state.ui.text_entry.get("text", "")) if app_state.ui.text_entry else "",
            "stroke_swatch_rects": stroke_swatch_rects, "fill_swatch_rects": fill_swatch_rects,
            "color_target": app_state.ui.color_target, "picker_h": app_state.ui.picker_h, "picker_s": app_state.ui.picker_s, "picker_v": app_state.ui.picker_v,
            "picker_drag_sv": app_state.ui.picker_drag_sv, "picker_drag_hue": app_state.ui.picker_drag_hue, "picker_drag_alpha": app_state.ui.picker_drag_alpha,
            "sv_rect": app_state.ui.picker_rects["sv"], "hue_rect": app_state.ui.picker_rects["hue"],
            "tab_stroke_rect": app_state.ui.picker_rects["tab_stroke"], "tab_fill_rect": app_state.ui.picker_rects["tab_fill"],
            "nofill_rect": app_state.ui.picker_rects["nofill"], "alpha_rect": app_state.ui.picker_rects["alpha"],
            "fill_type_prev_rect": app_state.ui.fill_type_prev_rect_cache, "fill_type_next_rect": app_state.ui.fill_type_next_rect_cache, "fill_stop_rects": dict(app_state.ui.fill_stop_rects_cache),
            "fill_stop_add_rect": app_state.ui.fill_stop_add_rect_cache, "fill_stop_remove_rect": app_state.ui.fill_stop_remove_rect_cache,
            "fill_stop_pos_rect": app_state.ui.fill_stop_pos_rect_cache, "fill_gradient_stop": app_state.ui.fill_gradient_stop,
            "pattern_type_rect": app_state.ui.pattern_type_rect_cache,
            "pattern_size_minus_rect": app_state.ui.pattern_size_minus_rect_cache,
            "pattern_size_plus_rect": app_state.ui.pattern_size_plus_rect_cache,
            "fill_stop_pos_drag": app_state.ui.fill_stop_pos_drag,
            "selection_submode": app_state.selection.selection_submode,
            "selection_bbox": bb,
            "nodes_mode_prev_rect": app_state.ui.nodes_mode_prev_rect_cache,
            "nodes_mode_next_rect": app_state.ui.nodes_mode_next_rect_cache,
            "elev_front_rect": app_state.ui.elev_front_rect_cache,
            "elev_forward_rect": app_state.ui.elev_forward_rect_cache,
            "elev_backward_rect": app_state.ui.elev_backward_rect_cache,
            "elev_back_rect": app_state.ui.elev_back_rect_cache,
            "bool_union_rect": app_state.ui.bool_union_rect_cache,
            "bool_intersect_rect": app_state.ui.bool_intersect_rect_cache,
            "bool_subtract_rect": app_state.ui.bool_subtract_rect_cache,
            "bool_exclude_rect": app_state.ui.bool_exclude_rect_cache,
            "distribute_h_rect": app_state.ui.distribute_h_rect_cache,
            "distribute_v_rect": app_state.ui.distribute_v_rect_cache,
            "path_close_rect": app_state.ui.path_close_rect_cache,
            "path_reverse_rect": app_state.ui.path_reverse_rect_cache,
            "path_add_rect": app_state.ui.path_add_rect_cache,
            "path_delete_rect": app_state.ui.path_delete_rect_cache,
            "path_smooth_rect": app_state.ui.path_smooth_rect_cache,
            "path_corner_rect": app_state.ui.path_corner_rect_cache,
            "path_expand_rect": app_state.ui.path_expand_rect_cache,
            "obj_opacity_rect": app_state.ui.obj_opacity_rect_cache,

            "shadow_toggle_rect": app_state.ui.shadow_toggle_rect_cache,
            "shadow_blur_minus_rect": app_state.ui.shadow_blur_minus_rect_cache,
            "shadow_blur_plus_rect": app_state.ui.shadow_blur_plus_rect_cache,
            "cap_prev_rect": app_state.ui.cap_prev_rect_cache,
            "cap_next_rect": app_state.ui.cap_next_rect_cache,
            "join_prev_rect": app_state.ui.join_prev_rect_cache,
            "join_next_rect": app_state.ui.join_next_rect_cache,
            "dash_prev_rect": app_state.ui.dash_prev_rect_cache,
            "dash_next_rect": app_state.ui.dash_next_rect_cache,
            "marker_start_rect": app_state.ui.marker_start_rect_cache,
            "marker_end_rect": app_state.ui.marker_end_rect_cache,
            "marker_dropdown": app_state.ui.marker_dropdown,
            "marker_dropdown_rect": app_state.ui.marker_dropdown_rect,
            "marker_dropdown_item_rects": app_state.ui.marker_dropdown_item_rects,
            "width_profile_prev_rect": app_state.ui.width_profile_prev_rect_cache,
            "width_profile_next_rect": app_state.ui.width_profile_next_rect_cache,
            "obj_opacity_drag": app_state.ui.obj_opacity_drag,
            "xform_field_focus": app_state.ui.xform_field_focus,
            "xform_field_buffer": app_state.ui.xform_field_buffer,
            "drag_field_edit": app_state.ui.drag_field_edit,
            "drag_field_last_click": app_state.ui.drag_field_last_click,
            "panel_sections": app_state.ui.panel_sections,
            "panel_section_rects": app_state.ui.panel_section_rects,
            "xform_x_rect": app_state.ui.xform_x_rect_cache,
            "xform_y_rect": app_state.ui.xform_y_rect_cache,
            "xform_w_rect": app_state.ui.xform_w_rect_cache,
            "xform_h_rect": app_state.ui.xform_h_rect_cache,
            "xform_r_rect": app_state.ui.xform_r_rect_cache,
            "xform_xm_rect": app_state.ui.xform_xm_rect_cache,
            "xform_xp_rect": app_state.ui.xform_xp_rect_cache,
            "xform_ym_rect": app_state.ui.xform_ym_rect_cache,
            "xform_yp_rect": app_state.ui.xform_yp_rect_cache,
            "xform_wm_rect": app_state.ui.xform_wm_rect_cache,
            "xform_wp_rect": app_state.ui.xform_wp_rect_cache,
            "xform_hm_rect": app_state.ui.xform_hm_rect_cache,
            "xform_hp_rect": app_state.ui.xform_hp_rect_cache,
            "xform_rm_rect": app_state.ui.xform_rm_rect_cache,
            "xform_rp_rect": app_state.ui.xform_rp_rect_cache,
            "mirror_h_rect": app_state.ui.mirror_h_rect_cache,
            "mirror_v_rect": app_state.ui.mirror_v_rect_cache,
            "align_left_rect": app_state.ui.align_left_rect_cache,
            "align_hcenter_rect": app_state.ui.align_hcenter_rect_cache,
            "align_right_rect": app_state.ui.align_right_rect_cache,
            "align_top_rect": app_state.ui.align_top_rect_cache,
            "align_vmiddle_rect": app_state.ui.align_vmiddle_rect_cache,
            "align_bottom_rect": app_state.ui.align_bottom_rect_cache,
            "trace_algorithm": app_state.tools.trace_algorithm,
            "trace_algo_prev_rect": app_state.ui.trace_algo_prev_rect_cache,
            "trace_algo_next_rect": app_state.ui.trace_algo_next_rect_cache,
            "draw_tool_prev_rect": app_state.ui.draw_tool_prev_rect_cache,
            "draw_tool_next_rect": app_state.ui.draw_tool_next_rect_cache,
            "draw_shape": app_state.tools.draw_shape,
            "draw_shape_rects": app_state.ui.draw_shape_rects_cache,
            "draw_shape_variant": app_state.tools.triangle_variant,
            "rect_variant": app_state.tools.rect_variant,
            "ellipse_variant": app_state.tools.ellipse_variant,
            "line_constrain": app_state.tools.line_constrain,
            "line_arrow": app_state.tools.line_arrow,
            "corner_radius": app_state.tools.corner_radius,
            "ellipse_segments": app_state.tools.ellipse_segments,
            "polygon_sides": app_state.tools.polygon_sides,
            "star_points": app_state.tools.star_points,
            "star_inner_ratio": app_state.tools.star_inner_ratio,
            "shape_menu_key": app_state.ui.shape_menu_key,
            "shape_menu_anchor": app_state.ui.shape_menu_anchor,
            "shape_menu_rect": app_state.ui.shape_menu_rect,
            "shape_menu_item_rects": app_state.ui.shape_menu_item_rects,
            "panel_collapsed": app_state.viewport.panel_collapsed,
            "panel_toggle_rect": app_state.ui.panel_toggle_rect_cache,
            "workspace_rect": pygame.Rect(0, 0, 0, 0),
            "draw_tool": app_state.tools.draw_tool,
            "draw_tool_pen_rect": app_state.ui.draw_tool_pen_rect_cache,
            "draw_tool_eraser_rect": app_state.ui.draw_tool_eraser_rect_cache,
            "draw_tool_bucket_rect": app_state.ui.draw_tool_bucket_rect_cache,
            "draw_tool_cutter_rect": app_state.ui.draw_tool_cutter_rect_cache,
            "bezier_pen": app_state.tools.bezier_pen,
            "bucket_fill_color": app_state.tools.bucket_fill_color,
            "bucket_picker_h": app_state.tools.bucket_picker_h,
            "bucket_picker_s": app_state.tools.bucket_picker_s,
            "bucket_picker_v": app_state.tools.bucket_picker_v,
            "bucket_picker_drag": app_state.ui.bucket_picker_drag,
            "bucket_sv_rect": app_state.ui.bucket_sv_rect_cache,
            "bucket_hue_rect": app_state.ui.bucket_hue_rect_cache,
            "bucket_swatch_rects": app_state.ui.bucket_swatch_rects_cache,
            "snap_toggle_rect": app_state.ui.snap_toggle_rect_cache,
            "selected_curve": app_state.selection.selected_curve,
            "selected_curves": set(app_state.selection.selected_curves),
            "selected_point": app_state.selection.selected_point,
            "redrawing_curve": app_state.drag.redrawing_curve,
            "curve_hide_rect": app_state.ui.curve_hide_rect_cache,
            "curve_redraw_rect": app_state.ui.curve_redraw_rect_cache,
            "curve_cut_rect": app_state.ui.curve_cut_rect_cache,
            "curve_join_rect": app_state.ui.curve_join_rect_cache,
            "curve_cut_mode": app_state.tools.curve_cut_mode,
            "eyedropper_pick": app_state.tools.eyedropper_pick,
            "eyedropper_rect": app_state.ui.eyedropper_rect_cache,
            "cut_gap": app_state.drag.cut_gap,
            "cut_gap_slider": cut_gap_slider,
            "wave_toggle_rect": app_state.ui.wave_toggle_rect_cache,
            "wave_add_rect": app_state.ui.wave_add_rect_cache,
            "displacement_add_rect": app_state.ui.displacement_add_rect_cache,
            "repeat_add_rect": app_state.ui.repeat_add_rect_cache,
            "thickness_add_rect": app_state.ui.thickness_add_rect_cache,
            "wave_remove_rect": app_state.ui.wave_remove_rect_cache,
            "wave_bake_rect": app_state.ui.wave_bake_rect_cache,
            "wave_shape_prev_rect": app_state.ui.wave_shape_prev_rect_cache,
            "wave_shape_next_rect": app_state.ui.wave_shape_next_rect_cache,
            "displacement_profile_rects": app_state.ui.displacement_profile_rects_cache,
            "displacement_affect_rects": app_state.ui.displacement_affect_rects_cache,
            "wave_formula_rect": app_state.ui.wave_formula_rect_cache,
            "wave_formula_focus": app_state.ui.wave_formula_focus,
            "wave_custom_draw": app_state.ui.wave_custom_draw,
            "repeat_pick_mode": app_state.ui.repeat_pick_mode,
            "repeat_pick_target": app_state.ui.repeat_pick_target,
            "wave_custom_box_rect": app_state.ui.wave_custom_box_rect_cache,
            "wave_smooth_rect": app_state.ui.wave_smooth_rect_cache,
            "wave_clear_rect": app_state.ui.wave_clear_rect_cache,
            "wave_done_rect": app_state.ui.wave_done_rect_cache,
            "repeat_pick_curve_rect": app_state.ui.repeat_pick_curve_rect_cache,
            "wave_reverse_rect": app_state.ui.wave_reverse_rect_cache,
            "wave_clamp_rect": app_state.ui.wave_clamp_rect_cache,
            "wave_custom_drag": app_state.ui.wave_custom_drag,
            "wave_active_index": app_state.ui.wave_active_index,
            "wave_row_rects": app_state.ui.wave_row_rects_cache,
            "wave_custom_finished": app_state.ui.wave_custom_finished,
            "panel_scroll": app_state.ui.panel_scroll,
            "export_scale": app_state.ui.export_scale,
            "export_dpi": app_state.ui.export_dpi,
            "export_dialog_open": app_state.ui.export_dialog_open,
            "export_dialog_format": app_state.ui.export_dialog_format,
            "export_dialog_rects": app_state.ui.export_dialog_rects,
            "wave_slider_rects": app_state.ui.wave_slider_rects_cache,
            "strokes": app_state.document.strokes,
            "reference_image": app_state.document.reference_image,
            "reference_error": app_state.document.reference_error,
            "ref_load_rect": app_state.ui.ref_load_rect_cache,
            "ref_vis_rect": app_state.ui.ref_vis_rect_cache,
            "ref_clear_rect": app_state.ui.ref_clear_rect_cache,
            "ref_opacity_rect": app_state.ui.ref_opacity_rect_cache,
        }

        def run_menu_action(key):
            import types
            # Phase 1, Task 2: typed AppState is the source for command inputs.
            doc, sel, tools, drag, ui = (
                app_state.document, app_state.selection, app_state.tools,
                app_state.drag, app_state.ui,
            )
            s = CommandContext(
                _shape_state_counter=doc._shape_state_counter, _symbol_counter=doc._symbol_counter,
                active_artboard=doc.active_artboard, artboards=doc.artboards,
                clipboard_strokes=doc.clipboard_strokes,
                current_points=drag.current_points, curve_cut_mode=tools.curve_cut_mode,
                cut_points=drag.cut_points, cutting=drag.cutting,
                document_path=doc.document_path, drag_last=drag.drag_last,
                draw_tool=tools.draw_tool, drawing=drag.drawing,
                export_dialog_format=ui.export_dialog_format, export_dialog_open=ui.export_dialog_open,
                eyedropper_pick=tools.eyedropper_pick, help_open=ui.help_open,
                panel_collapsed=app_state.viewport.panel_collapsed,
                redrawing_curve=drag.redrawing_curve, running=ui.running,
                selected_curve=sel.selected_curve, selected_curves=sel.selected_curves,
                selected_point=sel.selected_point, selected_strokes=sel.selected_strokes,
                selection_submode=sel.selection_submode, shape_states=doc.shape_states,
                snap_enabled=tools.snap_enabled, symbols=doc.symbols,
                text_entry=ui.text_entry, text_family=tools.text_family, text_size=tools.text_size,
                tool_mode=tools.tool_mode, transform_drag=drag.transform_drag,
                workspace=ui.workspace,
                _bezier_pen_cancel=_bezier_pen_cancel, _bezier_pen_commit_or_cancel=_bezier_pen_commit_or_cancel,
                _capture_shape_state=_capture_shape_state, _copy_stroke=_copy_stroke,
                _delete_shape_state=_delete_shape_state, _insert_shape_state=_insert_shape_state,
                assign_group=assign_group, cfg=cfg, clear_group=clear_group, combined_bbox=combined_bbox,
                copy=copy, do_redo=do_redo, do_undo=do_undo, import_svg=import_svg,
                load_document_with_meta=load_document_with_meta, new_group_id=new_group_id,
                pick_import_svg_path=pick_import_svg_path, pick_open_document_path=pick_open_document_path,
                pick_save_document_path=pick_save_document_path, push_undo=push_undo, relayout=relayout,
                save_document=save_document, state=state, strokes=doc.strokes, translate_stroke=translate_stroke,
            )
            result = _menu_dispatch.run_menu_action(key, s, state_fields=app_state._SYNC_FIELDS)
            # Typed state is authoritative: the menu ctx was seeded from it and
            # menu_dispatch_controller syncs command results into s; mirror once.
            app_state.sync_from_locals(s.__dict__)
            # Auto-sync typed state fields back to frame locals (no callback
            # blacklist needed: only authoritative typed field names are copied).
            import sys as _sys2
            _state_fields = set(app_state._SYNC_FIELDS)
            _fl = _sys2._getframe().f_locals
            _chg = False
            for _k, _v in s.__dict__.items():
                if _k not in _state_fields:
                    continue
                if _fl.get(_k) is not _v:
                    _fl[_k] = _v
                    _chg = True
            if _chg:
                try:
                    import ctypes as _ct
                    _ct.pythonapi.PyFrame_LocalsToFast(_ct.py_object(_sys2._getframe()), _ct.c_int(0))
                except Exception:
                    pass
            return result

        # Event loop (extracted). process_event_frame() mirrors changed ctx state
        # into AppState, so no extra pre-event locals->typed roundtrip is needed.
        _frame.process_event_frame()
        # Render frame via the frame helper, which performs render-ctx sync back
        # to frame locals AND mirrors the result into AppState (no separate
        # end-of-frame locals->typed bridge call).
        _frame.render_frame_frame()
