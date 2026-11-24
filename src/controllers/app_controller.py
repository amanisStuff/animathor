"""Controller: application state, event handling and the main loop."""

import math
import copy

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
        # Phase 1 (semantic split plan): typed viewport state is the source of
        # truth for this layout group; cfg module attrs remain live mirrors for
        # legacy readers until the full typed-state migration completes.
        app_state.viewport.width = cfg.WIDTH
        app_state.viewport.height = cfg.HEIGHT
        app_state.viewport.canvas_x = cfg.CANVAS_X
        app_state.viewport.canvas_w = cfg.CANVAS_W
        app_state.viewport.panel_x = cfg.PANEL_X
        app_state.viewport.panel_collapsed = panel_collapsed

    strokes = []
    undo_stack = []
    redo_stack = []
    max_undo = 100

    def _sync_history_locals():
        """Mirror authoritative typed history state into legacy frame locals."""
        nonlocal undo_stack, redo_stack, strokes, max_undo
        undo_stack = app_state.document.undo_stack
        redo_stack = app_state.document.redo_stack
        strokes = app_state.document.strokes
        max_undo = app_state.document.max_undo

    def push_undo():
        _sync_history_locals()
        _history.push_undo(app_state.document.undo_stack, app_state.document.redo_stack, app_state.document.strokes, app_state.document.max_undo)

    def do_undo():
        _sync_history_locals()
        return _history.do_undo(app_state.document.undo_stack, app_state.document.redo_stack, app_state.document.strokes)

    def do_redo():
        _sync_history_locals()
        return _history.do_redo(app_state.document.undo_stack, app_state.document.redo_stack, app_state.document.strokes)

    current_points = []
    drawing = False
    tool_mode = "draw"
    selected_strokes = set()
    selected_point = None
    selected_curve = None  # (stroke_idx, comp_idx) in curve edit mode
    redrawing_curve = None  # {"stroke_idx", "comp_idx", "points", "started", "fixed_start", "fixed_end"}
    drag_last = None
    from controllers.drag import DragManager
    from controllers.app_state import AppState
    drag_manager = DragManager()  # semantic drag session manager (incremental migration)
    app_state = AppState()  # typed state contract (incremental migration target)
    app_state.drag.drag_manager = drag_manager
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
    _shape_state_counter = 0
    _symbol_counter = 0
    active_artboard = -1
    artboards = []
    bezier_pen = None
    bucket_fill_color = (0.45, 0.72, 1.0)
    bucket_picker_h = 0.0
    bucket_picker_s = 0.0
    bucket_picker_v = 0.1
    clipboard_strokes = []
    current_points = []
    curve_cut_mode = False
    cut_points = []
    cutting = False
    document_path = None
    drag_last = None
    draw_tool = "pen"
    drawing = False
    export_dialog_format = "png"
    export_dialog_open = False
    eyedropper_pick = False
    help_open = False
    panel_collapsed = False
    redrawing_curve = None
    running = True
    selected_curve = None
    selected_curves = set()
    selected_point = None
    selected_strokes = set()
    selection_submode = "transform"
    shape_states = {}
    snap_enabled = True
    strokes = []
    symbols = {}
    text_entry = None
    text_family = "Sans"
    text_size = 36.0
    tool_mode = "draw"
    transform_drag = None
    workspace = "draw"
    xform_field_buffer = ""
    xform_field_focus = None

    # UI cache / state locals injected by _frame.init_ui_caches() (real locals required).
    color_target = "stroke"
    picker_h = None
    picker_s = None
    picker_v = None
    picker_drag_sv = False
    picker_drag_hue = False
    picker_drag_alpha = False
    ref_opacity_drag = False
    picker_rects = {}
    fill_type_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    fill_type_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    fill_stop_rects_cache = {}
    fill_stop_add_rect_cache = pygame.Rect(0, 0, 0, 0)
    fill_stop_remove_rect_cache = pygame.Rect(0, 0, 0, 0)
    fill_stop_pos_rect_cache = pygame.Rect(0, 0, 0, 0)
    pattern_type_rect_cache = pygame.Rect(0, 0, 0, 0)
    pattern_size_minus_rect_cache = pygame.Rect(0, 0, 0, 0)
    pattern_size_plus_rect_cache = pygame.Rect(0, 0, 0, 0)
    fill_gradient_stop = 0
    fill_stop_pos_drag = False
    trace_algo_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    trace_algo_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    draw_tool_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    draw_tool_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    draw_shape_rects_cache = {}
    panel_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    shape_menu_key = None
    shape_menu_anchor = None
    shape_menu_rect = None
    shape_menu_item_rects = {}
    draw_tool_pen_rect_cache = pygame.Rect(0, 0, 0, 0)
    draw_tool_eraser_rect_cache = pygame.Rect(0, 0, 0, 0)
    draw_tool_bucket_rect_cache = pygame.Rect(0, 0, 0, 0)
    draw_tool_cutter_rect_cache = pygame.Rect(0, 0, 0, 0)
    snap_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    nodes_mode_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    nodes_mode_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_front_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_forward_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_backward_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_back_rect_cache = pygame.Rect(0, 0, 0, 0)
    bool_union_rect_cache = pygame.Rect(0, 0, 0, 0)
    bool_intersect_rect_cache = pygame.Rect(0, 0, 0, 0)
    bool_subtract_rect_cache = pygame.Rect(0, 0, 0, 0)
    bool_exclude_rect_cache = pygame.Rect(0, 0, 0, 0)
    distribute_h_rect_cache = pygame.Rect(0, 0, 0, 0)
    distribute_v_rect_cache = pygame.Rect(0, 0, 0, 0)
    export_dialog_rects = {}
    path_close_rect_cache = pygame.Rect(0, 0, 0, 0)
    path_reverse_rect_cache = pygame.Rect(0, 0, 0, 0)
    path_add_rect_cache = pygame.Rect(0, 0, 0, 0)
    path_delete_rect_cache = pygame.Rect(0, 0, 0, 0)
    path_smooth_rect_cache = pygame.Rect(0, 0, 0, 0)
    path_corner_rect_cache = pygame.Rect(0, 0, 0, 0)
    path_expand_rect_cache = pygame.Rect(0, 0, 0, 0)
    obj_opacity_rect_cache = pygame.Rect(0, 0, 0, 0)
    shadow_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    shadow_blur_minus_rect_cache = pygame.Rect(0, 0, 0, 0)
    shadow_blur_plus_rect_cache = pygame.Rect(0, 0, 0, 0)
    cap_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    cap_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    join_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    join_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    dash_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    dash_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    marker_start_rect_cache = pygame.Rect(0, 0, 0, 0)
    marker_end_rect_cache = pygame.Rect(0, 0, 0, 0)
    marker_dropdown = None
    marker_dropdown_rect = None
    marker_dropdown_item_rects = {}
    obj_opacity_drag = False
    xform_x_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_y_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_w_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_h_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_r_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_xm_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_xp_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_ym_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_yp_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_wm_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_wp_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_hm_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_hp_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_rm_rect_cache = pygame.Rect(0, 0, 0, 0)
    xform_rp_rect_cache = pygame.Rect(0, 0, 0, 0)
    text_edit_rect_cache = pygame.Rect(0, 0, 0, 0)
    text_font_rect_cache = pygame.Rect(0, 0, 0, 0)
    text_size_minus_rect_cache = pygame.Rect(0, 0, 0, 0)
    text_size_plus_rect_cache = pygame.Rect(0, 0, 0, 0)
    text_on_path_rect_cache = pygame.Rect(0, 0, 0, 0)
    text_off_path_rect_cache = pygame.Rect(0, 0, 0, 0)
    mirror_h_rect_cache = pygame.Rect(0, 0, 0, 0)
    mirror_v_rect_cache = pygame.Rect(0, 0, 0, 0)
    align_left_rect_cache = pygame.Rect(0, 0, 0, 0)
    align_hcenter_rect_cache = pygame.Rect(0, 0, 0, 0)
    align_right_rect_cache = pygame.Rect(0, 0, 0, 0)
    align_top_rect_cache = pygame.Rect(0, 0, 0, 0)
    align_vmiddle_rect_cache = pygame.Rect(0, 0, 0, 0)
    align_bottom_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_hide_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_redraw_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_cut_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_join_rect_cache = pygame.Rect(0, 0, 0, 0)
    eyedropper_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_add_rect_cache = pygame.Rect(0, 0, 0, 0)
    displacement_add_rect_cache = pygame.Rect(0, 0, 0, 0)
    repeat_add_rect_cache = pygame.Rect(0, 0, 0, 0)
    thickness_add_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_remove_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_bake_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_shape_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_shape_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    displacement_profile_rects_cache = {}
    width_profile_prev_rect_cache = pygame.Rect(0, 0, 0, 0)
    width_profile_next_rect_cache = pygame.Rect(0, 0, 0, 0)
    displacement_affect_rects_cache = {}
    wave_formula_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_formula_focus = False
    wave_custom_draw = False
    repeat_pick_mode = False
    repeat_pick_target = None
    wave_custom_box_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_smooth_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_clear_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_done_rect_cache = pygame.Rect(0, 0, 0, 0)
    repeat_pick_curve_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_reverse_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_clamp_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_custom_drag = None
    wave_active_index = 0
    wave_row_rects_cache = {}
    wave_custom_finished = False
    wave_slider_rects_cache = {}
    wave_slider_drag = None
    panel_scroll = 0
    export_scale = 1.0
    export_dpi = 300
    ref_load_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_vis_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_clear_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_opacity_rect_cache = pygame.Rect(0, 0, 0, 0)
    bucket_picker_drag = None
    bucket_sv_rect_cache = pygame.Rect(0, 0, 0, 0)
    bucket_hue_rect_cache = pygame.Rect(0, 0, 0, 0)
    bucket_swatch_rects_cache = {}
    reference_image = None
    reference_error = None
    ref_drag = None
    space_panning = False
    pan_drag = None
    hover_snap = None
    hover_snap_kind = "connect"
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

    def bucket_pick(rect, pos, kind):
        # Typed ToolState is passed directly; no SimpleNamespace ctx bag.
        _bucket.pick(app_state.tools, rect, pos, kind, state, clamp, hsv_to_rgb)

    def set_bucket_color(col):
        _bucket.set_color(app_state.tools, col, state, rgb_to_hsv)

    def commit_text_entry():
        # Typed substates are passed directly; no SimpleNamespace ctx bag.
        nonlocal text_entry, selected_strokes, selected_point, selected_curve, selected_curves
        r = _text_entry.commit(
            app_state.selection, app_state.document, app_state.ui,
            push_undo, hsv_to_rgb, new_text_stroke,
        )
        # Mirror typed results into legacy locals for same-frame readers.
        text_entry = app_state.ui.text_entry
        selected_strokes = app_state.selection.selected_strokes
        selected_point = app_state.selection.selected_point
        selected_curve = app_state.selection.selected_curve
        selected_curves = app_state.selection.selected_curves
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

    def _bp_ctx():
        import types as _types
        ctx = _types.SimpleNamespace()
        ctx.bezier_pen = app_state.tools.bezier_pen
        ctx.strokes = app_state.document.strokes
        ctx.selected_strokes = app_state.selection.selected_strokes
        ctx.selected_point = app_state.selection.selected_point
    # --- Bezier pen tool (click-to-place anchors, drag handles) ---
        ctx.selected_curve = app_state.selection.selected_curve
        ctx.selected_curves = app_state.selection.selected_curves
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
        app_state.tools.bezier_pen = bezier_pen
        app_state.document.strokes = strokes
        app_state.selection.selected_strokes = selected_strokes
        app_state.selection.selected_point = selected_point
        app_state.selection.selected_curve = selected_curve
        app_state.selection.selected_curves = selected_curves

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
    # Seed AppState from initialized locals (AppState becomes primary for its slice).
    try:
        app_state.sync_from_locals(locals())
    except Exception:
        pass
    while running:
        # Single frame-start capture point: main()'s direct local mutations
        # (selection sanitization, pivot reset, hover snap) are mirrored into
        # typed AppState, which is authoritative when frame helpers dispatch.
        try:
            app_state.sync_from_locals(locals())
        except Exception:
            pass
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
            # Phase 1, Task 2: typed AppState is the source for command inputs.
            doc, sel, tools, drag, ui = (
                app_state.document, app_state.selection, app_state.tools,
                app_state.drag, app_state.ui,
            )
            s = types.SimpleNamespace(
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
