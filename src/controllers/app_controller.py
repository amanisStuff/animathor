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
from models.geometry import bbox_handle_anchor_local, bbox_handle_local_positions, gradient_edit_handles, hit_test_gradient_handle, gradient_edit_bbox, get_fill_gradient, is_fill_gradient, normalize_gradient, clamp, default_linear_gradient, default_radial_gradient, default_shaped_gradient, get_stroke_obb
from models.strokes import scale_stroke_local, rotate_stroke_around, skew_stroke_local


def _stroke_kind_label(stroke):
    """Short human-readable kind for a stroke, used in the layer list."""
    if not isinstance(stroke, dict):
        return "Path"
    if stroke.get("is_group"):
        return "Group"
    if stroke.get("shape_kind"):
        return str(stroke["shape_kind"]).capitalize()
    if stroke.get("text"):
        return "Text"
    if stroke.get("fill_color") is not None and stroke.get("stroke_width", 3.0) == 0:
        return "Shape"
    return "Path"


def _capture_shape_state(strokes, sel, shape_states, counter):
    """Save the selected strokes as a new shape state in the library.

    Geometry is normalized to the selection bbox top-left so instances can be
    placed by translation alone. Returns ``(state_id, next_counter)``.
    """
    counter = int(counter) + 1
    sid = f"shape{counter}"
    def_strokes = []
    idxs = [i for i in sel if 0 <= i < len(strokes) and isinstance(strokes[i], dict)]
    for i in idxs:
        st = copy.deepcopy(strokes[i])
        for k in ("symbol_id", "symbol_is_master", "symbol_instance_id",
                  "shape_state_id", "shape_state_is_master", "shape_state_instance_id"):
            st.pop(k, None)
        def_strokes.append(st)
    bb = combined_bbox(strokes, idxs) if idxs else None
    ox, oy = (float(bb[0]), float(bb[1])) if bb else (0.0, 0.0)
    norm_def = []
    for st in def_strokes:
        norm_def.append(translate_stroke(st, -ox, -oy))
    shape_states[sid] = {"name": f"Shape State {counter}", "strokes": norm_def, "origin": [ox, oy]}
    for i in idxs:
        strokes[i]["shape_state_id"] = sid
        strokes[i]["shape_state_is_master"] = True
        strokes[i]["shape_state_instance_id"] = f"{sid}:master"
    return sid, counter


def _insert_shape_state(strokes, shape_states, counter, sel):
    """Insert a library shape state as new asset strokes. Returns ``(indices, counter)``."""
    sid = None
    for i in sorted(sel):
        if 0 <= i < len(strokes) and isinstance(strokes[i], dict) and strokes[i].get("shape_state_id"):
            sid = strokes[i].get("shape_state_id")
            break
    if sid is None and shape_states:
        sid = list(shape_states.keys())[-1]
    sdef = shape_states.get(sid) if sid else None
    def_strokes = (sdef or {}).get("strokes") if isinstance(sdef, dict) else None
    indices = []
    if not (sid and isinstance(def_strokes, list) and def_strokes):
        return indices, counter
    counter = int(counter) + 1
    inst_id = f"{sid}:i{counter}"
    base = len(strokes)
    offx = offy = 24.0
    idxs = [i for i in sel if 0 <= i < len(strokes)]
    if idxs:
        bb = combined_bbox(strokes, idxs)
        if bb:
            offx = (bb[2] - bb[0]) * 0.2 + 24.0
            offy = (bb[3] - bb[1]) * 0.2 + 24.0
    origin = sdef.get("origin") if isinstance(sdef, dict) else None
    try:
        ox = float(origin[0]) if isinstance(origin, (list, tuple)) and len(origin) > 0 else 0.0
        oy = float(origin[1]) if isinstance(origin, (list, tuple)) and len(origin) > 1 else 0.0
    except Exception:
        ox = oy = 0.0
    for st in copy.deepcopy(def_strokes):
        if not isinstance(st, dict):
            continue
        nst = translate_stroke(st, ox + offx, oy + offy)
        nst["shape_state_id"] = sid
        nst["shape_state_is_master"] = False
        nst["shape_state_instance_id"] = inst_id
        strokes.append(nst)
        indices.append(base)
        base += 1
    return indices, counter


def _delete_shape_state(shape_states, sid, strokes):
    """Remove a library state and detach strokes that reference it."""
    if sid and sid in shape_states:
        del shape_states[sid]
    touched = False
    for i in range(len(strokes)):
        st = strokes[i]
        if isinstance(st, dict) and st.get("shape_state_id") == sid:
            for k in ("shape_state_id", "shape_state_is_master", "shape_state_instance_id"):
                st.pop(k, None)
            touched = True
    return touched


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
        # snapshot strokes for undo (action-based)
        try:
            undo_stack.append(copy.deepcopy(strokes))
        except Exception:
            undo_stack.append(list(strokes))
        if len(undo_stack) > MAX_UNDO:
            del undo_stack[0:len(undo_stack) - MAX_UNDO]
        redo_stack.clear()

    def do_undo():
        if undo_stack:
            try:
                redo_stack.append(copy.deepcopy(strokes))
            except Exception:
                redo_stack.append(list(strokes))
            restored = undo_stack.pop()
            strokes.clear()
            strokes.extend(restored)
            return True
        return False

    def do_redo():
        if redo_stack:
            try:
                undo_stack.append(copy.deepcopy(strokes))
            except Exception:
                undo_stack.append(list(strokes))
            restored = redo_stack.pop()
            strokes.clear()
            strokes.extend(restored)
            return True
        return False

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

    color_target = "stroke"  # "stroke" or "fill"
    picker_h, picker_s, picker_v = 0.0, 0.0, 0.1
    picker_drag_sv = False
    picker_drag_hue = False
    picker_drag_alpha = False
    ref_opacity_drag = False
    picker_rects = {"sv": pygame.Rect(0,0,0,0), "hue": pygame.Rect(0,0,0,0),
                    "tab_stroke": pygame.Rect(0,0,0,0), "tab_fill": pygame.Rect(0,0,0,0),
                    "nofill": pygame.Rect(0,0,0,0), "alpha": pygame.Rect(0,0,0,0)}
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
    draw_shape_rects_cache = {k: pygame.Rect(0, 0, 0, 0)
                              for k, _ in list(DRAW_SHAPES) + list(BOTTOM_TOOLS)}
    panel_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    shape_menu_key = None  # shape whose right-click options menu is open
    shape_menu_anchor = pygame.Rect(0, 0, 0, 0)
    shape_menu_rect = pygame.Rect(0, 0, 0, 0)
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
    marker_dropdown = None  # "start" | "end" | None
    marker_dropdown_rect = pygame.Rect(0, 0, 0, 0)
    marker_dropdown_item_rects = {}
    obj_opacity_drag = False
    # Numeric transform precision inputs (focus + edit buffer).
    xform_field_focus = None  # one of {"x","y","w","h","r"} or None
    xform_field_buffer = ""
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
    # (Layer panel UI removed.)
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
    repeat_pick_target = None  # (stroke_i, comp_i, style_i) when picking a curve as repeat pattern
    wave_custom_box_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_smooth_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_clear_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_done_rect_cache = pygame.Rect(0, 0, 0, 0)
    repeat_pick_curve_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_reverse_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_clamp_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_custom_drag = None
    wave_active_index = 0
    wave_row_rects_cache = []
    wave_custom_finished = False
    wave_slider_rects_cache = {}
    wave_slider_drag = None
    panel_scroll = 0
    # Export dialog defaults (used by File > Export dialog).
    export_scale = 1.0
    export_dpi = 300
    export_dialog_open = False
    export_dialog_format = "png"
    ref_load_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_vis_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_clear_rect_cache = pygame.Rect(0, 0, 0, 0)
    ref_opacity_rect_cache = pygame.Rect(0, 0, 0, 0)
    # Fill (bucket) tool color: chosen in the panel picker or its popup swatches.
    bucket_fill_color = (0.45, 0.72, 1.0)
    bucket_picker_h, bucket_picker_s, bucket_picker_v = rgb_to_hsv(*bucket_fill_color)
    bucket_picker_drag = None  # "sv" | "hue" | None
    bucket_sv_rect_cache = pygame.Rect(0, 0, 0, 0)
    bucket_hue_rect_cache = pygame.Rect(0, 0, 0, 0)
    bucket_swatch_rects_cache = [pygame.Rect(0, 0, 0, 0) for _ in BUCKET_SWATCHES]
    reference_image = None  # {"surface": cairo.ImageSurface, "w","h","x","y","opacity","visible","path"}
    reference_error = None  # message shown in the panel when a load fails
    ref_drag = None
    space_panning = False
    pan_drag = None  # {"start_mouse":(x,y),"start_pan":(x,y)}
    document_path = None
    clipboard_strokes = []
    artboards = []  # [{"name","x","y","w","h"}, ...]
    active_artboard = -1
    symbols = {}  # {symbol_id: {"name": str, "strokes": [stroke_dict,...]}}
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
        # A radius of 0 makes the interaction helpers skip snapping entirely.
        return SNAP_RADIUS if snap_enabled else 0

    def _alignment_guides_for_point(pt, other_strokes, sr):
        """Return transient alignment guides when point aligns to other object bbox edges/centers."""
        if sr <= 0 or not other_strokes:
            return []
        px, py = pt
        target_bbs = [stroke_bbox(s) for s in other_strokes]
        target_bbs = [b for b in target_bbs if b]
        best_x = None  # (dist, pos, target_bb)
        best_y = None
        for (tx0, ty0, tx1, ty1) in target_bbs:
            tcx = (tx0 + tx1) * 0.5
            tcy = (ty0 + ty1) * 0.5
            for tval in (tx0, tcx, tx1):
                d = abs(tval - px)
                if d <= sr and (best_x is None or d < best_x[0]):
                    best_x = (d, tval, (tx0, ty0, tx1, ty1))
            for tval in (ty0, tcy, ty1):
                d = abs(tval - py)
                if d <= sr and (best_y is None or d < best_y[0]):
                    best_y = (d, tval, (tx0, ty0, tx1, ty1))
        guides = []
        if best_x is not None:
            tbb = best_x[2]
            guides.append({"axis": "x", "pos": best_x[1], "y0": min(py, tbb[1]), "y1": max(py, tbb[3])})
        if best_y is not None:
            tbb = best_y[2]
            guides.append({"axis": "y", "pos": best_y[1], "x0": min(px, tbb[0]), "x1": max(px, tbb[2])})
        return guides

    def _snap_move_delta(sel_indices, dx, dy):
        """Snap a translation (dx,dy) to smart object alignments, with point-snap fallback.
        Returns (dx, dy, guides) where guides are transient alignment lines for rendering."""
        sr = snap_radius()
        if sr <= 0 or not sel_indices or (dx == 0 and dy == 0):
            return dx, dy, []
        sel_set = set(sel_indices)
        other = [(i, s) for i, s in enumerate(strokes) if i not in sel_set]
        if not other:
            return dx, dy, []
        xs, ys = [], []
        for si in sel_set:
            if 0 <= si < len(strokes):
                bb = stroke_bbox(strokes[si])
                if bb:
                    x1, y1, x2, y2 = bb
                    xs.extend([x1, x2]); ys.extend([y1, y2])
        if not xs:
            return dx, dy, []
        sx0, sx1 = min(xs), max(xs)
        sy0, sy1 = min(ys), max(ys)
        scx, scy = (sx0 + sx1) * 0.5, (sy0 + sy1) * 0.5
        mx0, mx1, mcx = sx0 + dx, sx1 + dx, scx + dx
        my0, my1, mcy = sy0 + dy, sy1 + dy, scy + dy

        # Smart axis-aligned snaps to other objects' bounding boxes.
        target_bbs = []
        for _, st in other:
            tbb = stroke_bbox(st)
            if tbb:
                target_bbs.append(tbb)
        best_x = None  # (abs_dist, adj, pos, target_bb)
        best_y = None
        for (tx0, ty0, tx1, ty1) in target_bbs:
            tcx = (tx0 + tx1) * 0.5
            tcy = (ty0 + ty1) * 0.5
            for sval in (mx0, mcx, mx1):
                for tval in (tx0, tcx, tx1):
                    d = abs(tval - sval)
                    if d <= sr and (best_x is None or d < best_x[0]):
                        best_x = (d, tval - sval, tval, (tx0, ty0, tx1, ty1))
            for sval in (my0, mcy, my1):
                for tval in (ty0, tcy, ty1):
                    d = abs(tval - sval)
                    if d <= sr and (best_y is None or d < best_y[0]):
                        best_y = (d, tval - sval, tval, (tx0, ty0, tx1, ty1))

        guides = []
        ndx, ndy = dx, dy
        if best_x is not None:
            ndx += best_x[1]
            tbb = best_x[3]
            gy0 = min(my0, tbb[1])
            gy1 = max(my1, tbb[3])
            guides.append({"axis": "x", "pos": best_x[2], "y0": gy0, "y1": gy1})
        if best_y is not None:
            ndy += best_y[1]
            tbb = best_y[3]
            gx0 = min(mx0 + (best_x[1] if best_x else 0.0), tbb[0])
            gx1 = max(mx1 + (best_x[1] if best_x else 0.0), tbb[2])
            guides.append({"axis": "y", "pos": best_y[2], "x0": gx0, "x1": gx1})
        if best_x is not None or best_y is not None:
            return ndx, ndy, guides

        # Fallback: legacy point-snap to nearest geometry on other strokes.
        anchors = [
            (sx0, sy0), (scx, sy0), (sx1, sy0),
            (sx0, scy), (scx, scy), (sx1, scy),
            (sx0, sy1), (scx, sy1), (sx1, sy1),
        ]
        other_strokes = [s for _, s in other]
        best_adj = None
        best_d = sr + 1.0
        for ax, ay in anchors:
            tx, ty = ax + dx, ay + dy
            sp = nearest_snap_point((tx, ty), other_strokes, sr)
            if sp is not None:
                d = math.hypot(sp[0] - tx, sp[1] - ty)
                if d < best_d:
                    best_d = d
                    best_adj = (sp[0] - tx, sp[1] - ty)
        if best_adj is not None:
            return dx + best_adj[0], dy + best_adj[1], []
        return dx, dy, []

    def bucket_pick(rect, pos, kind):
        """Set the bucket color from an SV square or hue bar position."""
        nonlocal bucket_fill_color, bucket_picker_h, bucket_picker_s, bucket_picker_v
        if rect.w <= 0 or rect.h <= 0:
            return
        if kind == "sv":
            bucket_picker_s = clamp((pos[0] - rect.x) / max(1, rect.w - 1), 0.0, 1.0)
            bucket_picker_v = clamp(1.0 - (pos[1] - rect.y) / max(1, rect.h - 1), 0.0, 1.0)
        else:
            bucket_picker_h = clamp((pos[0] - rect.x) / max(1, rect.w - 1), 0.0, 1.0) * 360.0
        bucket_fill_color = hsv_to_rgb(bucket_picker_h, bucket_picker_s, bucket_picker_v)
        # Keep this frame's state in sync so the panel draws the same values.
        state["bucket_fill_color"] = bucket_fill_color
        state["bucket_picker_h"] = bucket_picker_h
        state["bucket_picker_s"] = bucket_picker_s
        state["bucket_picker_v"] = bucket_picker_v
        state["bucket_picker_drag"] = kind

    def set_bucket_color(col):
        """Set the bucket color from a preset swatch and sync the picker."""
        nonlocal bucket_fill_color, bucket_picker_h, bucket_picker_s, bucket_picker_v
        bucket_fill_color = tuple(col)
        bucket_picker_h, bucket_picker_s, bucket_picker_v = rgb_to_hsv(*bucket_fill_color)
        state["bucket_fill_color"] = bucket_fill_color
        state["bucket_picker_h"] = bucket_picker_h
        state["bucket_picker_s"] = bucket_picker_s
        state["bucket_picker_v"] = bucket_picker_v

    def commit_text_entry():
        """Commit the active text buffer as an editable outline stroke."""
        nonlocal text_entry, selected_strokes, selected_point, selected_curve, selected_curves
        if text_entry is None:
            return False
        content = str(text_entry.get("text", ""))
        edit_index = text_entry.get("edit_index")
        if content.strip():
            push_undo()
            col = hsv_to_rgb(picker_h, picker_s, picker_v)
            color = (col[0], col[1], col[2], 1.0)
            old_tp = None
            if edit_index is not None and 0 <= edit_index < len(strokes) and isinstance(strokes[edit_index], dict):
                old_tp = strokes[edit_index].get("text_path")
            if isinstance(old_tp, dict) and old_tp.get("segs"):
                st = new_text_stroke(content, text_entry["x"], text_entry["y"],
                                     text_entry["family"], text_entry["size"], color=color,
                                     path_segs=old_tp.get("segs"), path_offset=old_tp.get("offset", 0.0))
            else:
                st = new_text_stroke(content, text_entry["x"], text_entry["y"],
                                     text_entry["family"], text_entry["size"], color=color)
            if edit_index is not None and 0 <= edit_index < len(strokes):
                for _k in ("opacity", "blend_mode", "shadow", "hidden", "locked"):
                    if _k in strokes[edit_index]:
                        st[_k] = strokes[edit_index][_k]
                strokes[edit_index] = st
                selected_strokes = {edit_index}
            else:
                strokes.append(st)
                selected_strokes = {len(strokes) - 1}
            selected_point = None; selected_curve = None; selected_curves.clear()
        text_entry = None
        return True

    def _xform_sel_bbox():
        sel = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
        if not sel:
            return sel, None
        return sel, combined_bbox(strokes, sel)

    def _xform_current_value(field):
        sel, bb = _xform_sel_bbox()
        if not bb:
            return None
        x0, y0, x1, y1 = bb
        if field == "x":
            return float(x0)
        if field == "y":
            return float(y0)
        if field == "w":
            return max(0.0, float(x1 - x0))
        if field == "h":
            return max(0.0, float(y1 - y0))
        if field == "r":
            return 0.0
        return None

    def _apply_xform_field(field, target, relative=False):
        """Apply numeric transform to selected strokes. Returns True on change."""
        nonlocal strokes
        sel, bb = _xform_sel_bbox()
        if not sel or not bb:
            return False
        x0, y0, x1, y1 = bb
        bw = max(0.0, float(x1 - x0))
        bh = max(0.0, float(y1 - y0))
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        try:
            val = float(target)
        except (TypeError, ValueError):
            return False
        if field == "x":
            dx = (val if relative else (val - x0))
            if abs(dx) < 1e-9:
                return False
            push_undo()
            for si in sel:
                strokes[si] = translate_stroke(strokes[si], dx, 0.0)
            return True
        if field == "y":
            dy = (val if relative else (val - y0))
            if abs(dy) < 1e-9:
                return False
            push_undo()
            for si in sel:
                strokes[si] = translate_stroke(strokes[si], 0.0, dy)
            return True
        if field == "w":
            if bw < 1e-9:
                return False
            new_w = (bw + val) if relative else val
            if new_w <= 0.0:
                return False
            sx = max(0.01, new_w / bw)
            if abs(sx - 1.0) < 1e-9:
                return False
            push_undo()
            for si in sel:
                strokes[si] = transform_stroke(strokes[si], cx, cy, 0.0, sx, 1.0)
            return True
        if field == "h":
            if bh < 1e-9:
                return False
            new_h = (bh + val) if relative else val
            if new_h <= 0.0:
                return False
            sy = max(0.01, new_h / bh)
            if abs(sy - 1.0) < 1e-9:
                return False
            push_undo()
            for si in sel:
                strokes[si] = transform_stroke(strokes[si], cx, cy, 0.0, 1.0, sy)
            return True
        if field == "r":
            delta_deg = val
            if abs(delta_deg) < 1e-9:
                return False
            push_undo()
            ang = math.radians(delta_deg)
            for si in sel:
                strokes[si] = rotate_stroke_around(strokes[si], cx, cy, ang)
            return True
        return False

    def _commit_xform_field():
        nonlocal xform_field_focus, xform_field_buffer
        field = xform_field_focus
        if field is None:
            return False
        buf = str(xform_field_buffer).strip()
        xform_field_focus = None
        xform_field_buffer = ""
        state["xform_field_focus"] = None
        state["xform_field_buffer"] = ""
        if buf == "" or buf in ("-", ".", "-."):
            return False
        try:
            val = float(buf)
        except ValueError:
            return False
        return _apply_xform_field(field, val, relative=False)

    def _cancel_xform_field():
        nonlocal xform_field_focus, xform_field_buffer
        xform_field_focus = None
        xform_field_buffer = ""
        state["xform_field_focus"] = None
        state["xform_field_buffer"] = ""

    # --- Bezier pen tool (click-to-place anchors, drag handles) ---
    _bezier_last_click = {"time": 0, "pos": (0.0, 0.0)}

    def _bezier_pen_cancel():
        nonlocal bezier_pen
        bezier_pen = None

    def _bezier_pen_finish(close_path=False):
        """Finalize active Bezier pen path into a stroke. Returns True if created."""
        nonlocal bezier_pen, strokes, selected_strokes, selected_point, selected_curve, selected_curves
        bp = bezier_pen
        bezier_pen = None
        if not bp:
            return False
        anchors = list(bp.get("anchors") or [])
        if len(anchors) < 2:
            return False
        segs = []
        n = len(anchors)
        last = n if close_path and n >= 3 else n - 1
        for i in range(last):
            a = anchors[i]
            b = anchors[(i + 1) % n]
            p0 = tuple(a["pt"]); p3 = tuple(b["pt"])
            c1 = tuple(a.get("h_out") or a["pt"])
            c2 = tuple(b.get("h_in") or b["pt"])
            segs.append((p0, c1, c2, p3))
        if not segs:
            return False
        push_undo()
        algo_name = "pen"
        st = new_stroke(segs, algorithm=algo_name)
        st["components"] = [{
            "raw_points": [tuple(a["pt"]) for a in anchors],
            "draw_max_points": len(anchors),
            "algorithm": algo_name,
            "segs": list(segs),
        }]
        if close_path and n >= 3:
            st = _close_path_if_needed(st)
        strokes.append(st)
        strokes = merge_connected_strokes(strokes)
        selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
        return True

    def _bezier_pen_add_anchor(pos):
        """Add a new anchor at pos and start dragging its handles."""
        nonlocal bezier_pen
        pt = tuple(pos)
        if bezier_pen is None:
            bezier_pen = {"anchors": [], "dragging": False, "mouse_down": True,
                          "down_pos": pt, "preview_pt": pt, "dragging_first": False}
        bezier_pen.setdefault("anchors", [])
        bezier_pen["anchors"].append({"pt": pt, "h_in": pt, "h_out": pt, "smooth": False})
        bezier_pen["dragging"] = True
        bezier_pen["mouse_down"] = True
        bezier_pen["down_pos"] = pt
        bezier_pen["preview_pt"] = pt
        bezier_pen["dragging_first"] = False

    def _bezier_pen_update_drag(pos):
        """Update handles while dragging: last anchor's h_out, or first anchor's h_in for close."""
        nonlocal bezier_pen
        if not bezier_pen or not bezier_pen.get("anchors"):
            return
        anchors = bezier_pen["anchors"]
        if bezier_pen.get("dragging_first"):
            a = anchors[0]
            pt = a["pt"]
            # Dragging on first point when closing: set h_in, mirror to h_out
            if math.hypot(pos[0] - pt[0], pos[1] - pt[1]) > 2.0:
                h_in = tuple(pos)
                h_out = (2.0 * pt[0] - h_in[0], 2.0 * pt[1] - h_in[1])
                a["h_in"] = h_in
                a["h_out"] = h_out
                a["smooth"] = True
            else:
                a["h_in"] = pt
                a["h_out"] = pt
                a["smooth"] = False
        else:
            a = anchors[-1]
            pt = a["pt"]
            if math.hypot(pos[0] - pt[0], pos[1] - pt[1]) > 2.0:
                h_out = tuple(pos)
                h_in = (2.0 * pt[0] - h_out[0], 2.0 * pt[1] - h_out[1])
                a["h_out"] = h_out
                a["h_in"] = h_in
                a["smooth"] = True
            else:
                a["h_out"] = pt
                a["h_in"] = pt
                a["smooth"] = False
        bezier_pen["preview_pt"] = tuple(pos)

    def _bezier_pen_near_first(pos, radius=10.0):
        if not bezier_pen or not bezier_pen.get("anchors"):
            return False
        first = bezier_pen["anchors"][0]["pt"]
        return math.hypot(pos[0] - first[0], pos[1] - first[1]) <= radius

    def _bezier_pen_commit_or_cancel():
        """Finish open bezier pen path if drawable, else cancel. Safe to call anytime."""
        if bezier_pen is None:
            return False
        if len((bezier_pen or {}).get("anchors") or []) >= 2:
            return _bezier_pen_finish(close_path=False)
        _bezier_pen_cancel()
        return False



    def snap_world(pos, threshold_px=8.0):
        """Snap a world point to guides or the grid while drawing."""
        z = float(getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0)
        use_grid = bool(getattr(cfg, "SNAP_TO_GRID", False))
        if not use_grid and not guides:
            return pos
        snapped, _kind = snap_point(
            pos, grid_size=float(getattr(cfg, "GRID_SIZE", 20.0) or 20.0),
            guides=guides, threshold=float(threshold_px) / z, use_grid=use_grid)
        return snapped

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        hover_snap = None
        hover_snap_kind = "connect"
        if in_canvas(mouse_pos) and (tool_mode == "draw" or redrawing_curve is not None):
            cpos = to_canvas(mouse_pos)
            if redrawing_curve is not None:
                rpts = redrawing_curve.get("points", [])
                fixed_start = redrawing_curve.get("fixed_start")
                fixed_end = redrawing_curve.get("fixed_end")
                if not redrawing_curve.get("started") and fixed_start is not None:
                    # show fixed start as connect snap
                    hover_snap = tuple(fixed_start)
                    hover_snap_kind = "connect"
                elif redrawing_curve.get("started") and fixed_end is not None:
                    # show fixed end as target snap while drawing
                    hover_snap = tuple(fixed_end)
                    hover_snap_kind = "connect"
                else:
                    extras = [rpts[0]] if rpts else None
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    hover_snap, hover_snap_kind = draw_snap_info(cpos, strokes, snap_radius(), shift_held, extra_points=extras)
            elif tool_mode == "draw":
                if draw_tool == "pen" and draw_shape == "pen" and bezier_pen is not None:
                    # Bezier pen: show snap for next anchor (or first-anchor close target).
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
            ctx = types.SimpleNamespace()
            ctx._shape_state_counter = _shape_state_counter
            ctx._symbol_counter = _symbol_counter
            ctx.active_artboard = active_artboard
            ctx.artboards = artboards
            ctx.clipboard_strokes = clipboard_strokes
            ctx.current_points = current_points
            ctx.curve_cut_mode = curve_cut_mode
            ctx.cut_points = cut_points
            ctx.cutting = cutting
            ctx.document_path = document_path
            ctx.drag_last = drag_last
            ctx.draw_tool = draw_tool
            ctx.drawing = drawing
            ctx.export_dialog_format = export_dialog_format
            ctx.export_dialog_open = export_dialog_open
            ctx.eyedropper_pick = eyedropper_pick
            ctx.help_open = help_open
            ctx.panel_collapsed = panel_collapsed
            ctx.redrawing_curve = redrawing_curve
            ctx.running = running
            ctx.selected_curve = selected_curve
            ctx.selected_curves = selected_curves
            ctx.selected_point = selected_point
            ctx.selected_strokes = selected_strokes
            ctx.selection_submode = selection_submode
            ctx.shape_states = shape_states
            ctx.snap_enabled = snap_enabled
            ctx.symbols = symbols
            ctx.text_entry = text_entry
            ctx.text_family = text_family
            ctx.text_size = text_size
            ctx.tool_mode = tool_mode
            ctx.transform_drag = transform_drag
            ctx.workspace = workspace
            ctx._bezier_pen_cancel = _bezier_pen_cancel
            ctx._bezier_pen_commit_or_cancel = _bezier_pen_commit_or_cancel
            ctx._capture_shape_state = _capture_shape_state
            ctx._copy_stroke = _copy_stroke
            ctx._delete_shape_state = _delete_shape_state
            ctx._insert_shape_state = _insert_shape_state
            ctx.assign_group = assign_group
            ctx.cfg = cfg
            ctx.clear_group = clear_group
            ctx.combined_bbox = combined_bbox
            ctx.copy = copy
            ctx.do_redo = do_redo
            ctx.do_undo = do_undo
            ctx.import_svg = import_svg
            ctx.load_document_with_meta = load_document_with_meta
            ctx.new_group_id = new_group_id
            ctx.pick_import_svg_path = pick_import_svg_path
            ctx.pick_open_document_path = pick_open_document_path
            ctx.pick_save_document_path = pick_save_document_path
            ctx.push_undo = push_undo
            ctx.relayout = relayout
            ctx.save_document = save_document
            ctx.state = state
            ctx.strokes = strokes
            ctx.translate_stroke = translate_stroke
            from controllers.menu_actions import run_menu_action as _rma
            result = _rma(ctx, key)
            _shape_state_counter = ctx._shape_state_counter
            _symbol_counter = ctx._symbol_counter
            active_artboard = ctx.active_artboard
            artboards = ctx.artboards
            clipboard_strokes = ctx.clipboard_strokes
            current_points = ctx.current_points
            curve_cut_mode = ctx.curve_cut_mode
            cut_points = ctx.cut_points
            cutting = ctx.cutting
            document_path = ctx.document_path
            drag_last = ctx.drag_last
            draw_tool = ctx.draw_tool
            drawing = ctx.drawing
            export_dialog_format = ctx.export_dialog_format
            export_dialog_open = ctx.export_dialog_open
            eyedropper_pick = ctx.eyedropper_pick
            help_open = ctx.help_open
            panel_collapsed = ctx.panel_collapsed
            redrawing_curve = ctx.redrawing_curve
            running = ctx.running
            selected_curve = ctx.selected_curve
            selected_curves = ctx.selected_curves
            selected_point = ctx.selected_point
            selected_strokes = ctx.selected_strokes
            selection_submode = ctx.selection_submode
            shape_states = ctx.shape_states
            snap_enabled = ctx.snap_enabled
            symbols = ctx.symbols
            text_entry = ctx.text_entry
            text_family = ctx.text_family
            text_size = ctx.text_size
            tool_mode = ctx.tool_mode
            transform_drag = ctx.transform_drag
            workspace = ctx.workspace
            return result

        # Event loop (extracted)
        import types as _types
        _ev_ctx=_types.SimpleNamespace()
        _ev_ctx.__dict__.update({k:v for k,v in locals().items()})
        from controllers.event_loop import process_events as _pe
        _pe(_ev_ctx)
        if hasattr(_ev_ctx,'_'): _=_ev_ctx._
        if hasattr(_ev_ctx,'_bezier_last_click'): _bezier_last_click=_ev_ctx._bezier_last_click
        if hasattr(_ev_ctx,'a'): a=_ev_ctx.a
        if hasattr(_ev_ctx,'algo_name'): algo_name=_ev_ctx.algo_name
        if hasattr(_ev_ctx,'alpha'): alpha=_ev_ctx.alpha
        if hasattr(_ev_ctx,'anchors'): anchors=_ev_ctx.anchors
        if hasattr(_ev_ctx,'b'): b=_ev_ctx.b
        if hasattr(_ev_ctx,'bar'): bar=_ev_ctx.bar
        if hasattr(_ev_ctx,'base'): base=_ev_ctx.base
        if hasattr(_ev_ctx,'bb'): bb=_ev_ctx.bb
        if hasattr(_ev_ctx,'best_d'): best_d=_ev_ctx.best_d
        if hasattr(_ev_ctx,'bezier_pen'): bezier_pen=_ev_ctx.bezier_pen
        if hasattr(_ev_ctx,'boost_points'): boost_points=_ev_ctx.boost_points
        if hasattr(_ev_ctx,'boxes'): boxes=_ev_ctx.boxes
        if hasattr(_ev_ctx,'bucket_fill_color'): bucket_fill_color=_ev_ctx.bucket_fill_color
        if hasattr(_ev_ctx,'bucket_picker_drag'): bucket_picker_drag=_ev_ctx.bucket_picker_drag
        if hasattr(_ev_ctx,'c1'): c1=_ev_ctx.c1
        if hasattr(_ev_ctx,'c2'): c2=_ev_ctx.c2
        if hasattr(_ev_ctx,'cfg'): cfg=_ev_ctx.cfg
        if hasattr(_ev_ctx,'clock'): clock=_ev_ctx.clock
        if hasattr(_ev_ctx,'col'): col=_ev_ctx.col
        if hasattr(_ev_ctx,'color_target'): color_target=_ev_ctx.color_target
        if hasattr(_ev_ctx,'comp_i'): comp_i=_ev_ctx.comp_i
        if hasattr(_ev_ctx,'comps'): comps=_ev_ctx.comps
        if hasattr(_ev_ctx,'corner_radius'): corner_radius=_ev_ctx.corner_radius
        if hasattr(_ev_ctx,'cpos'): cpos=_ev_ctx.cpos
        if hasattr(_ev_ctx,'current_points'): current_points=_ev_ctx.current_points
        if hasattr(_ev_ctx,'curve_cut_mode'): curve_cut_mode=_ev_ctx.curve_cut_mode
        if hasattr(_ev_ctx,'cut_gap'): cut_gap=_ev_ctx.cut_gap
        if hasattr(_ev_ctx,'cut_points'): cut_points=_ev_ctx.cut_points
        if hasattr(_ev_ctx,'cutting'): cutting=_ev_ctx.cutting
        if hasattr(_ev_ctx,'cx'): cx=_ev_ctx.cx
        if hasattr(_ev_ctx,'cy'): cy=_ev_ctx.cy
        if hasattr(_ev_ctx,'d'): d=_ev_ctx.d
        if hasattr(_ev_ctx,'drag_last'): drag_last=_ev_ctx.drag_last
        if hasattr(_ev_ctx,'draw_shape'): draw_shape=_ev_ctx.draw_shape
        if hasattr(_ev_ctx,'draw_tool'): draw_tool=_ev_ctx.draw_tool
        if hasattr(_ev_ctx,'drawing'): drawing=_ev_ctx.drawing
        if hasattr(_ev_ctx,'dx'): dx=_ev_ctx.dx
        if hasattr(_ev_ctx,'dy'): dy=_ev_ctx.dy
        if hasattr(_ev_ctx,'ellipse_segments'): ellipse_segments=_ev_ctx.ellipse_segments
        if hasattr(_ev_ctx,'ellipse_variant'): ellipse_variant=_ev_ctx.ellipse_variant
        if hasattr(_ev_ctx,'end'): end=_ev_ctx.end
        if hasattr(_ev_ctx,'event'): event=_ev_ctx.event
        if hasattr(_ev_ctx,'export_dialog_format'): export_dialog_format=_ev_ctx.export_dialog_format
        if hasattr(_ev_ctx,'export_dialog_open'): export_dialog_open=_ev_ctx.export_dialog_open
        if hasattr(_ev_ctx,'export_dpi'): export_dpi=_ev_ctx.export_dpi
        if hasattr(_ev_ctx,'export_scale'): export_scale=_ev_ctx.export_scale
        if hasattr(_ev_ctx,'eyedropper_pick'): eyedropper_pick=_ev_ctx.eyedropper_pick
        if hasattr(_ev_ctx,'field'): field=_ev_ctx.field
        if hasattr(_ev_ctx,'fill_color'): fill_color=_ev_ctx.fill_color
        if hasattr(_ev_ctx,'fill_stop_pos_drag'): fill_stop_pos_drag=_ev_ctx.fill_stop_pos_drag
        if hasattr(_ev_ctx,'first'): first=_ev_ctx.first
        if hasattr(_ev_ctx,'fixed_end'): fixed_end=_ev_ctx.fixed_end
        if hasattr(_ev_ctx,'fixed_start'): fixed_start=_ev_ctx.fixed_start
        if hasattr(_ev_ctx,'gradient_drag'): gradient_drag=_ev_ctx.gradient_drag
        if hasattr(_ev_ctx,'guide_drag'): guide_drag=_ev_ctx.guide_drag
        if hasattr(_ev_ctx,'guides'): guides=_ev_ctx.guides
        if hasattr(_ev_ctx,'h'): h=_ev_ctx.h
        if hasattr(_ev_ctx,'help_open'): help_open=_ev_ctx.help_open
        if hasattr(_ev_ctx,'i'): i=_ev_ctx.i
        if hasattr(_ev_ctx,'idxs'): idxs=_ev_ctx.idxs
        if hasattr(_ev_ctx,'items'): items=_ev_ctx.items
        if hasattr(_ev_ctx,'k'): k=_ev_ctx.k
        if hasattr(_ev_ctx,'key'): key=_ev_ctx.key
        if hasattr(_ev_ctx,'keys'): keys=_ev_ctx.keys
        if hasattr(_ev_ctx,'limit'): limit=_ev_ctx.limit
        if hasattr(_ev_ctx,'line_arrow'): line_arrow=_ev_ctx.line_arrow
        if hasattr(_ev_ctx,'line_constrain'): line_constrain=_ev_ctx.line_constrain
        if hasattr(_ev_ctx,'marker_dropdown'): marker_dropdown=_ev_ctx.marker_dropdown
        if hasattr(_ev_ctx,'marquee_select'): marquee_select=_ev_ctx.marquee_select
        if hasattr(_ev_ctx,'max_points_per_curve'): max_points_per_curve=_ev_ctx.max_points_per_curve
        if hasattr(_ev_ctx,'menu_open'): menu_open=_ev_ctx.menu_open
        if hasattr(_ev_ctx,'mode'): mode=_ev_ctx.mode
        if hasattr(_ev_ctx,'n'): n=_ev_ctx.n
        if hasattr(_ev_ctx,'new_h'): new_h=_ev_ctx.new_h
        if hasattr(_ev_ctx,'new_w'): new_w=_ev_ctx.new_w
        if hasattr(_ev_ctx,'obj_opacity_drag'): obj_opacity_drag=_ev_ctx.obj_opacity_drag
        if hasattr(_ev_ctx,'only'): only=_ev_ctx.only
        if hasattr(_ev_ctx,'opacity'): opacity=_ev_ctx.opacity
        if hasattr(_ev_ctx,'p'): p=_ev_ctx.p
        if hasattr(_ev_ctx,'p0'): p0=_ev_ctx.p0
        if hasattr(_ev_ctx,'p3'): p3=_ev_ctx.p3
        if hasattr(_ev_ctx,'pan_drag'): pan_drag=_ev_ctx.pan_drag
        if hasattr(_ev_ctx,'panel_collapsed'): panel_collapsed=_ev_ctx.panel_collapsed
        if hasattr(_ev_ctx,'panel_scroll'): panel_scroll=_ev_ctx.panel_scroll
        if hasattr(_ev_ctx,'path'): path=_ev_ctx.path
        if hasattr(_ev_ctx,'pending_transform_toggle'): pending_transform_toggle=_ev_ctx.pending_transform_toggle
        if hasattr(_ev_ctx,'picker_drag_alpha'): picker_drag_alpha=_ev_ctx.picker_drag_alpha
        if hasattr(_ev_ctx,'picker_drag_hue'): picker_drag_hue=_ev_ctx.picker_drag_hue
        if hasattr(_ev_ctx,'picker_drag_sv'): picker_drag_sv=_ev_ctx.picker_drag_sv
        if hasattr(_ev_ctx,'picker_h'): picker_h=_ev_ctx.picker_h
        if hasattr(_ev_ctx,'picker_s'): picker_s=_ev_ctx.picker_s
        if hasattr(_ev_ctx,'picker_v'): picker_v=_ev_ctx.picker_v
        if hasattr(_ev_ctx,'pivot_drag'): pivot_drag=_ev_ctx.pivot_drag
        if hasattr(_ev_ctx,'pivot_pos'): pivot_pos=_ev_ctx.pivot_pos
        if hasattr(_ev_ctx,'polygon_sides'): polygon_sides=_ev_ctx.polygon_sides
        if hasattr(_ev_ctx,'pos'): pos=_ev_ctx.pos
        if hasattr(_ev_ctx,'primary'): primary=_ev_ctx.primary
        if hasattr(_ev_ctx,'primary_i'): primary_i=_ev_ctx.primary_i
        if hasattr(_ev_ctx,'pts'): pts=_ev_ctx.pts
        if hasattr(_ev_ctx,'r'): r=_ev_ctx.r
        if hasattr(_ev_ctx,'rect_variant'): rect_variant=_ev_ctx.rect_variant
        if hasattr(_ev_ctx,'redrawing_curve'): redrawing_curve=_ev_ctx.redrawing_curve
        if hasattr(_ev_ctx,'ref_drag'): ref_drag=_ev_ctx.ref_drag
        if hasattr(_ev_ctx,'ref_opacity_drag'): ref_opacity_drag=_ev_ctx.ref_opacity_drag
        if hasattr(_ev_ctx,'reference_error'): reference_error=_ev_ctx.reference_error
        if hasattr(_ev_ctx,'reference_image'): reference_image=_ev_ctx.reference_image
        if hasattr(_ev_ctx,'repeat_pick_mode'): repeat_pick_mode=_ev_ctx.repeat_pick_mode
        if hasattr(_ev_ctx,'repeat_pick_target'): repeat_pick_target=_ev_ctx.repeat_pick_target
        if hasattr(_ev_ctx,'result'): result=_ev_ctx.result
        if hasattr(_ev_ctx,'running'): running=_ev_ctx.running
        if hasattr(_ev_ctx,'s'): s=_ev_ctx.s
        if hasattr(_ev_ctx,'s1'): s1=_ev_ctx.s1
        if hasattr(_ev_ctx,'screen'): screen=_ev_ctx.screen
        if hasattr(_ev_ctx,'scx'): scx=_ev_ctx.scx
        if hasattr(_ev_ctx,'scy'): scy=_ev_ctx.scy
        if hasattr(_ev_ctx,'segs'): segs=_ev_ctx.segs
        if hasattr(_ev_ctx,'sel'): sel=_ev_ctx.sel
        if hasattr(_ev_ctx,'sel_list'): sel_list=_ev_ctx.sel_list
        if hasattr(_ev_ctx,'selected_curve'): selected_curve=_ev_ctx.selected_curve
        if hasattr(_ev_ctx,'selected_curves'): selected_curves=_ev_ctx.selected_curves
        if hasattr(_ev_ctx,'selected_point'): selected_point=_ev_ctx.selected_point
        if hasattr(_ev_ctx,'selected_strokes'): selected_strokes=_ev_ctx.selected_strokes
        if hasattr(_ev_ctx,'selection_submode'): selection_submode=_ev_ctx.selection_submode
        if hasattr(_ev_ctx,'shadow'): shadow=_ev_ctx.shadow
        if hasattr(_ev_ctx,'shape_menu_anchor'): shape_menu_anchor=_ev_ctx.shape_menu_anchor
        if hasattr(_ev_ctx,'shape_menu_key'): shape_menu_key=_ev_ctx.shape_menu_key
        if hasattr(_ev_ctx,'shift_held'): shift_held=_ev_ctx.shift_held
        if hasattr(_ev_ctx,'si'): si=_ev_ctx.si
        if hasattr(_ev_ctx,'smart_snap_guides'): smart_snap_guides=_ev_ctx.smart_snap_guides
        if hasattr(_ev_ctx,'snap'): snap=_ev_ctx.snap
        if hasattr(_ev_ctx,'snap_enabled'): snap_enabled=_ev_ctx.snap_enabled
        if hasattr(_ev_ctx,'sp'): sp=_ev_ctx.sp
        if hasattr(_ev_ctx,'space_panning'): space_panning=_ev_ctx.space_panning
        if hasattr(_ev_ctx,'st'): st=_ev_ctx.st
        if hasattr(_ev_ctx,'star_inner_ratio'): star_inner_ratio=_ev_ctx.star_inner_ratio
        if hasattr(_ev_ctx,'star_points'): star_points=_ev_ctx.star_points
        if hasattr(_ev_ctx,'start_strokes'): start_strokes=_ev_ctx.start_strokes
        if hasattr(_ev_ctx,'state'): state=_ev_ctx.state
        if hasattr(_ev_ctx,'strokes'): strokes=_ev_ctx.strokes
        if hasattr(_ev_ctx,'sv'): sv=_ev_ctx.sv
        if hasattr(_ev_ctx,'sx1'): sx1=_ev_ctx.sx1
        if hasattr(_ev_ctx,'sy1'): sy1=_ev_ctx.sy1
        if hasattr(_ev_ctx,'tcx'): tcx=_ev_ctx.tcx
        if hasattr(_ev_ctx,'tcy'): tcy=_ev_ctx.tcy
        if hasattr(_ev_ctx,'text_entry'): text_entry=_ev_ctx.text_entry
        if hasattr(_ev_ctx,'text_family'): text_family=_ev_ctx.text_family
        if hasattr(_ev_ctx,'text_size'): text_size=_ev_ctx.text_size
        if hasattr(_ev_ctx,'tool_mode'): tool_mode=_ev_ctx.tool_mode
        if hasattr(_ev_ctx,'trace_algorithm'): trace_algorithm=_ev_ctx.trace_algorithm
        if hasattr(_ev_ctx,'transform_drag'): transform_drag=_ev_ctx.transform_drag
        if hasattr(_ev_ctx,'transform_handle_mode'): transform_handle_mode=_ev_ctx.transform_handle_mode
        if hasattr(_ev_ctx,'triangle_variant'): triangle_variant=_ev_ctx.triangle_variant
        if hasattr(_ev_ctx,'tx1'): tx1=_ev_ctx.tx1
        if hasattr(_ev_ctx,'ty1'): ty1=_ev_ctx.ty1
        if hasattr(_ev_ctx,'v'): v=_ev_ctx.v
        if hasattr(_ev_ctx,'val'): val=_ev_ctx.val
        if hasattr(_ev_ctx,'w'): w=_ev_ctx.w
        if hasattr(_ev_ctx,'wave_custom_drag'): wave_custom_drag=_ev_ctx.wave_custom_drag
        if hasattr(_ev_ctx,'wave_formula_focus'): wave_formula_focus=_ev_ctx.wave_formula_focus
        if hasattr(_ev_ctx,'wave_slider_drag'): wave_slider_drag=_ev_ctx.wave_slider_drag
        if hasattr(_ev_ctx,'workspace'): workspace=_ev_ctx.workspace
        if hasattr(_ev_ctx,'xform_field_buffer'): xform_field_buffer=_ev_ctx.xform_field_buffer
        if hasattr(_ev_ctx,'xform_field_focus'): xform_field_focus=_ev_ctx.xform_field_focus
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
