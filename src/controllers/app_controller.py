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
            """Execute a menu command.

            Keyboard shortcuts and menu clicks both funnel through here so a
            command behaves identically no matter how it was invoked.
            """
            nonlocal document_path, selected_strokes, selected_point, selected_curve
            nonlocal selected_curves, transform_drag, drag_last, redrawing_curve
            nonlocal clipboard_strokes, tool_mode, draw_tool, drawing, current_points
            nonlocal eyedropper_pick, cutting, cut_points, curve_cut_mode
            nonlocal text_entry, text_family, text_size
            nonlocal selection_submode, snap_enabled, panel_collapsed, help_open, running, export_dialog_open, export_dialog_format
            nonlocal artboards, active_artboard, symbols, _symbol_counter
            nonlocal shape_states, _shape_state_counter
            nonlocal workspace

            if key == "new":
                _bezier_pen_cancel()
                push_undo()
                strokes.clear()
                selected_strokes.clear(); selected_point = None; selected_curve = None
                selected_curves.clear(); transform_drag = None; drag_last = None
                redrawing_curve = None
                document_path = None
                artboards = []
                active_artboard = -1
                symbols = {}
                _symbol_counter = 0
                shape_states = {}
                _shape_state_counter = 0
            elif key == "save":
                try:
                    if document_path is None:
                        document_path = pick_save_document_path()
                    if document_path:
                        save_document(document_path, strokes, {"view": {"zoom": cfg.VIEW_ZOOM, "pan": [cfg.VIEW_PAN_X, cfg.VIEW_PAN_Y]}, "artboards": list(artboards or []), "active_artboard": int(active_artboard), "symbols": copy.deepcopy(symbols), "shape_states": copy.deepcopy(shape_states)})
                except Exception:
                    pass
            elif key == "save_as":
                try:
                    path = pick_save_document_path()
                    if path:
                        document_path = path
                        save_document(document_path, strokes, {"view": {"zoom": cfg.VIEW_ZOOM, "pan": [cfg.VIEW_PAN_X, cfg.VIEW_PAN_Y]}, "artboards": list(artboards or []), "active_artboard": int(active_artboard), "symbols": copy.deepcopy(symbols), "shape_states": copy.deepcopy(shape_states)})
                except Exception:
                    pass
            elif key == "open":
                try:
                    path = pick_open_document_path()
                    if path:
                        loaded, meta = load_document_with_meta(path)
                        _bezier_pen_cancel()
                        push_undo()
                        strokes.clear(); strokes.extend(loaded)
                        selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
                        transform_drag = None; drag_last = None; redrawing_curve = None
                        document_path = path
                        # Restore the saved camera, artboards, and symbols.
                        meta = meta or {}
                        view = meta.get("view") or {}
                        if isinstance(view, dict):
                            if isinstance(view.get("zoom"), (int, float)):
                                cfg.VIEW_ZOOM = max(0.1, min(20.0, float(view["zoom"])))
                            pan = view.get("pan")
                            if isinstance(pan, (list, tuple)) and len(pan) == 2:
                                cfg.VIEW_PAN_X = float(pan[0]); cfg.VIEW_PAN_Y = float(pan[1])
                        _abs = meta.get("artboards")
                        artboards = [dict(a) for a in _abs] if isinstance(_abs, list) else []
                        try:
                            active_artboard = int(meta.get("active_artboard", -1))
                        except Exception:
                            active_artboard = -1
                        if not (0 <= active_artboard < len(artboards)):
                            active_artboard = -1
                        _syms = meta.get("symbols")
                        symbols = copy.deepcopy(_syms) if isinstance(_syms, dict) else {}
                        _symbol_counter = 0
                        try:
                            for _sid in symbols.keys():
                                if isinstance(_sid, str) and _sid.startswith("sym"):
                                    _n = int(''.join(ch for ch in _sid[3:] if ch.isdigit()) or '0')
                                    _symbol_counter = max(_symbol_counter, _n)
                        except Exception:
                            pass
                        _ssts = meta.get("shape_states")
                        shape_states = copy.deepcopy(_ssts) if isinstance(_ssts, dict) else {}
                        _shape_state_counter = 0
                        try:
                            for _sid in shape_states.keys():
                                if isinstance(_sid, str) and _sid.startswith("shape"):
                                    _n = int(''.join(ch for ch in _sid[len("shape"):] if ch.isdigit()) or '0')
                                    _shape_state_counter = max(_shape_state_counter, _n)
                        except Exception:
                            pass
                except Exception:
                    pass
            elif key == "import_svg":
                try:
                    path = pick_import_svg_path()
                    if path:
                        imported = import_svg(path)
                        if imported:
                            _bezier_pen_cancel()
                            push_undo()
                            strokes.clear(); strokes.extend(imported)
                            selected_strokes.clear(); selected_point = None
                            selected_curve = None; selected_curves.clear()
                            transform_drag = None; drag_last = None; redrawing_curve = None
                            document_path = None
                            artboards = []
                            active_artboard = -1
                            symbols = {}
                            _symbol_counter = 0
                            shape_states = {}
                            _shape_state_counter = 0
                except Exception:
                    pass
            elif key == "export":
                export_dialog_open = True
                help_open = False
            elif key == "quit":
                running = False
            elif key == "undo":
                _bezier_pen_cancel()
                if do_undo():
                    selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
                selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
            elif key == "redo":
                _bezier_pen_cancel()
                if do_redo():
                    selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
                selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
            elif key == "select_all":
                selected_strokes = set(range(len(strokes)))
                selected_point = None; selected_curve = None
            elif key == "duplicate":
                if selected_strokes:
                    push_undo()
                    new_sel = set()
                    for i in sorted(selected_strokes):
                        if 0 <= i < len(strokes):
                            dup = _copy_stroke(strokes[i])
                            translate_stroke(dup, 16, 16)
                            strokes.append(dup)
                            new_sel.add(len(strokes) - 1)
                    if new_sel:
                        selected_strokes = new_sel
                        selected_point = None; selected_curve = None
            elif key == "group":
                if len(selected_strokes) >= 2:
                    push_undo()
                    new_group = new_group_id()
                    for i in sorted(selected_strokes):
                        if 0 <= i < len(strokes):
                            strokes[i] = assign_group(strokes[i], new_group)
            elif key == "ungroup":
                if selected_strokes:
                    push_undo()
                    for i in sorted(selected_strokes):
                        if 0 <= i < len(strokes):
                            strokes[i] = clear_group(strokes[i])
            elif key == "copy":
                if selected_strokes:
                    clipboard_strokes = [_copy_stroke(strokes[i]) for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
            elif key == "cut":
                if selected_strokes:
                    clipboard_strokes = [_copy_stroke(strokes[i]) for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                    push_undo()
                    for i in sorted(selected_strokes, reverse=True):
                        if 0 <= i < len(strokes):
                            strokes.pop(i)
                    selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
            elif key == "paste":
                if clipboard_strokes:
                    push_undo()
                    new_sel = set()
                    for st in clipboard_strokes:
                        dup = _copy_stroke(st)
                        translate_stroke(dup, 16, 16)
                        strokes.append(dup)
                        new_sel.add(len(strokes) - 1)
                    if new_sel:
                        selected_strokes = new_sel
                        selected_point = None; selected_curve = None
            elif key == "delete":
                if selected_strokes:
                    push_undo()
                    for i in sorted(selected_strokes, reverse=True):
                        if 0 <= i < len(strokes):
                            strokes.pop(i)
                    selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None
            elif key == "fit":
                if strokes:
                    bb = combined_bbox(strokes, list(range(len(strokes))))
                    if bb is not None:
                        bw = max(1.0, bb[2] - bb[0]); bh = max(1.0, bb[3] - bb[1])
                        vh = cfg.canvas_viewport_height()
                        z = min((cfg.CANVAS_W - 40) / bw, (vh - 40) / bh)
                        cfg.VIEW_ZOOM = max(0.1, min(20.0, z))
                        cfg.VIEW_PAN_X = (cfg.CANVAS_W - bw * cfg.VIEW_ZOOM) / 2 - bb[0] * cfg.VIEW_ZOOM
                        cfg.VIEW_PAN_Y = (vh - bh * cfg.VIEW_ZOOM) / 2 - bb[1] * cfg.VIEW_ZOOM
                else:
                    cfg.VIEW_ZOOM = 1.0; cfg.VIEW_PAN_X = 0.0; cfg.VIEW_PAN_Y = 0.0
            elif key == "actual_size":
                cfg.VIEW_ZOOM = 1.0; cfg.VIEW_PAN_X = 0.0; cfg.VIEW_PAN_Y = 0.0
            elif key == "toggle_panel":
                panel_collapsed = not panel_collapsed
                state["panel_collapsed"] = panel_collapsed
                relayout()
            elif key == "toggle_snap":
                snap_enabled = not snap_enabled
            elif key == "toggle_grid":
                cfg.SHOW_GRID = not getattr(cfg, "SHOW_GRID", False)
                state["show_grid"] = cfg.SHOW_GRID
            elif key == "toggle_rulers":
                cfg.SHOW_RULERS = not getattr(cfg, "SHOW_RULERS", False)
                state["show_rulers"] = cfg.SHOW_RULERS
            elif key == "toggle_grid_snap":
                cfg.SNAP_TO_GRID = not getattr(cfg, "SNAP_TO_GRID", False)
                state["snap_to_grid"] = cfg.SNAP_TO_GRID
            elif key == "clear_guides":
                guides = []
            elif key == "artboard_add":
                try:
                    w = float(getattr(cfg, "CANVAS_W", 800))
                    h = float(getattr(cfg, "canvas_viewport_height", lambda: getattr(cfg, "CANVAS_H", 600))())
                except Exception:
                    w, h = 800.0, 600.0
                artboards.append({"name": f"Artboard {len(artboards)+1}", "x": 0.0, "y": 0.0, "w": max(1.0, w), "h": max(1.0, h)})
                active_artboard = len(artboards) - 1
            elif key == "artboard_fit_selection":
                sel = [i for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                bb = combined_bbox(strokes, sel) if sel else None
                if bb is None and strokes:
                    bb = combined_bbox(strokes, list(range(len(strokes))))
                if bb is not None:
                    x0, y0, x1, y1 = bb
                    pad = 20.0
                    ab = {"name": f"Artboard {len(artboards)+1}", "x": float(x0 - pad), "y": float(y0 - pad),
                          "w": float(max(1.0, (x1 - x0) + pad*2)), "h": float(max(1.0, (y1 - y0) + pad*2))}
                    if 0 <= active_artboard < len(artboards):
                        ab["name"] = artboards[active_artboard].get("name", ab["name"])
                        artboards[active_artboard] = ab
                    else:
                        artboards.append(ab)
                        active_artboard = len(artboards) - 1
            elif key == "artboard_remove":
                if 0 <= active_artboard < len(artboards):
                    artboards.pop(active_artboard)
                    if not artboards:
                        active_artboard = -1
                    else:
                        active_artboard = min(active_artboard, len(artboards) - 1)
            elif key == "artboard_next":
                if artboards:
                    active_artboard = (active_artboard + 1) % len(artboards)
                else:
                    active_artboard = -1
            elif key == "symbol_create":
                sel = [i for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                if sel:
                    push_undo()
                    _symbol_counter += 1
                    sid = f"sym{_symbol_counter}"
                    # Capture definition from selection (as a reusable master set).
                    def_strokes = [copy.deepcopy(strokes[i]) for i in sel]
                    # Normalize definition origin to (0,0) relative to its bbox top-left for stable placement.
                    bb = combined_bbox(strokes, sel)
                    ox, oy = (bb[0], bb[1]) if bb else (0.0, 0.0)
                    norm_def = []
                    for st in def_strokes:
                        st.pop("symbol_id", None); st.pop("symbol_is_master", None); st.pop("symbol_instance_id", None)
                        norm_def.append(translate_stroke(st, -ox, -oy))
                    symbols[sid] = {"name": f"Symbol {_symbol_counter}", "strokes": norm_def, "origin": [float(ox), float(oy)]}
                    inst_id = f"{sid}:master"
                    for i in sel:
                        strokes[i]["symbol_id"] = sid
                        strokes[i]["symbol_is_master"] = True
                        strokes[i]["symbol_instance_id"] = inst_id
            elif key == "symbol_insert":
                # Choose symbol: from selection if present, else most recent/any available.
                sid = None
                for i in sorted(selected_strokes):
                    if 0 <= i < len(strokes) and isinstance(strokes[i], dict) and strokes[i].get("symbol_id"):
                        sid = strokes[i].get("symbol_id")
                        break
                if sid is None and symbols:
                    # prefer last created
                    sid = list(symbols.keys())[-1]
                sdef = symbols.get(sid) if sid else None
                def_strokes = (sdef or {}).get("strokes") if isinstance(sdef, dict) else None
                if sid and isinstance(def_strokes, list) and def_strokes:
                    push_undo()
                    # Place offset from selection bbox or definition origin.
                    offx = offy = 24.0
                    if selected_strokes:
                        bb = combined_bbox(strokes, [i for i in selected_strokes if 0 <= i < len(strokes)])
                        if bb:
                            offx = (bb[2] - bb[0]) * 0.2 + 24.0
                            offy = (bb[3] - bb[1]) * 0.2 + 24.0
                    origin = (sdef.get("origin") or [0.0, 0.0]) if isinstance(sdef, dict) else [0.0, 0.0]
                    try:
                        ox, oy = float(origin[0]), float(origin[1])
                    except Exception:
                        ox, oy = 0.0, 0.0
                    _symbol_counter += 1
                    inst_id = f"{sid}:i{_symbol_counter}"
                    new_indices = []
                    base = len(strokes)
                    for st in copy.deepcopy(def_strokes):
                        if not isinstance(st, dict):
                            continue
                        nst = translate_stroke(st, ox + offx, oy + offy)
                        nst["symbol_id"] = sid
                        nst["symbol_is_master"] = False
                        nst["symbol_instance_id"] = inst_id
                        strokes.append(nst)
                        new_indices.append(base)
                        base += 1
                    if new_indices:
                        selected_strokes = set(new_indices)
                        selected_point = None; selected_curve = None; selected_curves.clear()
            elif key == "symbol_update":
                # Update definition from master strokes of target symbol and propagate to instances.
                target_sid = None
                for i in sorted(selected_strokes):
                    if 0 <= i < len(strokes) and isinstance(strokes[i], dict) and strokes[i].get("symbol_id"):
                        target_sid = strokes[i].get("symbol_id")
                        break
                if target_sid and target_sid in symbols:
                    master_idx = [i for i, st in enumerate(strokes) if isinstance(st, dict) and st.get("symbol_id") == target_sid and st.get("symbol_is_master")]
                    if not master_idx:
                        # fall back to selected strokes if they belong to symbol
                        master_idx = [i for i in sorted(selected_strokes) if 0 <= i < len(strokes) and isinstance(strokes[i], dict) and strokes[i].get("symbol_id") == target_sid]
                    if master_idx:
                        push_undo()
                        mbb = combined_bbox(strokes, master_idx)
                        mox, moy = (mbb[0], mbb[1]) if mbb else (0.0, 0.0)
                        new_def = []
                        for i in master_idx:
                            st = copy.deepcopy(strokes[i])
                            st.pop("symbol_id", None); st.pop("symbol_is_master", None); st.pop("symbol_instance_id", None)
                            new_def.append(translate_stroke(st, -mox, -moy))
                        sdef = symbols.get(target_sid) or {}
                        sdef = dict(sdef)
                        sdef["strokes"] = new_def
                        sdef["origin"] = [float(mox), float(moy)]
                        symbols[target_sid] = sdef
                        # Propagate to instance groups (preserve each instance bbox top-left).
                        inst_groups = {}
                        for i, st in enumerate(strokes):
                            if not isinstance(st, dict):
                                continue
                            if st.get("symbol_id") == target_sid and not st.get("symbol_is_master"):
                                iid = st.get("symbol_instance_id") or f"_idx_{i}"
                                inst_groups.setdefault(iid, []).append(i)
                        # Replace from highest indices down to keep indices stable during removal.
                        for iid, idxs in list(inst_groups.items()):
                            idxs = sorted(idxs)
                            if not idxs:
                                continue
                            ibb = combined_bbox(strokes, idxs)
                            ix, iy = (ibb[0], ibb[1]) if ibb else (mox, moy)
                            # remove old instance strokes
                            for j in reversed(idxs):
                                if 0 <= j < len(strokes):
                                    strokes.pop(j)
                            # insert updated copies
                            insert_at = min(idxs) if idxs else len(strokes)
                            for st in copy.deepcopy(new_def):
                                if not isinstance(st, dict):
                                    continue
                                nst = translate_stroke(st, ix, iy)
                                nst["symbol_id"] = target_sid
                                nst["symbol_is_master"] = False
                                nst["symbol_instance_id"] = iid
                                strokes.insert(insert_at, nst)
                                insert_at += 1
                        # keep selection reasonable
                        selected_strokes = set(master_idx) if master_idx else set()
                        selected_point = None; selected_curve = None; selected_curves.clear()
            elif key == "symbol_detach":
                sel = [i for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                if sel:
                    push_undo()
                    for i in sel:
                        if isinstance(strokes[i], dict):
                            strokes[i].pop("symbol_id", None)
                            strokes[i].pop("symbol_is_master", None)
                            strokes[i].pop("symbol_instance_id", None)
            elif key == "shape_state_save":
                sel = [i for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                if sel:
                    push_undo()
                    sid, _sc = _capture_shape_state(strokes, sel, shape_states, _shape_state_counter)
                    _shape_state_counter = _sc
            elif key == "shape_state_insert":
                push_undo()
                new_indices, _sc = _insert_shape_state(strokes, shape_states, _shape_state_counter, sorted(selected_strokes))
                _shape_state_counter = _sc
                if new_indices:
                    selected_strokes = set(new_indices)
                    selected_point = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
            elif key == "shape_state_delete":
                sid = None
                for i in sorted(selected_strokes):
                    if 0 <= i < len(strokes) and isinstance(strokes[i], dict) and strokes[i].get("shape_state_id"):
                        sid = strokes[i].get("shape_state_id")
                        break
                if sid is None and shape_states:
                    sid = list(shape_states.keys())[-1]
                if sid and sid in shape_states:
                    push_undo()
                    _delete_shape_state(shape_states, sid, strokes)
            elif key == "workspace":
                workspace = "library" if workspace == "draw" else "draw"
                state["workspace"] = workspace
            elif key == "tool_select":
                _bezier_pen_commit_or_cancel()
                tool_mode = "selection"; drawing = False; current_points = []
                selected_point = None; drag_last = None; transform_drag = None
                curve_cut_mode = False; eyedropper_pick = False
            elif key == "tool_eyedropper":
                _bezier_pen_commit_or_cancel()
                tool_mode = "selection"; drawing = False; current_points = []
                eyedropper_pick = True
                cutting = False; cut_points = []
                curve_cut_mode = False
                redrawing_curve = None
                selected_point = None; drag_last = None; transform_drag = None
            elif key == "tool_pen":
                tool_mode = "draw"; draw_tool = "pen"; drawing = False; current_points = []
                selected_strokes.clear(); selected_point = None; transform_drag = None
                eyedropper_pick = False
            elif key == "tool_eraser":
                _bezier_pen_commit_or_cancel()
                tool_mode = "draw"; draw_tool = "eraser"; drawing = False; current_points = []
                selected_strokes.clear(); selected_point = None; transform_drag = None
                eyedropper_pick = False
            elif key == "tool_bucket":
                _bezier_pen_commit_or_cancel()
                tool_mode = "draw"; draw_tool = "bucket"; drawing = False; current_points = []
                selected_strokes.clear(); selected_point = None; transform_drag = None
                eyedropper_pick = False
            elif key == "tool_cutter":
                _bezier_pen_commit_or_cancel()
                tool_mode = "draw"; draw_tool = "cutter"; drawing = False; current_points = []
                cutting = False; cut_points = []
                selected_strokes.clear(); selected_point = None; transform_drag = None
                eyedropper_pick = False
            elif key == "tool_text":
                _bezier_pen_commit_or_cancel()
                tool_mode = "draw"; draw_tool = "text"; drawing = False; current_points = []
                text_entry = None
                selected_strokes.clear(); selected_point = None; transform_drag = None
                eyedropper_pick = False
            elif key == "cycle_submode":
                modes = ["transform", "nodes", "curve"]
                selection_submode = modes[(modes.index(selection_submode) + 1) % len(modes)] if selection_submode in modes else "transform"
                selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; redrawing_curve = None
                curve_cut_mode = False
            elif key == "shortcuts":
                help_open = not help_open

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.VIDEORESIZE:
                # Handle window resize - maintain layout
                new_w = max(800, event.w)
                new_h = max(400, event.h)
                # Recreate screen surface with new size
                screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                cfg.WIDTH = new_w
                cfg.HEIGHT = new_h
                relayout()

            if event.type == pygame.MOUSEWHEEL:
                _mx, _my = pygame.mouse.get_pos()
                if _mx >= cfg.PANEL_X:
                    # scroll the right panel when the pointer is over it
                    panel_scroll = max(0, int(panel_scroll - event.y * 48))
                    state["panel_scroll"] = panel_scroll
                elif in_canvas((_mx, _my)):
                    # zoom canvas toward cursor
                    old_z = float(getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0)
                    factor = 1.1 if event.y > 0 else (1 / 1.1)
                    new_z = max(0.1, min(20.0, old_z * (factor ** abs(event.y))))
                    if new_z != old_z:
                        wx, wy = to_canvas((_mx, _my))
                        cfg.VIEW_ZOOM = new_z
                        cfg.VIEW_PAN_X = _mx - cfg.CANVAS_X - wx * new_z
                        cfg.VIEW_PAN_Y = _my - wy * new_z

            if slider.handle_event(event):
                max_points_per_curve = slider.value
            _cut_gap_active = ((tool_mode == "draw" and draw_tool == "cutter")
                               or (tool_mode == "selection" and curve_cut_mode))
            if (_cut_gap_active and cut_gap_slider.track.width > 0
                    and cut_gap_slider.handle_event(event)):
                cut_gap = cut_gap_slider.value
                state["cut_gap"] = cut_gap
            comp_style_target = None
            if tool_mode == "selection" and selection_submode == "curve" and selected_curve and len(selected_strokes) == 1:
                scv = selected_curve
                if scv and scv[0] in selected_strokes:
                    comp_style_target = (scv[0], scv[1])
            point_style_target = None
            if tool_mode == "selection" and selection_submode == "nodes" and selected_point and len(selected_strokes) == 1:
                si = next(iter(selected_strokes))
                seg_i, pname = selected_point
                if pname in ("p0", "p3") and 0 <= si < len(strokes):
                    point_style_target = (si, seg_i, pname)
            if tool_mode == "selection" and selected_strokes and width_slider.handle_event(event):
                if selection_submode == "transform":
                    for si in selected_strokes:
                        if 0 <= si < len(strokes):
                            strokes[si]["stroke_width"] = float(width_slider.value)
                elif comp_style_target is not None:
                    si, ci = comp_style_target
                    if 0 <= si < len(strokes):
                        comps = _stroke_components(strokes[si])
                        if 0 <= ci < len(comps):
                            comps[ci]["stroke_width"] = float(width_slider.value)
                            strokes[si]["components"] = comps
                elif point_style_target is not None:
                    si, seg_i, pname = point_style_target
                    if 0 <= si < len(strokes):
                        set_point_width(strokes[si], seg_i, pname, float(width_slider.value))

            if event.type == pygame.KEYDOWN:
                if menu_open is not None and event.key == pygame.K_ESCAPE:
                    menu_open = None
                    continue
                if help_open:
                    if event.key == pygame.K_ESCAPE:
                        help_open = False
                        menu_open = None
                    continue
                if export_dialog_open:
                    if event.key == pygame.K_ESCAPE:
                        export_dialog_open = False
                    continue
                if text_entry is not None:
                    # Text insertion mode: capture keystrokes into the buffer so
                    # single-letter tool shortcuts never fire while typing.
                    if event.key == pygame.K_ESCAPE:
                        text_entry = None
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        commit_text_entry()
                    elif event.key == pygame.K_BACKSPACE:
                        text_entry["text"] = text_entry["text"][:-1]
                    elif event.key in (pygame.K_UP, pygame.K_DOWN) and \
                            bool(pygame.key.get_mods() & pygame.KMOD_CTRL):
                        text_entry["size"] = max(4.0, min(400.0,
                            text_entry["size"] + (2.0 if event.key == pygame.K_UP else -2.0)))
                    elif event.unicode and event.unicode.isprintable():
                        if len(text_entry["text"]) < 500:
                            text_entry["text"] += event.unicode
                    continue
                if xform_field_focus is not None and tool_mode == "selection" and selection_submode == "transform" and selected_strokes:
                    if event.key == pygame.K_ESCAPE:
                        _cancel_xform_field()
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        _commit_xform_field()
                    elif event.key == pygame.K_BACKSPACE:
                        xform_field_buffer = str(xform_field_buffer)[:-1]
                        state["xform_field_buffer"] = xform_field_buffer
                    elif event.key == pygame.K_UP:
                        step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
                        _apply_xform_field(xform_field_focus, step, relative=True)
                        xform_field_buffer = ""
                        state["xform_field_buffer"] = ""
                    elif event.key == pygame.K_DOWN:
                        step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
                        _apply_xform_field(xform_field_focus, -step, relative=True)
                        xform_field_buffer = ""
                        state["xform_field_buffer"] = ""
                    elif event.unicode and (event.unicode.isdigit() or event.unicode in ".-"):
                        if len(str(xform_field_buffer)) < 24:
                            xform_field_buffer = str(xform_field_buffer) + event.unicode
                            state["xform_field_buffer"] = xform_field_buffer
                    continue
                elif xform_field_focus is not None:
                    # Focus is stale (wrong mode/selection) — clear so keys aren't trapped.
                    _cancel_xform_field()
                # Bezier pen: Enter finishes open path, Escape cancels.
                if bezier_pen is not None and tool_mode == "draw" and draw_tool == "pen" and draw_shape == "pen":
                    if event.key == pygame.K_ESCAPE:
                        _bezier_pen_cancel()
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if len(bezier_pen.get("anchors", [])) >= 2:
                            _bezier_pen_finish(close_path=False)
                        else:
                            _bezier_pen_cancel()
                        continue
                    if event.key == pygame.K_BACKSPACE:
                        # Remove last placed anchor (useful correction while drawing).
                        anchors = bezier_pen.get("anchors", [])
                        if len(anchors) > 1:
                            anchors.pop()
                            bezier_pen["mouse_down"] = False
                            bezier_pen["dragging"] = False
                        else:
                            _bezier_pen_cancel()
                        continue
                if wave_formula_focus and tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes:
                    si, comp_i = selected_curve
                    if 0 <= si < len(strokes):
                        comps = _stroke_components(strokes[si])
                        if 0 <= comp_i < len(comps):
                            comps[comp_i] = dict(comps[comp_i])
                            wi = int(state.get("wave_active_index", 0) or 0)
                            w = _get_distortion_style(comps[comp_i], wi)
                            if w.get("type") == "wave":
                                formula = str(w.get("formula", "sin(x)") or "")
                                if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                                    wave_formula_focus = False
                                    state["wave_formula_focus"] = False
                                elif event.key == pygame.K_BACKSPACE:
                                    formula = formula[:-1]
                                    w["formula"] = formula
                                    _set_distortion_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                                elif event.unicode and event.unicode.isprintable():
                                    formula += event.unicode
                                    w["formula"] = formula
                                    _set_distortion_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                            else:
                                wave_formula_focus = False
                                state["wave_formula_focus"] = False
                    # consume key while editing formula (except we already handled)
                    if wave_formula_focus or event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE) or (event.unicode and event.unicode.isprintable()):
                        pass
                elif state.get("wave_custom_draw") and tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes:
                    # custom wave draw mode key handling: Esc/Enter finishes
                    si, comp_i = selected_curve
                    if 0 <= si < len(strokes):
                        comps = _stroke_components(strokes[si])
                        if 0 <= comp_i < len(comps):
                            if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                                state["wave_custom_draw"] = False
                                state["wave_custom_finished"] = True
                else:
                    mods = pygame.key.get_mods()
                    ctrl = bool(mods & pygame.KMOD_CTRL)
                    shift = bool(mods & pygame.KMOD_SHIFT)
                    # --- Esc: cancel/deselect first, quit only as fallback ---
                    if event.key == pygame.K_ESCAPE:
                        if eyedropper_pick:
                            eyedropper_pick = False
                        elif redrawing_curve is not None:
                            redrawing_curve = None
                        elif marquee_select is not None:
                            marquee_select = None
                        elif drawing:
                            drawing = False; current_points = []
                        elif transform_drag is not None or drag_last is not None or selected_strokes or selected_point or selected_curve:
                            selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
                            transform_drag = None; drag_last = None
                        elif space_panning:
                            space_panning = False; pan_drag = None
                        else:
                            running = False
                    # --- File: Save / Open / Export ---
                    elif ctrl and event.key == pygame.K_s and not shift:
                        run_menu_action("save")
                    elif ctrl and event.key == pygame.K_s and shift:
                        run_menu_action("save_as")
                    elif ctrl and event.key == pygame.K_n:
                        run_menu_action("new")
                    elif ctrl and event.key == pygame.K_o:
                        run_menu_action("open")
                    elif ctrl and shift and event.key == pygame.K_e:
                        run_menu_action("export")
                    # --- Select / clipboard / duplicate ---
                    elif ctrl and event.key == pygame.K_a:
                        run_menu_action("select_all")
                    elif ctrl and event.key == pygame.K_d:
                        run_menu_action("duplicate")
                    elif ctrl and event.key == pygame.K_g:
                        run_menu_action("ungroup" if shift else "group")
                    elif ctrl and event.key == pygame.K_c and not shift:
                        run_menu_action("copy")
                    elif ctrl and event.key == pygame.K_x:
                        run_menu_action("cut")
                    elif ctrl and event.key == pygame.K_v:
                        run_menu_action("paste")
                    # --- View ---
                    elif ctrl and event.key == pygame.K_0:
                        run_menu_action("fit")
                    elif ctrl and event.key == pygame.K_1:
                        run_menu_action("actual_size")
                    # --- Undo / Redo ---
                    elif ctrl and event.key == pygame.K_z:
                        run_menu_action("redo" if shift else "undo")
                    elif ctrl and event.key == pygame.K_y:
                        run_menu_action("redo")
                    # --- Tool switching (single-key, no modifiers) ---
                    elif not ctrl and event.key == pygame.K_v:
                        run_menu_action("tool_select")
                    elif not ctrl and event.key == pygame.K_i:
                        run_menu_action("tool_eyedropper")
                    elif not ctrl and event.key == pygame.K_b:
                        run_menu_action("tool_pen")
                    elif not ctrl and event.key == pygame.K_e:
                        run_menu_action("tool_eraser")
                    elif not ctrl and event.key == pygame.K_f:
                        run_menu_action("tool_bucket")
                    elif not ctrl and event.key == pygame.K_c:
                        run_menu_action("tool_cutter")
                    elif not ctrl and event.key == pygame.K_t:
                        run_menu_action("tool_text")
                    elif not ctrl and event.key == pygame.K_s:
                        run_menu_action("toggle_snap")
                    elif not ctrl and event.key == pygame.K_HASH:
                        run_menu_action("toggle_grid")
                    elif ctrl and event.key == pygame.K_r:
                        run_menu_action("toggle_rulers")
                    elif event.key == pygame.K_SPACE:
                        space_panning = True
                    # --- Editing ---
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and tool_mode == "selection":
                        run_menu_action("delete")
                    elif event.key == pygame.K_n and tool_mode == "selection":
                        run_menu_action("cycle_submode")
                    elif event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS):
                        max_points_per_curve = max(2, max_points_per_curve - 1); slider.value = max_points_per_curve
                    elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                        limit = BOOST_MAX_POINTS if boost_points else NORMAL_MAX_POINTS
                        max_points_per_curve = min(limit, max_points_per_curve + 1); slider.value = max_points_per_curve
                    elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        if drawing and tool_mode == "draw" and current_points:
                            snap = nearest_snap_point(current_points[0], strokes, snap_radius())
                            if snap is not None:
                                current_points[0] = snap
                        elif redrawing_curve is not None and redrawing_curve.get("started") and redrawing_curve.get("points"):
                            if redrawing_curve.get("fixed_start") is None:
                                snap = nearest_snap_point(redrawing_curve["points"][0], strokes, snap_radius())
                                if snap is not None:
                                    redrawing_curve["points"][0] = snap
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    space_panning = False
                    pan_drag = None
                if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    if drawing and tool_mode == "draw" and current_points:
                        snap = nearest_snap_point(current_points[-1], strokes, snap_radius())
                        if snap is not None:
                            current_points[-1] = snap
                    elif redrawing_curve is not None and redrawing_curve.get("started") and redrawing_curve.get("points"):
                        if redrawing_curve.get("fixed_end") is None:
                            snap = nearest_snap_point(redrawing_curve["points"][-1], strokes, snap_radius())
                            if snap is not None:
                                redrawing_curve["points"][-1] = snap

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                pan_drag = {"start_mouse": event.pos, "start_pan": (getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0))}
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if export_dialog_open:
                    continue
                # Right-click a bottom-bar shape tool: its options popup above the button.
                _shape_rects = state.get("draw_shape_rects", {})
                _rc_hit = next((k for k, r in _shape_rects.items() if r.collidepoint(event.pos)), None)
                _draw_keys = {k for k, _ in DRAW_SHAPES} | {k for k, _ in BOTTOM_TOOLS}
                if _rc_hit is not None and tool_mode == "draw" and _rc_hit in _draw_keys:
                    if shape_menu_key == _rc_hit:
                        shape_menu_key = None
                    else:
                        shape_menu_key = _rc_hit
                        shape_menu_anchor = _shape_rects[_rc_hit].copy()
                        menu_open = None
                else:
                    shape_menu_key = None
                state["shape_menu_key"] = shape_menu_key
                state["shape_menu_anchor"] = shape_menu_anchor
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Library workspace is view/browse-only: no drawing input.
                if workspace == "library":
                    drawing = False; current_points = []
                if export_dialog_open:
                    _edr = state.get("export_dialog_rects", {}) or {}
                    _card = _edr.get("card", pygame.Rect(0, 0, 0, 0))
                    if isinstance(_card, pygame.Rect) and _card.collidepoint(event.pos):
                        _hit = next((k for k, r in _edr.items()
                                     if k != "card" and isinstance(r, pygame.Rect) and r.collidepoint(event.pos)), None)
                        if _hit in ("cancel", "close"):
                            export_dialog_open = False
                        elif _hit == "export":
                            export_dialog_open = False
                            try:
                                path = pick_export_image_path(export_dialog_format)
                                if path:
                                    _exp_ab = artboards[active_artboard] if (0 <= active_artboard < len(artboards)) else None
                                    export_scene_image(path, strokes, ref_img=reference_image,
                                                       view_zoom=getattr(cfg, "VIEW_ZOOM", 1.0),
                                                       view_pan=(getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0)),
                                                       size=(cfg.CANVAS_W, cfg.canvas_viewport_height()),
                                                       scale=float(export_scale), dpi=int(export_dpi),
                                                       artboard=_exp_ab)
                            except Exception:
                                pass
                        elif _hit in ("format", "format_prev", "format_next"):
                            _fmts = ["png", "svg", "pdf", "eps", "jpg", "webp"]
                            try:
                                _fi = _fmts.index(str(export_dialog_format))
                            except ValueError:
                                _fi = 0
                            _fi = (_fi + (-1 if _hit == "format_prev" else 1)) % len(_fmts)
                            export_dialog_format = _fmts[_fi]
                        elif _hit in ("scale", "scale_prev", "scale_next"):
                            _scales = [1.0, 2.0, 3.0, 4.0]
                            try:
                                _si = _scales.index(float(export_scale))
                            except ValueError:
                                _si = 0
                            _si = (_si + (-1 if _hit == "scale_prev" else 1)) % len(_scales)
                            export_scale = _scales[_si]
                        elif _hit in ("dpi", "dpi_prev", "dpi_next"):
                            _dpis = [72, 96, 150, 300, 600]
                            try:
                                _di = _dpis.index(int(export_dpi))
                            except ValueError:
                                _di = 3
                            _di = (_di + (-1 if _hit == "dpi_prev" else 1)) % len(_dpis)
                            export_dpi = _dpis[_di]
                    else:
                        export_dialog_open = False
                    menu_open = None
                    continue
                if help_open:
                    help_open = False
                    menu_open = None
                    continue
                color_target = state.get("color_target", color_target)
                # Rulers & guides: drag from a ruler to create a guide, or grab
                # an existing guide to move it. Dropping on a ruler removes it.
                if getattr(cfg, "SHOW_RULERS", False):
                    _rs = int(RULER_SIZE)
                    _top_r = pygame.Rect(cfg.CANVAS_X, TOP_BAR_H, cfg.CANVAS_W, _rs)
                    _left_r = pygame.Rect(cfg.CANVAS_X, TOP_BAR_H, _rs, cfg.canvas_viewport_height())
                    if _top_r.collidepoint(event.pos):
                        guides = add_guide(guides, "x", to_canvas(event.pos)[0])
                        guide_drag = {"axis": "x", "index": len(guides) - 1}
                        continue
                    if _left_r.collidepoint(event.pos):
                        guides = add_guide(guides, "y", to_canvas(event.pos)[1])
                        guide_drag = {"axis": "y", "index": len(guides) - 1}
                        continue
                    if in_canvas(event.pos):
                        _gh = hit_guide(to_canvas(event.pos), guides,
                                        5.0 / (float(getattr(cfg, "VIEW_ZOOM", 1.0)) or 1.0))
                        if _gh is not None:
                            guide_drag = {"axis": guides[_gh]["axis"], "index": _gh}
                            continue
                # space+LMB -> pan
                if space_panning and in_canvas(event.pos):
                    pan_drag = {"start_mouse": event.pos, "start_pan": (getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0))}
                    continue
                # Collapse/expand the right sidebar.
                if state.get("panel_toggle_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                    panel_collapsed = not panel_collapsed
                    state["panel_collapsed"] = panel_collapsed
                    relayout()
                    continue
                if wave_formula_focus and not state.get("wave_formula_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    wave_formula_focus = False
                    state["wave_formula_focus"] = False
                # Top menu bar interactions
                menu_handled = False
                if event.pos[1] < TOP_BAR_H:
                    shape_menu_key = None
                    # Workspace switcher (Draw <-> Library) lives in the top bar.
                    if (isinstance(state.get("workspace_rect"), pygame.Rect)
                            and state["workspace_rect"].collidepoint(event.pos)):
                        workspace = "library" if workspace == "draw" else "draw"
                        state["workspace"] = workspace
                        menu_open = None
                        menu_handled = True
                    hit = next((k for k, r in menu_bar_rects.items()
                                if r.collidepoint(event.pos)), None)
                    menu_open = None if hit is None or menu_open == hit else hit
                    help_open = False
                    menu_handled = True
                elif menu_open is not None:
                    hit = next((k for k, r in menu_item_rects.items()
                                if r.collidepoint(event.pos)), None)
                    if hit is not None:
                        run_menu_action(hit)
                    # A click outside the dropdown only dismisses it.
                    menu_open = None
                    menu_handled = True
                if marker_dropdown is not None:
                    _mk_items = state.get("marker_dropdown_item_rects", {}) or {}
                    _mk_hit = next((k for k, r in _mk_items.items()
                                    if isinstance(r, pygame.Rect) and r.collidepoint(event.pos)), None)
                    _mk_anchor = state.get("marker_start_rect" if marker_dropdown == "start" else "marker_end_rect", pygame.Rect(0, 0, 0, 0))
                    if _mk_hit is not None:
                        push_undo()
                        for si in sorted(selected_strokes):
                            if 0 <= si < len(strokes) and isinstance(strokes[si], dict):
                                strokes[si] = set_marker(strokes[si], marker_dropdown, _mk_hit)
                        marker_dropdown = None
                        menu_handled = True
                    elif state.get("marker_dropdown_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                        menu_handled = True
                    elif isinstance(_mk_anchor, pygame.Rect) and _mk_anchor.collidepoint(event.pos):
                        # Let the marker button handler toggle it.
                        pass
                    else:
                        marker_dropdown = None
                    state["marker_dropdown"] = marker_dropdown
                if shape_menu_key is not None:
                    _menu_items = state.get("shape_menu_item_rects", {})
                    _menu_hit = next((k for k, r in _menu_items.items() if r.collidepoint(event.pos)), None)
                    if _menu_hit is not None:
                        if _menu_hit == "snap":
                            snap_enabled = not snap_enabled
                        elif _menu_hit.startswith("bucket_color_"):
                            try:
                                _bi = int(_menu_hit.rsplit("_", 1)[1])
                                if 0 <= _bi < len(BUCKET_SWATCHES):
                                    set_bucket_color(BUCKET_SWATCHES[_bi])
                            except ValueError:
                                pass
                            # Keep the popup open so several colors can be tried.
                        elif _menu_hit == "boost":
                            boost_points = not boost_points
                            slider.max_v = BOOST_MAX_POINTS if boost_points else NORMAL_MAX_POINTS
                            if not boost_points:
                                max_points_per_curve = min(max_points_per_curve, NORMAL_MAX_POINTS)
                            slider.value = max_points_per_curve
                        elif _menu_hit.startswith("choice_prev:") or _menu_hit.startswith("choice_next:"):
                            _cdir = -1 if _menu_hit.startswith("choice_prev:") else 1
                            _ckey = _menu_hit.split(":", 1)[1]
                            _choices = {
                                "trace_algorithm": [k for k, _ in TRACE_ALGORITHMS],
                                "triangle_variant": [k for k, _ in TRIANGLE_VARIANTS],
                                "rect_variant": ["rect", "square"],
                                "ellipse_variant": ["ellipse", "circle"],
                            }
                            _opts = _choices.get(_ckey, [])
                            if _opts:
                                if _ckey == "trace_algorithm":
                                    _cur = trace_algorithm if trace_algorithm in _opts else _opts[0]
                                elif _ckey == "triangle_variant":
                                    _cur = triangle_variant if triangle_variant in _opts else _opts[0]
                                elif _ckey == "rect_variant":
                                    _cur = rect_variant if rect_variant in _opts else _opts[0]
                                else:
                                    _cur = ellipse_variant if ellipse_variant in _opts else _opts[0]
                                _ni = (_opts.index(_cur) + _cdir) % len(_opts)
                                _nv = _opts[_ni]
                                if _ckey == "trace_algorithm":
                                    trace_algorithm = _nv
                                elif _ckey == "triangle_variant":
                                    triangle_variant = _nv
                                    if bezier_pen is not None:
                                        _bezier_pen_commit_or_cancel()
                                    draw_shape = "triangle"
                                    draw_tool = "pen"
                                    tool_mode = "draw"
                                elif _ckey == "rect_variant":
                                    rect_variant = _nv
                                    if bezier_pen is not None:
                                        _bezier_pen_commit_or_cancel()
                                    draw_shape = _nv
                                    draw_tool = "pen"
                                    tool_mode = "draw"
                                elif _ckey == "ellipse_variant":
                                    ellipse_variant = _nv
                                    if bezier_pen is not None:
                                        _bezier_pen_commit_or_cancel()
                                    draw_shape = _nv
                                    draw_tool = "pen"
                                    tool_mode = "draw"
                        elif _menu_hit in ("fit", "catmull-rom", "single"):
                            trace_algorithm = _menu_hit
                            shape_menu_key = None
                        elif _menu_hit in ("isosceles", "right", "equilateral"):
                            triangle_variant = _menu_hit
                            # Picking a type implies the triangle tool.
                            if bezier_pen is not None:
                                _bezier_pen_commit_or_cancel()
                            draw_shape = "triangle"
                            tool_mode = "draw"
                            shape_menu_key = None
                        elif _menu_hit in ("rect", "square"):
                            rect_variant = _menu_hit
                            if bezier_pen is not None:
                                _bezier_pen_commit_or_cancel()
                            draw_shape = _menu_hit
                            draw_tool = "pen"
                            tool_mode = "draw"
                            shape_menu_key = None
                        elif _menu_hit in ("ellipse", "circle"):
                            ellipse_variant = _menu_hit
                            if bezier_pen is not None:
                                _bezier_pen_commit_or_cancel()
                            draw_shape = _menu_hit
                            draw_tool = "pen"
                            tool_mode = "draw"
                            shape_menu_key = None
                        elif _menu_hit == "line_constrain":
                            line_constrain = not line_constrain
                        elif _menu_hit == "line_arrow":
                            line_arrow = not line_arrow
                        elif _menu_hit == "points_minus":
                            max_points_per_curve = max(2, max_points_per_curve - 1)
                            slider.value = max_points_per_curve
                        elif _menu_hit == "points_plus":
                            limit = BOOST_MAX_POINTS if boost_points else NORMAL_MAX_POINTS
                            max_points_per_curve = min(limit, max_points_per_curve + 1)
                            slider.value = max_points_per_curve
                        elif _menu_hit == "corner_minus":
                            corner_radius = max(0, corner_radius - 5)
                        elif _menu_hit == "corner_plus":
                            corner_radius = min(50, corner_radius + 5)
                        elif _menu_hit == "segments_minus":
                            ellipse_segments = max(4, ellipse_segments - 2)
                        elif _menu_hit == "segments_plus":
                            ellipse_segments = min(16, ellipse_segments + 2)
                        elif _menu_hit == "sides_minus":
                            polygon_sides = max(3, polygon_sides - 1)
                        elif _menu_hit == "sides_plus":
                            polygon_sides = min(24, polygon_sides + 1)
                        elif _menu_hit == "spokes_minus":
                            star_points = max(3, star_points - 1)
                        elif _menu_hit == "spokes_plus":
                            star_points = min(24, star_points + 1)
                        elif _menu_hit == "inner_minus":
                            star_inner_ratio = max(0.1, round(star_inner_ratio - 0.05, 2))
                        elif _menu_hit == "inner_plus":
                            star_inner_ratio = min(0.9, round(star_inner_ratio + 0.05, 2))
                        elif _menu_hit == "gap_minus":
                            cut_gap = max(0, cut_gap - 2)
                            cut_gap_slider.value = cut_gap
                            state["cut_gap"] = cut_gap
                        elif _menu_hit == "gap_plus":
                            cut_gap = min(20, cut_gap + 2)
                            cut_gap_slider.value = cut_gap
                            state["cut_gap"] = cut_gap
                        menu_handled = True
                    elif state.get("shape_menu_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                        menu_handled = True
                    else:
                        shape_menu_key = None
                state["shape_menu_key"] = shape_menu_key
                state["shape_menu_anchor"] = shape_menu_anchor
                if menu_handled:
                    continue
                if btn_undo.hit(event.pos):
                    if do_undo():
                        selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
                    selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
                elif btn_redo.hit(event.pos):
                    if do_redo():
                        selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
                    selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
                elif btn_draw.hit(event.pos):
                    tool_mode = "draw"; draw_tool = "pen"; drawing = False; current_points = []; selected_strokes.clear(); selected_point = None; transform_drag = None
                elif btn_select.hit(event.pos):
                    _bezier_pen_commit_or_cancel()
                    tool_mode = "selection"; drawing = False; current_points = []; selected_point = None; drag_last = None; transform_drag = None; selection_submode = "transform"
                    curve_cut_mode = False
                elif any(r.collidepoint(event.pos) for r in state.get("draw_shape_rects", {}).values()):
                    _hit_key = next((k for k, r in state.get("draw_shape_rects", {}).items() if r.collidepoint(event.pos)), None)
                    if _hit_key is not None:
                        _mirror_align = {"mirror_h", "mirror_v", "align_left", "align_hcenter", "align_right", "align_top", "align_vmiddle", "align_bottom"}
                        _draw_keys = {k for k, _ in DRAW_SHAPES} | {k for k, _ in BOTTOM_TOOLS}
                        if tool_mode == "selection" and selection_submode == "transform" and _hit_key in _mirror_align and selected_strokes:
                            sel = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
                            if sel:
                                obb = combined_obb(strokes, sel)
                                bb = combined_bbox(strokes, sel)
                                if obb and bb:
                                    if pivot_pos is not None:
                                        cx, cy = pivot_pos
                                    else:
                                        cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
                                    push_undo()
                                    if _hit_key == "mirror_h":
                                        for si in sel:
                                            strokes[si] = mirror_stroke(strokes[si], cx, cy, "h")
                                    elif _hit_key == "mirror_v":
                                        for si in sel:
                                            strokes[si] = mirror_stroke(strokes[si], cx, cy, "v")
                                    else:
                                        tx1, ty1, tx2, ty2 = bb
                                        tcx, tcy = (tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0
                                        for si in sel:
                                            sbb = stroke_bbox(strokes[si])
                                            if not sbb:
                                                continue
                                            sx1, sy1, sx2, sy2 = sbb
                                            scx, scy = (sx1 + sx2) / 2.0, (sy1 + sy2) / 2.0
                                            dx = dy = 0.0
                                            if _hit_key == "align_left":
                                                dx = tx1 - sx1
                                            elif _hit_key == "align_hcenter":
                                                dx = tcx - scx
                                            elif _hit_key == "align_right":
                                                dx = tx2 - sx2
                                            elif _hit_key == "align_top":
                                                dy = ty1 - sy1
                                            elif _hit_key == "align_vmiddle":
                                                dy = tcy - scy
                                            elif _hit_key == "align_bottom":
                                                dy = ty2 - sy2
                                            if dx != 0.0 or dy != 0.0:
                                                strokes[si] = translate_stroke(strokes[si], dx, dy)
                            selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; pending_transform_toggle = None
                        elif tool_mode == "draw" or _hit_key in _draw_keys:
                            # Bottom toolbar: pick a shape or a drawing tool.
                            _new_tool = draw_tool
                            _new_shape = draw_shape
                            if _hit_key in ("eraser", "bucket", "cutter"):
                                _new_tool = _hit_key
                            elif _hit_key not in _mirror_align:
                                if _hit_key == "rect":
                                    _new_shape = rect_variant
                                elif _hit_key == "ellipse":
                                    _new_shape = ellipse_variant
                                else:
                                    _new_shape = _hit_key
                                _new_tool = "pen"
                            # Commit active Bezier path when leaving Bezier pen context.
                            if bezier_pen is not None and not (_new_tool == "pen" and _new_shape == "pen"):
                                _bezier_pen_commit_or_cancel()
                            draw_tool = _new_tool
                            draw_shape = _new_shape
                            tool_mode = "draw"
                            drawing = False
                            current_points = []
                            selected_strokes.clear(); selected_point = None; transform_drag = None
                        # else: unhandled bottom-bar action for this view; ignore

                elif event.pos[0] >= cfg.PANEL_X:
                    # Right panel interactions
                    if xform_field_focus is not None and tool_mode == "selection" and selection_submode == "transform":
                        _xform_all = ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                                      "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                                      "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                                      "xform_rm_rect", "xform_rp_rect")
                        if not any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) for k in _xform_all):
                            _commit_xform_field()
                    if btn_boost.hit(event.pos) and tool_mode == "draw":
                        boost_points = not boost_points
                        slider.max_v = BOOST_MAX_POINTS if boost_points else NORMAL_MAX_POINTS
                        if not boost_points:
                            max_points_per_curve = min(max_points_per_curve, NORMAL_MAX_POINTS)
                        slider.value = max_points_per_curve
                    elif tool_mode == "draw":
                        handled_draw_panel = False
                        if state.get("ref_load_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            path = pick_reference_image_path()
                            if path:
                                ref = load_reference_image(path)
                                if ref is not None:
                                    reference_image = ref
                                    reference_error = None
                                else:
                                    reference_error = "Could not load reference image (unsupported or corrupt file)."
                            handled_draw_panel = True
                        elif state.get("ref_vis_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            if reference_image:
                                reference_image["visible"] = not reference_image.get("visible", True)
                            handled_draw_panel = True
                        elif state.get("ref_clear_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            reference_image = None
                            reference_error = None
                            handled_draw_panel = True
                        elif reference_image and state.get("ref_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            bar = state["ref_opacity_rect"]
                            reference_image["opacity"] = clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
                            ref_opacity_drag = True
                            handled_draw_panel = True
                        if not handled_draw_panel:
                            if state.get("snap_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                snap_enabled = not snap_enabled
                            elif state.get("bucket_sv_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                bucket_pick(state["bucket_sv_rect"], event.pos, "sv")
                                bucket_picker_drag = "sv"
                            elif state.get("bucket_hue_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                bucket_pick(state["bucket_hue_rect"], event.pos, "hue")
                                bucket_picker_drag = "hue"
                            elif any(r.collidepoint(event.pos) for r in state.get("bucket_swatch_rects", [])):
                                for _i, _r in enumerate(state.get("bucket_swatch_rects", [])):
                                    if _r.collidepoint(event.pos) and _i < len(BUCKET_SWATCHES):
                                        set_bucket_color(BUCKET_SWATCHES[_i])
                                        break
                            elif any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                                     for k in ("draw_tool_prev_rect", "draw_tool_next_rect")):
                                _dtdir = -1 if state.get("draw_tool_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                                _dtools = ["pen", "eraser", "bucket", "cutter"]
                                _cur_dt = draw_tool if draw_tool in _dtools else "pen"
                                draw_tool = _dtools[(_dtools.index(_cur_dt) + _dtdir) % len(_dtools)]
                                if draw_tool != "pen" and bezier_pen is not None:
                                    _bezier_pen_commit_or_cancel()
                                if draw_tool == "cutter":
                                    cutting = False; cut_points = []
                            else:
                                picked_shape = False
                                for key, r in state.get("draw_shape_rects", {}).items():
                                    if r.collidepoint(event.pos):
                                        if bezier_pen is not None and not (draw_tool == "pen" and key == "pen"):
                                            _bezier_pen_commit_or_cancel()
                                        if key == "rect":
                                            draw_shape = rect_variant
                                        elif key == "ellipse":
                                            draw_shape = ellipse_variant
                                        else:
                                            draw_shape = key
                                        picked_shape = True
                                        break
                                if not picked_shape:
                                    if any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                                           for k in ("trace_algo_prev_rect", "trace_algo_next_rect")):
                                        _adir = -1 if state.get("trace_algo_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                                        _algos = [k for k, _ in TRACE_ALGORITHMS]
                                        _cur = trace_algorithm if trace_algorithm in _algos else _algos[0]
                                        trace_algorithm = _algos[(_algos.index(_cur) + _adir) % len(_algos)]
                    elif tool_mode == "selection" and any(
                        state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                        for k in ("nodes_mode_prev_rect", "nodes_mode_next_rect")
                    ):
                        _mdir = -1 if state.get("nodes_mode_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                        _modes = ["transform", "nodes", "curve"]
                        _cur = selection_submode if selection_submode in _modes else "transform"
                        selection_submode = _modes[(_modes.index(_cur) + _mdir) % len(_modes)]
                        selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; redrawing_curve = None
                        curve_cut_mode = False
                    elif tool_mode == "selection" and selection_submode == "transform" and selected_strokes and (
                        state.get("elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                    ):
                        push_undo()
                        sel = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
                        if sel:
                            sel_set_local = set(sel)
                            if state.get("elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                picked = [strokes[i] for i in sel]
                                remaining = [st for i, st in enumerate(strokes) if i not in sel_set_local]
                                strokes[:] = remaining + picked
                                selected_strokes = set(range(len(remaining), len(strokes)))
                            elif state.get("elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                picked = [strokes[i] for i in sel]
                                remaining = [st for i, st in enumerate(strokes) if i not in sel_set_local]
                                strokes[:] = picked + remaining
                                selected_strokes = set(range(len(picked)))
                            elif state.get("elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                for i in range(len(strokes) - 2, -1, -1):
                                    if i in selected_strokes and (i + 1) not in selected_strokes:
                                        strokes[i], strokes[i + 1] = strokes[i + 1], strokes[i]
                                        selected_strokes.discard(i); selected_strokes.add(i + 1)
                            elif state.get("elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                for i in range(1, len(strokes)):
                                    if i in selected_strokes and (i - 1) not in selected_strokes:
                                        strokes[i], strokes[i - 1] = strokes[i - 1], strokes[i]
                                        selected_strokes.discard(i); selected_strokes.add(i - 1)
                        selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; pending_transform_toggle = None
                    elif tool_mode == "selection" and selection_submode == "transform" and len(selected_strokes) >= 2 and (
                        state.get("bool_union_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("bool_intersect_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("bool_subtract_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("bool_exclude_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                    ):
                        sel = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
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
                                result = boolean_result([strokes[i] for i in sel], op=op)
                            except Exception:
                                result = None
                            if result:
                                result_segs, result_comps, result_corners = result
                                push_undo()
                                primary = strokes[sel[0]]
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
                                    del strokes[i]
                                strokes.append(new_st)
                                selected_strokes = {len(strokes) - 1}
                                selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; pending_transform_toggle = None
                    elif tool_mode == "selection" and selection_submode == "transform" and selected_strokes and (
                        state.get("mirror_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("mirror_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("align_left_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("align_hcenter_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("align_right_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("align_top_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("align_vmiddle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("align_bottom_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                    ):
                        sel = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
                        if sel:
                            obb = combined_obb(strokes, sel)
                            bb = combined_bbox(strokes, sel)
                            if obb and bb:
                                if pivot_pos is not None:
                                    cx, cy = pivot_pos
                                else:
                                    cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
                                push_undo()
                                if state.get("mirror_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                    for si in sel:
                                        strokes[si] = mirror_stroke(strokes[si], cx, cy, "h")
                                elif state.get("mirror_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                    for si in sel:
                                        strokes[si] = mirror_stroke(strokes[si], cx, cy, "v")
                                else:
                                    tx1, ty1, tx2, ty2 = bb
                                    tcx, tcy = (tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0
                                    for si in sel:
                                        sbb = stroke_bbox(strokes[si])
                                        if not sbb:
                                            continue
                                        sx1, sy1, sx2, sy2 = sbb
                                        scx, scy = (sx1 + sx2) / 2.0, (sy1 + sy2) / 2.0
                                        dx = dy = 0.0
                                        if state.get("align_left_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                            dx = tx1 - sx1
                                        elif state.get("align_hcenter_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                            dx = tcx - scx
                                        elif state.get("align_right_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                            dx = tx2 - sx2
                                        elif state.get("align_top_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                            dy = ty1 - sy1
                                        elif state.get("align_vmiddle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                            dy = tcy - scy
                                        elif state.get("align_bottom_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                            dy = ty2 - sy2
                                        if dx != 0.0 or dy != 0.0:
                                            strokes[si] = translate_stroke(strokes[si], dx, dy)
                        selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; pending_transform_toggle = None
                    elif tool_mode == "selection" and selection_submode == "transform" and len(selected_strokes) >= 3 and (
                        state.get("distribute_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
                        state.get("distribute_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                    ):
                        sel = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
                        boxes = [stroke_bbox(strokes[si]) for si in sel]
                        if all(boxes) and len(boxes) >= 3:
                            horizontal = state.get("distribute_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                            offsets = distribute_offsets(boxes, "h" if horizontal else "v")
                            push_undo()
                            for si, (dx, dy) in zip(sel, offsets):
                                if dx or dy:
                                    strokes[si] = translate_stroke(strokes[si], dx, dy)
                        selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None
                    elif tool_mode == "selection" and selection_submode == "transform" and selected_strokes and (
                        any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                            for k in ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                                      "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                                      "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                                      "xform_rm_rect", "xform_rp_rect"))
                    ):
                        # Numeric transform: focus/seed value field, or nudge via +/-.
                        fields = ("x", "y", "w", "h", "r")
                        handled_xform = False
                        for fk in fields:
                            if state.get(f"xform_{fk}_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                cur = _xform_current_value(fk)
                                if cur is not None:
                                    if fk == "r":
                                        seed = "0"
                                    else:
                                        seed = f"{cur:.3f}".rstrip("0").rstrip(".") or "0"
                                    xform_field_focus = fk
                                    xform_field_buffer = seed
                                    state["xform_field_focus"] = fk
                                    state["xform_field_buffer"] = seed
                                handled_xform = True
                                break
                            if state.get(f"xform_{fk}m_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
                                _apply_xform_field(fk, -step, relative=True)
                                xform_field_focus = None
                                xform_field_buffer = ""
                                state["xform_field_focus"] = None
                                state["xform_field_buffer"] = ""
                                handled_xform = True
                                break
                            if state.get(f"xform_{fk}p_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
                                _apply_xform_field(fk, step, relative=True)
                                xform_field_focus = None
                                xform_field_buffer = ""
                                state["xform_field_focus"] = None
                                state["xform_field_buffer"] = ""
                                handled_xform = True
                                break
                        if handled_xform:
                            selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; pending_transform_toggle = None
                    elif tool_mode == "selection" and selection_submode == "transform" and selected_strokes and any(
                        state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                        for k in ("width_profile_prev_rect", "width_profile_next_rect")
                    ):
                        wk = "width_profile_prev_rect" if state.get("width_profile_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else "width_profile_next_rect"
                        step_dir = -1 if wk == "width_profile_prev_rect" else 1
                        profiles = list(WIDTH_PROFILES) if 'WIDTH_PROFILES' in globals() else ["uniform", "taper_in", "taper_out", "taper_both", "pressure"]
                        if 'apply_width_profile' in globals():
                            push_undo()
                            for si in sorted(selected_strokes):
                                if 0 <= si < len(strokes) and isinstance(strokes[si], dict):
                                    cur = strokes[si].get("width_profile")
                                    if cur not in profiles:
                                        cur = "uniform"
                                    ni = (profiles.index(cur) + step_dir) % len(profiles)
                                    strokes[si] = apply_width_profile(strokes[si], profiles[ni])
                    elif tool_mode == "selection" and selection_submode == "transform" and selected_strokes and any(
                        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                        for k in ("marker_start_rect", "marker_end_rect")
                    ):
                        mk_key = "marker_start_rect" if state.get("marker_start_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else "marker_end_rect"
                        end = "start" if mk_key == "marker_start_rect" else "end"
                        marker_dropdown = None if marker_dropdown == end else end
                        state["marker_dropdown"] = marker_dropdown
                    elif tool_mode == "selection" and selection_submode == "transform" and selected_strokes and any(
                        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                        for k in ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
                                  "dash_prev_rect", "dash_next_rect")
                    ):
                        skey = next(k for k in ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
                                                "dash_prev_rect", "dash_next_rect")
                                    if state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
                        if skey.startswith("cap_"):
                            field, opts = "line_cap", ["butt", "round", "square"]
                        elif skey.startswith("join_"):
                            field, opts = "line_join", ["miter", "round", "bevel"]
                        else:
                            field, opts = "dash", [None, "dashed", "dotted"]
                        step_dir = -1 if skey.endswith("_prev_rect") else 1
                        push_undo()
                        for si in sorted(selected_strokes):
                            if 0 <= si < len(strokes) and isinstance(strokes[si], dict):
                                updated = dict(strokes[si])
                                cur = updated.get(field)
                                if field == "dash" and cur not in opts:
                                    cur = None
                                if cur not in opts:
                                    cur = opts[0]
                                idx = (opts.index(cur) + step_dir) % len(opts)
                                updated[field] = opts[idx]
                                strokes[si] = updated
                    elif tool_mode == "selection" and selected_strokes and state.get(
                        "text_edit_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        _ti = next(iter(sorted(selected_strokes)), None)
                        if _ti is not None and 0 <= _ti < len(strokes) and \
                                isinstance(strokes[_ti], dict) and strokes[_ti].get("is_text"):
                            _ts = strokes[_ti]
                            # Re-open the text editor seeded with existing content.
                            tool_mode = "draw"; draw_tool = "text"
                            drawing = False; current_points = []
                            text_family = _ts.get("font_family", text_family)
                            text_size = float(_ts.get("font_size", text_size))
                            text_entry = {"x": float(_ts.get("text_x", 0.0)),
                                          "y": float(_ts.get("text_y", 0.0)),
                                          "text": str(_ts.get("text_content", "")),
                                          "family": text_family, "size": text_size,
                                          "edit_index": _ti}
                            selected_strokes.clear()
                    elif tool_mode == "selection" and selected_strokes and state.get(
                        "text_font_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        _ti = next(iter(sorted(selected_strokes)), None)
                        if _ti is not None and 0 <= _ti < len(strokes) and \
                                isinstance(strokes[_ti], dict) and strokes[_ti].get("is_text"):
                            push_undo()
                            _fams = tuple(FONT_FAMILIES)
                            _cur = strokes[_ti].get("font_family", text_family)
                            _next = _fams[(_fams.index(_cur) + 1) % len(_fams)] if _cur in _fams else _fams[0]
                            strokes[_ti] = update_text_stroke(strokes[_ti], font_family=_next)
                            text_family = _next
                    elif tool_mode == "selection" and selected_strokes and any(
                        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                        for k in ("text_size_minus_rect", "text_size_plus_rect")):
                        _ti = next(iter(sorted(selected_strokes)), None)
                        _key = "text_size_plus_rect" if state.get(
                            "text_size_plus_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) \
                            else "text_size_minus_rect"
                        if _ti is not None and 0 <= _ti < len(strokes) and \
                                isinstance(strokes[_ti], dict) and strokes[_ti].get("is_text"):
                            push_undo()
                            _sz = float(strokes[_ti].get("font_size", 36.0))
                            _sz = max(4.0, min(400.0, _sz + (2.0 if _key == "text_size_plus_rect" else -2.0)))
                            strokes[_ti] = update_text_stroke(strokes[_ti], font_size=_sz)
                            text_size = _sz
                    elif tool_mode == "selection" and state.get("text_on_path_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        sel = [i for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                        if len(sel) == 2:
                            a, b = strokes[sel[0]], strokes[sel[1]]
                            text_i = path_i = None
                            if isinstance(a, dict) and a.get("is_text") and not (isinstance(b, dict) and b.get("is_text")):
                                text_i, path_i = sel[0], sel[1]
                            elif isinstance(b, dict) and b.get("is_text") and not (isinstance(a, dict) and a.get("is_text")):
                                text_i, path_i = sel[1], sel[0]
                            if text_i is not None and path_i is not None:
                                try:
                                    from models.strokes import segs_of as _segs_of_tp
                                    psegs = list(_segs_of_tp(strokes[path_i]) or [])
                                except Exception:
                                    psegs = list((strokes[path_i] or {}).get("segs") or [])
                                if psegs:
                                    try:
                                        from models.text import set_text_path as _set_text_path
                                        push_undo()
                                        strokes[text_i] = _set_text_path(strokes[text_i], psegs, 0.0)
                                        selected_strokes = {text_i}
                                        selected_point = None; selected_curve = None; selected_curves.clear()
                                    except Exception:
                                        pass
                    elif tool_mode == "selection" and state.get("text_off_path_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        if len(selected_strokes) == 1:
                            _ti = next(iter(selected_strokes))
                            if 0 <= _ti < len(strokes) and isinstance(strokes[_ti], dict) and strokes[_ti].get("is_text") and strokes[_ti].get("text_path"):
                                try:
                                    from models.text import clear_text_path as _clear_text_path
                                    push_undo()
                                    strokes[_ti] = _clear_text_path(strokes[_ti])
                                except Exception:
                                    pass
                    elif tool_mode == "selection" and selected_strokes and state.get(
                        "obj_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        bar = state["obj_opacity_rect"]
                        opacity = clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
                        push_undo()
                        for si in sorted(selected_strokes):
                            if 0 <= si < len(strokes) and isinstance(strokes[si], dict):
                                strokes[si] = set_appearance(strokes[si], opacity=opacity)
                        obj_opacity_drag = True
                        state["obj_opacity_drag"] = True
                    elif tool_mode == "selection" and selected_strokes and any(
                        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                        for k in ("shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")
                    ):
                        appear_keys = ("shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")
                        appear_key = next(k for k in appear_keys
                                          if state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
                        push_undo()
                        for si in sorted(selected_strokes):
                            if not (0 <= si < len(strokes)) or not isinstance(strokes[si], dict):
                                continue
                            app = get_appearance(strokes[si])
                            if appear_key == "shadow_toggle_rect":
                                shadow = app["shadow"] if app["shadow"] is not None else {
                                    "dx": 6.0, "dy": 6.0, "blur": 6.0,
                                    "opacity": 0.35, "color": (0.0, 0.0, 0.0, 1.0)}
                                strokes[si] = set_appearance(strokes[si], shadow=shadow if app["shadow"] is None else None)
                            else:
                                shadow = app["shadow"]
                                if shadow is None:
                                    shadow = {"dx": 6.0, "dy": 6.0, "blur": 6.0,
                                              "opacity": 0.35, "color": (0.0, 0.0, 0.0, 1.0)}
                                step = -2.0 if appear_key == "shadow_blur_minus_rect" else 2.0
                                shadow = dict(shadow)
                                shadow["blur"] = max(0.0, min(64.0, float(shadow.get("blur", 4.0)) + step))
                                strokes[si] = set_appearance(strokes[si], shadow=shadow)
                    elif tool_mode == "selection" and selection_submode == "nodes" and any(
                        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                        for k in ("path_close_rect", "path_reverse_rect", "path_add_rect",
                                  "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                                  "path_expand_rect")
                    ):
                        path_keys = ("path_close_rect", "path_reverse_rect", "path_add_rect",
                                     "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                                     "path_expand_rect")
                        path_key = next(k for k in path_keys
                                        if state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
                        sel_idx = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
                        if sel_idx:
                            si = sel_idx[0]
                            st = strokes[si]
                            seg_i, pname = selected_point if selected_point else (0, "p0")
                            if pname not in ("p0", "p3"):
                                pname = "p0" if pname == "c1" else "p3"
                            seg_i = max(0, min(int(seg_i), len(segs_of(st)) - 1))
                            push_undo()
                            if path_key == "path_close_rect":
                                strokes[si] = set_path_closed(st, not _is_closed_segs(segs_of(st)))
                            elif path_key == "path_reverse_rect":
                                strokes[si] = reverse_stroke(st)
                            elif path_key == "path_add_rect":
                                strokes[si] = add_anchor_at(st, seg_i, 0.5)
                                selected_point = (seg_i, "p0")
                            elif path_key == "path_delete_rect":
                                strokes[si] = delete_anchor(st, seg_i, pname)
                                selected_point = None
                            elif path_key == "path_smooth_rect":
                                strokes[si] = set_anchor_smooth(st, seg_i, pname, True)
                            elif path_key == "path_expand_rect":
                                expanded = expand_stroke_outline(st)
                                if expanded is not None:
                                    strokes[si] = expanded
                                else:
                                    # Nothing to expand (zero-width path): undo the push.
                                    strokes[si] = st
                                    if undo_stack:
                                        undo_stack.pop()
                                selected_point = None
                            else:
                                strokes[si] = set_anchor_smooth(st, seg_i, pname, False)
                            transform_drag = None; drag_last = None
                    elif tool_mode == "selection" and state.get("eyedropper_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        eyedropper_pick = not eyedropper_pick
                        state["eyedropper_pick"] = eyedropper_pick
                        cutting = False; cut_points = []
                    elif tool_mode == "selection" and selection_submode == "curve" and state.get("curve_join_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        if len(selected_curves) >= 2:
                            by_stroke = {}
                            for si, ci in list(selected_curves):
                                by_stroke.setdefault(si, set()).add(int(ci))
                            results = {}
                            for si, idxs in by_stroke.items():
                                if 0 <= si < len(strokes):
                                    new_st, index_map = join_components_in_stroke(strokes[si], idxs)
                                    if index_map is not None:
                                        results[si] = (new_st, index_map, idxs)
                            if results:
                                push_undo()
                                new_selected_curves = set()
                                for si, idxs in by_stroke.items():
                                    if si in results:
                                        new_st, index_map, _idxs2 = results[si]
                                        strokes[si] = new_st
                                        for ci in idxs:
                                            new_selected_curves.add((si, int(index_map.get(ci, ci))))
                                    elif 0 <= si < len(strokes):
                                        for ci in idxs:
                                            new_selected_curves.add((si, int(ci)))
                                selected_curves = new_selected_curves
                                selected_curve = next(iter(selected_curves), None)
                                selected_strokes = {si for si, _ in selected_curves}
                        selected_point = None; transform_drag = None; drag_last = None
                        eyedropper_pick = False
                    elif tool_mode == "selection" and selection_submode == "curve" and state.get("curve_cut_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        curve_cut_mode = not curve_cut_mode
                        state["curve_cut_mode"] = curve_cut_mode
                        cutting = False; cut_points = []
                        selected_point = None; transform_drag = None; drag_last = None
                        eyedropper_pick = False
                    elif tool_mode == "selection" and selection_submode == "curve" and state.get("curve_redraw_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        if selected_curve and selected_curve[0] in selected_strokes:
                            si, comp_i = selected_curve
                            fixed_start = fixed_end = None
                            if 0 <= si < len(strokes):
                                segs = segs_of(strokes[si])
                                ranges = _component_ranges(strokes[si])
                                if 0 <= comp_i < len(ranges):
                                    s0, s1 = ranges[comp_i]
                                    if s1 > s0 and s1 <= len(segs):
                                        fixed_start = tuple(segs[s0][0])
                                        fixed_end = tuple(segs[s1 - 1][3])
                            redrawing_curve = {
                                "stroke_idx": si, "comp_idx": comp_i, "points": [],
                                "started": False, "fixed_start": fixed_start, "fixed_end": fixed_end,
                            }
                            selected_point = None; transform_drag = None; drag_last = None
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("wave_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                # append a new wave style to the stack and edit it
                                n = len(_get_distortion_styles(comps[comp_i]))
                                w = default_wave_params()
                                w["enabled"] = True
                                _set_distortion_style(comps[comp_i], w, n)
                                strokes[si]["components"] = comps
                                state["wave_active_index"] = n
                                state["wave_custom_finished"] = False
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                        state["wave_custom_draw"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("displacement_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                n = len(_get_distortion_styles(comps[comp_i]))
                                d = default_displacement_params()
                                d["enabled"] = True
                                _set_distortion_style(comps[comp_i], d, n)
                                strokes[si]["components"] = comps
                                state["wave_active_index"] = n
                                state["wave_custom_finished"] = False
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                        state["wave_custom_draw"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("repeat_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                n = len(_get_distortion_styles(comps[comp_i]))
                                r = default_repeat_params()
                                r["enabled"] = True
                                _set_distortion_style(comps[comp_i], r, n)
                                strokes[si]["components"] = comps
                                state["wave_active_index"] = n
                                state["wave_custom_finished"] = False
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                        state["wave_custom_draw"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("thickness_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                n = len(_get_distortion_styles(comps[comp_i]))
                                th = default_thickness_params()
                                th["enabled"] = True
                                _set_distortion_style(comps[comp_i], th, n)
                                strokes[si]["components"] = comps
                                state["wave_active_index"] = n
                                state["wave_custom_finished"] = False
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                        state["wave_custom_draw"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("wave_bake_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            baked = bake_component_distortion(strokes[si], comp_i)
                            if baked is not strokes[si]:
                                push_undo()
                                strokes[si] = baked
                                comps_b = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps_b):
                                    n = len(_get_distortion_styles(comps_b[comp_i]))
                                    state["wave_active_index"] = (max(0, n - 1) if n else 0)
                                else:
                                    state["wave_active_index"] = 0
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                        state["wave_custom_draw"] = False
                        state["wave_custom_finished"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("wave_remove_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                wi = int(state.get("wave_active_index", 0) or 0)
                                _remove_distortion_style(comps[comp_i], wi)
                                strokes[si]["components"] = comps
                                n = len(_get_distortion_styles(comps[comp_i]))
                                state["wave_active_index"] = (max(0, min(wi, n - 1)) if n else 0)
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                        state["wave_custom_draw"] = False
                        state["wave_custom_finished"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("wave_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                wi = int(state.get("wave_active_index", 0) or 0)
                                w = _get_distortion_style(comps[comp_i], wi)
                                w["enabled"] = not bool(w.get("enabled"))
                                _set_distortion_style(comps[comp_i], w, wi)
                                strokes[si]["components"] = comps
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and any(_rr.collidepoint(event.pos) for _ri, _rr in (state.get("wave_row_rects") or [])):
                        # click a stack row to make that wave the active/edited one
                        for _ri, _rr in (state.get("wave_row_rects") or []):
                            if _rr.collidepoint(event.pos):
                                if _ri != int(state.get("wave_active_index", 0) or 0):
                                    state["wave_active_index"] = _ri
                                    state["wave_formula_focus"] = False
                                    state["wave_custom_draw"] = False
                                    state["wave_custom_finished"] = False
                                    wave_formula_focus = False
                                break
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes:
                        _w_hit = False
                        wi = int(state.get("wave_active_index", 0) or 0)
                        # displacement profile selector (flat/custom)
                        for key, r in (state.get("displacement_profile_rects") or {}).items():
                            if r.collidepoint(event.pos):
                                si, comp_i = selected_curve
                                if 0 <= si < len(strokes):
                                    comps = _stroke_components(strokes[si])
                                    if 0 <= comp_i < len(comps):
                                        comps[comp_i] = dict(comps[comp_i])
                                        w = _get_distortion_style(comps[comp_i], wi)
                                        if w.get("type") == "displacement":
                                            w["profile"] = key
                                            _set_distortion_style(comps[comp_i], w, wi)
                                            strokes[si]["components"] = comps
                                            if key == "custom":
                                                state["wave_custom_draw"] = True
                                                state["wave_custom_finished"] = False
                                                state["wave_formula_focus"] = False
                                                wave_formula_focus = False
                                            else:
                                                state["wave_custom_draw"] = False
                                                state["wave_custom_finished"] = False
                                _w_hit = True
                                break
                        # displacement "apply to" toggles (X/Y/Rotate/Length), combinable
                        if not _w_hit:
                            for key, r in (state.get("displacement_affect_rects") or {}).items():
                                if r.collidepoint(event.pos):
                                    si, comp_i = selected_curve
                                    if 0 <= si < len(strokes):
                                        comps = _stroke_components(strokes[si])
                                        if 0 <= comp_i < len(comps):
                                            comps[comp_i] = dict(comps[comp_i])
                                            w = _get_distortion_style(comps[comp_i], wi)
                                            if w.get("type") == "displacement":
                                                w[key] = not bool(w.get(key, True))
                                                _set_distortion_style(comps[comp_i], w, wi)
                                                strokes[si]["components"] = comps
                                    _w_hit = True
                                    break
                        # formula input focus
                        f_rect = state.get("wave_formula_rect", pygame.Rect(0,0,0,0))
                        if (not _w_hit) and f_rect.collidepoint(event.pos) and f_rect.w > 0 and f_rect.h > 0:
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    wchk = _get_distortion_style(comps[comp_i], wi)
                                    if wchk.get("type") == "wave":
                                        wave_formula_focus = True
                                        state["wave_formula_focus"] = True
                                        _w_hit = True
                        # Reverse direction toggle for the active distortion style
                        rev_r = state.get("wave_reverse_rect", pygame.Rect(0, 0, 0, 0))
                        if (not _w_hit) and rev_r.w > 0 and rev_r.h > 0 and rev_r.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_distortion_style(comps[comp_i], wi)
                                    w["reverse"] = not bool(w.get("reverse"))
                                    _set_distortion_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                            _w_hit = True
                        # Clamp: apply the style on only one side or the other
                        clamp_r = state.get("wave_clamp_rect", pygame.Rect(0, 0, 0, 0))
                        if (not _w_hit) and clamp_r.w > 0 and clamp_r.h > 0 and clamp_r.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_distortion_style(comps[comp_i], wi)
                                    mode = str(w.get("clamp", "none") or "none").lower()
                                    cycle = ["none", "positive", "negative"]
                                    try:
                                        idx = cycle.index(mode)
                                    except ValueError:
                                        idx = 0
                                    w["clamp"] = cycle[(idx + 1) % len(cycle)]
                                    _set_distortion_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                            _w_hit = True
                        # Smooth button
                        smooth_r = state.get("wave_smooth_rect", pygame.Rect(0, 0, 0, 0))
                        if (not _w_hit) and smooth_r.w > 0 and smooth_r.h > 0 and smooth_r.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_distortion_style(comps[comp_i], wi)
                                    if w.get("type") == "repeat":
                                        w["repeat_points"] = _smooth_repeat_points(w.get("repeat_points"))
                                    elif w.get("type") == "thickness":
                                        w["thickness_points"] = _smooth_repeat_points(w.get("thickness_points"))
                                    else:
                                        w["custom_points"] = _custom_smooth_samples(w.get("custom_points"))
                                        state["wave_custom_finished"] = False
                                    _set_distortion_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                            _w_hit = True
                        # Done button (finish custom draw)
                        done_r = state.get("wave_done_rect", pygame.Rect(0, 0, 0, 0))
                        if (not _w_hit) and done_r.w > 0 and done_r.h > 0 and done_r.collidepoint(event.pos):
                            state["wave_custom_draw"] = False
                            state["wave_custom_finished"] = True
                            _w_hit = True
                        # Clear button
                        clear_r = state.get("wave_clear_rect", pygame.Rect(0, 0, 0, 0))
                        if (not _w_hit) and clear_r.w > 0 and clear_r.h > 0 and clear_r.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_distortion_style(comps[comp_i], wi)
                                    if w.get("type") == "repeat":
                                        w["repeat_points"] = []
                                    elif w.get("type") == "thickness":
                                        w["thickness_points"] = []
                                    else:
                                        w["custom_points"] = []
                                    _set_distortion_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                                    state["wave_custom_finished"] = False
                            _w_hit = True
                        # Pick curve as repeat pattern
                        pick_r = state.get("repeat_pick_curve_rect", pygame.Rect(0, 0, 0, 0))
                        if (not _w_hit) and pick_r.w > 0 and pick_r.h > 0 and pick_r.collidepoint(event.pos):
                            if state.get("repeat_pick_mode"):
                                state["repeat_pick_mode"] = False
                                state["repeat_pick_target"] = None
                                repeat_pick_mode = False
                                repeat_pick_target = None
                            else:
                                state["repeat_pick_mode"] = True
                                state["repeat_pick_target"] = (si, comp_i, int(wi))
                                repeat_pick_mode = True
                                repeat_pick_target = (si, comp_i, int(wi))
                            _w_hit = True
                        # custom wave draw mode: pressing inside the box starts a paint stroke
                        box = state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
                        if (not _w_hit) and box.w > 0 and box.h > 0 and box.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_distortion_style(comps[comp_i], wi)
                                    # spatial displacement uses procedural noise (no custom draw box)
                                    if w.get("type") in ("wave", "repeat", "thickness"):
                                        state["wave_custom_finished"] = False
                                        state["wave_custom_draw"] = True
                                        state["wave_formula_focus"] = False
                                        wave_formula_focus = False
                                        wave_custom_drag = _custom_wave_paint(w, box, event.pos, None)
                                        state["wave_custom_drag"] = wave_custom_drag
                                        _set_distortion_style(comps[comp_i], w, wi)
                                        strokes[si]["components"] = comps
                            _w_hit = True
                        if not _w_hit:
                            for key, (r, lo, hi) in (state.get("wave_slider_rects") or {}).items():
                                if r.collidepoint(event.pos):
                                    si, comp_i = selected_curve
                                    if 0 <= si < len(strokes):
                                        comps = _stroke_components(strokes[si])
                                        if 0 <= comp_i < len(comps):
                                            comps[comp_i] = dict(comps[comp_i])
                                            w = _get_distortion_style(comps[comp_i], wi)
                                            t = (event.pos[0] - r.x) / max(1, r.w - 1)
                                            val = lo + clamp(t, 0.0, 1.0) * (hi - lo)
                                            if key in ("amplitude", "noise", "phase", "seed", "amount", "location", "handle_rotate", "handle_length"):
                                                val = float(int(round(val)))
                                            elif key in ("frequency", "noise_scale"):
                                                val = float(val)
                                            else:
                                                val = float(val)
                                            w[key] = val
                                            _set_distortion_style(comps[comp_i], w, wi)
                                            strokes[si]["components"] = comps
                                            wave_slider_drag = {"key": key, "rect": r, "lo": lo, "hi": hi, "si": si, "comp_i": comp_i, "wi": wi}
                                    _w_hit = True
                                    break
                        if not _w_hit and any(
                            state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                            for k in ("wave_shape_prev_rect", "wave_shape_next_rect")
                        ):
                            _wsdir = -1 if state.get("wave_shape_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                            _wshapes = [k for k, _ in WAVE_SHAPE_LABELS]
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_distortion_style(comps[comp_i], wi)
                                    if w.get("type") == "wave":
                                        _cur_ws = w.get("shape", "sine")
                                        if _cur_ws not in _wshapes:
                                            _cur_ws = _wshapes[0]
                                        _nws = _wshapes[(_wshapes.index(_cur_ws) + _wsdir) % len(_wshapes)]
                                        w["shape"] = _nws
                                        w["enabled"] = True
                                        if _nws == "custom" and "custom_points" not in w:
                                            w["custom_points"] = []
                                        _set_distortion_style(comps[comp_i], w, wi)
                                        strokes[si]["components"] = comps
                                        if _nws == "custom":
                                            state["wave_custom_draw"] = True
                                            state["wave_custom_finished"] = False
                                            state["wave_formula_focus"] = False
                                            wave_formula_focus = False
                                        else:
                                            state["wave_custom_draw"] = False
                                            state["wave_custom_finished"] = False
                            _w_hit = True
                        if not _w_hit and selected_strokes and (selection_submode == "transform" or (selection_submode == "curve" and selected_curve)):
                            # Modern color picker interactions
                            comp_style_target = None
                            if selection_submode == "curve" and selected_curve and len(selected_strokes) == 1 and selected_curve[0] in selected_strokes:
                                comp_style_target = selected_curve
                            if comp_style_target is not None:
                                color_target = "stroke"
                                state["color_target"] = "stroke"
                            if not (selection_submode == "curve" and comp_style_target is None):
                                sel_list = sorted(selected_strokes)
                                primary_i = sel_list[0]
                                primary_obj = strokes[primary_i] if 0 <= primary_i < len(strokes) else None
                                def _set_comp_stroke_color(si, ci, rgb, alpha):
                                    comps = _stroke_components(strokes[si])
                                    if 0 <= ci < len(comps):
                                        comps[ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
                                        strokes[si]["components"] = comps
                                if primary_obj is not None and state["tab_stroke_rect"].collidepoint(event.pos):
                                    color_target = "stroke"
                                    state["color_target"] = color_target
                                    if comp_style_target is not None:
                                        sc, _sw = _effective_component_style(primary_obj, comp_style_target[1])
                                        sc = sc or (0.1, 0.1, 0.15)
                                    else:
                                        sc = primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
                                    picker_h, picker_s, picker_v = rgb_to_hsv(*sc)
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state["tab_fill_rect"].collidepoint(event.pos) and comp_style_target is None:
                                    color_target = "fill"
                                    state["color_target"] = color_target
                                    fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) and primary_obj.get("fill_gradient", {}).get("type") in ("linear","radial") else None)
                                    if fg is not None:
                                        stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                        fc = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                    else:
                                        fc = primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
                                    picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and color_target == "fill" and comp_style_target is None:
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            strokes[si]["fill_color"] = None
                                            strokes[si]["fill_gradient"] = None
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and any(
                                    state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                                    for k in ("fill_type_prev_rect", "fill_type_next_rect")
                                ):
                                    _fdir = -1 if state.get("fill_type_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                                    _fmodes = ["solid", "linear", "radial", "conic", "spiral", "diamond", "square", "mesh", "pattern"]
                                    _pfg_cur = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                    _ppat_cur = get_fill_pattern(primary_obj) if 'get_fill_pattern' in globals() else primary_obj.get("fill_pattern")
                                    if _ppat_cur is not None:
                                        _cur_fill_mode = "pattern"
                                    elif _pfg_cur is not None:
                                        _cur_fill_mode = str(_pfg_cur.get("type", "linear"))
                                    elif primary_obj.get("fill_color") is not None:
                                        _cur_fill_mode = "solid"
                                    else:
                                        _cur_fill_mode = "solid"
                                    if _cur_fill_mode not in _fmodes:
                                        _cur_fill_mode = "solid"
                                    ftype = _fmodes[(_fmodes.index(_cur_fill_mode) + _fdir) % len(_fmodes)]
                                    if ftype is not None:
                                        cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                        grad_types = ("linear", "radial", "conic", "spiral", "diamond", "square", "mesh")
                                        for si in sel_list:
                                            if 0 <= si < len(strokes):
                                                st = strokes[si]
                                                fg = get_fill_gradient(st) if 'get_fill_gradient' in globals() else (st.get("fill_gradient") if isinstance(st.get("fill_gradient"), dict) else None)
                                                if ftype == "solid":
                                                    if fg is not None:
                                                        si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else max(0, min(cur_stop_i, max(0, len(fg.get("stops") or []) - 1)))
                                                        col0 = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in globals() else (0.0, 0.0, 0.0, 1.0)
                                                    else:
                                                        col0 = st.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                                                    st["fill_color"] = tuple(color_rgba(col0, (0.45, 0.72, 1.0, 1.0)))
                                                    st["fill_gradient"] = None
                                                elif ftype in grad_types:
                                                    if fg is not None and str(fg.get("type")) in grad_types:
                                                        if ftype == "mesh" or str(fg.get("type")) == "mesh":
                                                            base = st.get("fill_color")
                                                            if base is None and isinstance(fg.get("stops"), list) and fg.get("stops"):
                                                                try:
                                                                    base = get_gradient_stop_color(fg, 0) if 'get_gradient_stop_color' in globals() else (fg.get("stops")[0] or {}).get("color")
                                                                except Exception:
                                                                    base = None
                                                            base = color_rgba(base or (0.2, 0.4, 0.9, 1.0), (0.2, 0.4, 0.9, 1.0))
                                                            c1m = (1.0, 1.0, 1.0, float(base[3]))
                                                            if ftype == "mesh" and 'default_mesh_gradient' in globals():
                                                                st["fill_gradient"] = default_mesh_gradient(base, c1m)
                                                            elif ftype == "linear" and 'default_linear_gradient' in globals():
                                                                st["fill_gradient"] = default_linear_gradient(base, c1m, 0.0)
                                                            elif ftype == "radial" and 'default_radial_gradient' in globals():
                                                                st["fill_gradient"] = default_radial_gradient((1.0, 1.0, 1.0, float(base[3])), base)
                                                            elif 'default_shaped_gradient' in globals():
                                                                st["fill_gradient"] = default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(base[3])), base)
                                                            else:
                                                                st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(base)}, {"pos": 1.0, "color": list(c1m)}]}
                                                        else:
                                                            ng = dict(fg)
                                                            ng["type"] = ftype
                                                            if ftype == "linear" and "angle" not in ng:
                                                                ng["angle"] = 0.0
                                                            if ftype in ("radial", "conic", "spiral", "diamond", "square"):
                                                                if "center" not in ng:
                                                                    ng["center"] = [0.5, 0.5]
                                                                if "radii" not in ng:
                                                                    ng["radii"] = [0.5, 0.5]
                                                                if "angle" not in ng:
                                                                    ng["angle"] = 0.0
                                                                if ftype == "spiral" and "turns" not in ng:
                                                                    ng["turns"] = 2.0
                                                            if 'normalize_gradient' in globals():
                                                                try:
                                                                    ng = normalize_gradient(ng)
                                                                except Exception:
                                                                    pass
                                                            st["fill_gradient"] = ng
                                                    else:
                                                        base = st.get("fill_color") or (0.2, 0.4, 0.9, 1.0)
                                                        c0 = color_rgba(base, (0.2, 0.4, 0.9, 1.0))
                                                        c1 = (1.0, 1.0, 1.0, float(c0[3]))
                                                        if ftype == "mesh" and 'default_mesh_gradient' in globals():
                                                            st["fill_gradient"] = default_mesh_gradient(c0, c1)
                                                        elif ftype == "linear" and 'default_linear_gradient' in globals():
                                                            st["fill_gradient"] = default_linear_gradient(c0, c1, 0.0)
                                                        elif ftype == "radial" and 'default_radial_gradient' in globals():
                                                            st["fill_gradient"] = default_radial_gradient((1.0, 1.0, 1.0, float(c0[3])), c0)
                                                        elif 'default_shaped_gradient' in globals():
                                                            st["fill_gradient"] = default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(c0[3])), c0)
                                                        else:
                                                            st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(c0)}, {"pos": 1.0, "color": list(c1)}]}
                                                    st["fill_color"] = None
                                                elif ftype == "pattern":
                                                    pat = get_fill_pattern(st) if 'get_fill_pattern' in globals() else None
                                                    if pat is None and 'new_pattern' in globals():
                                                        pat = new_pattern("stripes")
                                                    st["fill_pattern"] = pat
                                                    st["fill_color"] = None
                                                    st["fill_gradient"] = None
                                        pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                        if pfg is not None:
                                            state["fill_gradient_stop"] = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                                            fc = get_gradient_stop_color(pfg, int(state.get("fill_gradient_stop", 0) or 0)) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                            picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                        elif ftype == "solid":
                                            fc = primary_obj.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                                            picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                            state["fill_gradient_stop"] = 0
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and state.get("pattern_type_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            pat = get_fill_pattern(strokes[si]) if 'get_fill_pattern' in globals() else None
                                            if pat is not None and 'cycle_pattern_type' in globals():
                                                strokes[si]["fill_pattern"] = cycle_pattern_type(pat)
                                            elif pat is None and 'new_pattern' in globals():
                                                strokes[si]["fill_pattern"] = new_pattern("stripes")
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and state.get("pattern_size_minus_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            pat = get_fill_pattern(strokes[si]) if 'get_fill_pattern' in globals() else None
                                            if pat is not None:
                                                pat = dict(pat)
                                                pat["size"] = max(2.0, float(pat.get("size", 14.0)) - 2.0)
                                                strokes[si]["fill_pattern"] = pat
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and state.get("pattern_size_plus_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            pat = get_fill_pattern(strokes[si]) if 'get_fill_pattern' in globals() else None
                                            if pat is not None:
                                                pat = dict(pat)
                                                pat["size"] = min(120.0, float(pat.get("size", 14.0)) + 2.0)
                                                strokes[si]["fill_pattern"] = pat
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and state.get("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                    cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                            if fg is not None and 'add_gradient_stop' in globals():
                                                si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                                ng, ni = add_gradient_stop(fg, si_clamped)
                                                strokes[si]["fill_gradient"] = ng
                                                strokes[si]["fill_color"] = None
                                    pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                    if pfg is not None:
                                        si_clamped = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                        ni = min(si_clamped + 1, max(0, len(pfg.get("stops") or []) - 1))
                                        state["fill_gradient_stop"] = ni
                                        fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                        picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and state.get("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                    cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                            if fg is not None and 'remove_gradient_stop' in globals():
                                                si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                                ng, ni = remove_gradient_stop(fg, si_clamped)
                                                strokes[si]["fill_gradient"] = ng
                                                strokes[si]["fill_color"] = None
                                    pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                    if pfg is not None:
                                        ni = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                                        state["fill_gradient_stop"] = ni
                                        fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                        picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                    fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                    if fg is not None:
                                        cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                        pr = state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
                                        # If a stop marker on the ramp is clicked, select that stop.
                                        stops_for_pick = get_gradient_stops(fg) if 'get_gradient_stops' in globals() else list(fg.get("stops") or [])
                                        if stops_for_pick:
                                            best_i = None
                                            best_d = 1e9
                                            for si_pick, st_pick in enumerate(stops_for_pick):
                                                try:
                                                    sp = float((st_pick or {}).get("pos", 0.0)) if isinstance(st_pick, dict) else float(st_pick[0])
                                                except Exception:
                                                    sp = 0.0
                                                sp = clamp(sp, 0.0, 1.0)
                                                sxp = pr.x + sp * max(1, pr.w - 1)
                                                d = abs(event.pos[0] - sxp)
                                                if d <= 7 and d < best_d:
                                                    best_d = d
                                                    best_i = si_pick
                                            if best_i is not None:
                                                cur_stop_i = int(best_i)
                                                state["fill_gradient_stop"] = cur_stop_i
                                        rel = (event.pos[0] - pr.x) / max(1, pr.w - 1)
                                        rel = clamp(rel, 0.0, 1.0)
                                        if 'set_gradient_stop_pos' in globals():
                                            for si in sel_list:
                                                if 0 <= si < len(strokes):
                                                    sfg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                    if sfg is not None:
                                                        sidx = clamp_gradient_stop_index(sfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                                        ng, _ni = set_gradient_stop_pos(sfg, sidx, rel)
                                                        strokes[si]["fill_gradient"] = ng
                                                        strokes[si]["fill_color"] = None
                                            pfg2 = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else None
                                            if pfg2 is not None:
                                                sidx = clamp_gradient_stop_index(pfg2, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                                _ngp, ni = set_gradient_stop_pos(pfg2, sidx, rel)
                                                state["fill_gradient_stop"] = ni
                                                fc = get_gradient_stop_color(_ngp, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                                picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                        fill_stop_pos_drag = True
                                        state["fill_stop_pos_drag"] = True
                                elif primary_obj is not None and color_target == "fill" and comp_style_target is None and any(r.collidepoint(event.pos) for r in (state.get("fill_stop_rects") or {}).values()):
                                    # reverse so if any overlap occurs, topmost/latest wins
                                    items = list((state.get("fill_stop_rects") or {}).items())
                                    skey = next((k for k, r in reversed(items) if r.collidepoint(event.pos)), None)
                                    if skey is not None:
                                        try:
                                            state["fill_gradient_stop"] = int(skey)
                                        except Exception:
                                            state["fill_gradient_stop"] = 0
                                        fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else None
                                        if fg is not None:
                                            si_clamped = clamp_gradient_stop_index(fg, int(state.get("fill_gradient_stop", 0) or 0)) if 'clamp_gradient_stop_index' in globals() else int(state.get("fill_gradient_stop", 0) or 0)
                                            state["fill_gradient_stop"] = si_clamped
                                            fc = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                            picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state["sv_rect"].collidepoint(event.pos):
                                    picker_drag_sv = True
                                    sv = state["sv_rect"]
                                    picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                                    picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                                    col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                    if comp_style_target is not None:
                                        si, ci = comp_style_target
                                        if 0 <= si < len(strokes):
                                            cur_sc, _ = _effective_component_style(strokes[si], ci)
                                            alpha = color_alpha(cur_sc, 1.0)
                                            _set_comp_stroke_color(si, ci, col, alpha)
                                    else:
                                        for si in sel_list:
                                            if 0 <= si < len(strokes):
                                                if color_target == "stroke":
                                                    alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                                    strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                                else:
                                                    fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                    if fg is not None:
                                                        stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                        alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                                        strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                    else:
                                                        alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                        strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                                        strokes[si]["fill_gradient"] = None
                                    state["picker_drag_sv"] = True
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state["hue_rect"].collidepoint(event.pos):
                                    picker_drag_hue = True
                                    hr = state["hue_rect"]
                                    picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                                    col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                    if comp_style_target is not None:
                                        si, ci = comp_style_target
                                        if 0 <= si < len(strokes):
                                            cur_sc, _ = _effective_component_style(strokes[si], ci)
                                            alpha = color_alpha(cur_sc, 1.0)
                                            _set_comp_stroke_color(si, ci, col, alpha)
                                    else:
                                        for si in sel_list:
                                            if 0 <= si < len(strokes):
                                                if color_target == "stroke":
                                                    alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                                    strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                                else:
                                                    fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                    if fg is not None:
                                                        stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                        alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                                        strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                    else:
                                                        alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                        strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                                        strokes[si]["fill_gradient"] = None
                                    state["picker_drag_hue"] = True
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                    ar = state["alpha_rect"]
                                    new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                                    if comp_style_target is not None:
                                        si, ci = comp_style_target
                                        if 0 <= si < len(strokes):
                                            cur_sc, _ = _effective_component_style(strokes[si], ci)
                                            base = color_rgb(cur_sc, (0.1,0.1,0.15))
                                            _set_comp_stroke_color(si, ci, base, new_alpha)
                                    else:
                                        for si in sel_list:
                                            if 0 <= si < len(strokes):
                                                if color_target == "stroke":
                                                    strokes[si]["stroke_color"] = set_color_alpha(strokes[si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                                                else:
                                                    fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                    if fg is not None:
                                                        stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                        cstop = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1)
                                                        strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (cstop[0], cstop[1], cstop[2], new_alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                    elif strokes[si].get("fill_color") is not None:
                                                        strokes[si]["fill_color"] = set_color_alpha(strokes[si].get("fill_color"), new_alpha)
                                    picker_drag_alpha = True
                                    state["picker_drag_alpha"] = True
                                elif primary_obj is not None:
                                    # preset swatches
                                    rects = state["stroke_swatch_rects"] if color_target == "stroke" else state["fill_swatch_rects"]
                                    for i, r in enumerate(rects):
                                        if r.w > 0 and r.collidepoint(event.pos) and i < len(STROKE_SWATCHES):
                                            col = STROKE_SWATCHES[i]
                                            if comp_style_target is not None:
                                                si, ci = comp_style_target
                                                if 0 <= si < len(strokes):
                                                    cur_sc, _ = _effective_component_style(strokes[si], ci)
                                                    alpha = color_alpha(cur_sc, 1.0)
                                                    _set_comp_stroke_color(si, ci, col, alpha)
                                            else:
                                                for si in sel_list:
                                                    if 0 <= si < len(strokes):
                                                        if color_target == "stroke":
                                                            alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                                            strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                                        else:
                                                            fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                            if fg is not None:
                                                                stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                                alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                                                strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                            else:
                                                                alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                                strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                                                strokes[si]["fill_gradient"] = None
                                            picker_h, picker_s, picker_v = rgb_to_hsv(*col)
                                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                            break
                    elif tool_mode == "selection" and selected_strokes and selection_submode == "transform":
                        # Modern color picker interactions (shape-level in transform, stroke-level per selected curve in curve mode)
                        comp_style_target = None
                        if selection_submode == "curve" and selected_curve and len(selected_strokes) == 1 and selected_curve[0] in selected_strokes:
                            comp_style_target = selected_curve
                        if comp_style_target is not None:
                            color_target = "stroke"
                            state["color_target"] = "stroke"
                        if selection_submode == "curve" and comp_style_target is None:
                            pass
                        else:
                            sel_list = sorted(selected_strokes)
                            primary_i = sel_list[0]
                            primary_obj = strokes[primary_i] if 0 <= primary_i < len(strokes) else None
                            def _set_comp_stroke_color(si, ci, rgb, alpha):
                                comps = _stroke_components(strokes[si])
                                if 0 <= ci < len(comps):
                                    comps[ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
                                    strokes[si]["components"] = comps
                            if primary_obj is None:
                                pass
                            elif state["tab_stroke_rect"].collidepoint(event.pos):
                                color_target = "stroke"
                                state["color_target"] = color_target
                                if comp_style_target is not None:
                                    sc, _sw = _effective_component_style(primary_obj, comp_style_target[1])
                                    sc = sc or (0.1, 0.1, 0.15)
                                else:
                                    sc = primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
                                picker_h, picker_s, picker_v = rgb_to_hsv(*sc)
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state["tab_fill_rect"].collidepoint(event.pos) and comp_style_target is None:
                                color_target = "fill"
                                state["color_target"] = color_target
                                fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) and primary_obj.get("fill_gradient", {}).get("type") in ("linear","radial") else None)
                                if fg is not None:
                                    stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                    fc = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                else:
                                    fc = primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
                                picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and color_target == "fill" and comp_style_target is None:
                                for si in sel_list:
                                    if 0 <= si < len(strokes):
                                        strokes[si]["fill_color"] = None
                                        strokes[si]["fill_gradient"] = None
                            elif color_target == "fill" and comp_style_target is None and any(
                                state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                                for k in ("fill_type_prev_rect", "fill_type_next_rect")
                            ):
                                _fdir = -1 if state.get("fill_type_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                                _fmodes = ["solid", "linear", "radial", "conic", "spiral", "diamond", "square", "mesh", "pattern"]
                                _pfg_cur = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                _ppat_cur = get_fill_pattern(primary_obj) if 'get_fill_pattern' in globals() else primary_obj.get("fill_pattern")
                                if _ppat_cur is not None:
                                    _cur_fill_mode = "pattern"
                                elif _pfg_cur is not None:
                                    _cur_fill_mode = str(_pfg_cur.get("type", "linear"))
                                elif primary_obj.get("fill_color") is not None:
                                    _cur_fill_mode = "solid"
                                else:
                                    _cur_fill_mode = "solid"
                                if _cur_fill_mode not in _fmodes:
                                    _cur_fill_mode = "solid"
                                ftype = _fmodes[(_fmodes.index(_cur_fill_mode) + _fdir) % len(_fmodes)]
                                if ftype is not None:
                                    cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                    grad_types = ("linear", "radial", "conic", "spiral", "diamond", "square", "mesh")
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            st = strokes[si]
                                            fg = get_fill_gradient(st) if 'get_fill_gradient' in globals() else (st.get("fill_gradient") if isinstance(st.get("fill_gradient"), dict) else None)
                                            if ftype == "solid":
                                                if fg is not None:
                                                    si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else max(0, min(cur_stop_i, max(0, len(fg.get("stops") or []) - 1)))
                                                    col0 = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in globals() else (0.0, 0.0, 0.0, 1.0)
                                                else:
                                                    col0 = st.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                                                st["fill_color"] = tuple(color_rgba(col0, (0.45, 0.72, 1.0, 1.0)))
                                                st["fill_gradient"] = None
                                            elif ftype in grad_types:
                                                if fg is not None and str(fg.get("type")) in grad_types:
                                                    if ftype == "mesh" or str(fg.get("type")) == "mesh":
                                                        base = st.get("fill_color")
                                                        if base is None and isinstance(fg.get("stops"), list) and fg.get("stops"):
                                                            try:
                                                                base = get_gradient_stop_color(fg, 0) if 'get_gradient_stop_color' in globals() else (fg.get("stops")[0] or {}).get("color")
                                                            except Exception:
                                                                base = None
                                                        base = color_rgba(base or (0.2, 0.4, 0.9, 1.0), (0.2, 0.4, 0.9, 1.0))
                                                        c1m = (1.0, 1.0, 1.0, float(base[3]))
                                                        if ftype == "mesh" and 'default_mesh_gradient' in globals():
                                                            st["fill_gradient"] = default_mesh_gradient(base, c1m)
                                                        elif ftype == "linear" and 'default_linear_gradient' in globals():
                                                            st["fill_gradient"] = default_linear_gradient(base, c1m, 0.0)
                                                        elif ftype == "radial" and 'default_radial_gradient' in globals():
                                                            st["fill_gradient"] = default_radial_gradient((1.0, 1.0, 1.0, float(base[3])), base)
                                                        elif 'default_shaped_gradient' in globals():
                                                            st["fill_gradient"] = default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(base[3])), base)
                                                        else:
                                                            st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(base)}, {"pos": 1.0, "color": list(c1m)}]}
                                                    else:
                                                        ng = dict(fg)
                                                        ng["type"] = ftype
                                                        if ftype == "linear" and "angle" not in ng:
                                                            ng["angle"] = 0.0
                                                        if ftype in ("radial", "conic", "spiral", "diamond", "square"):
                                                            if "center" not in ng:
                                                                ng["center"] = [0.5, 0.5]
                                                            if "radii" not in ng:
                                                                ng["radii"] = [0.5, 0.5]
                                                            if "angle" not in ng:
                                                                ng["angle"] = 0.0
                                                            if ftype == "spiral" and "turns" not in ng:
                                                                ng["turns"] = 2.0
                                                        if 'normalize_gradient' in globals():
                                                            try:
                                                                ng = normalize_gradient(ng)
                                                            except Exception:
                                                                pass
                                                        st["fill_gradient"] = ng
                                                else:
                                                    base = st.get("fill_color") or (0.2, 0.4, 0.9, 1.0)
                                                    c0 = color_rgba(base, (0.2, 0.4, 0.9, 1.0))
                                                    c1 = (1.0, 1.0, 1.0, float(c0[3]))
                                                    if ftype == "mesh" and 'default_mesh_gradient' in globals():
                                                        st["fill_gradient"] = default_mesh_gradient(c0, c1)
                                                    elif ftype == "linear" and 'default_linear_gradient' in globals():
                                                        st["fill_gradient"] = default_linear_gradient(c0, c1, 0.0)
                                                    elif ftype == "radial" and 'default_radial_gradient' in globals():
                                                        st["fill_gradient"] = default_radial_gradient((1.0, 1.0, 1.0, float(c0[3])), c0)
                                                    elif 'default_shaped_gradient' in globals():
                                                        st["fill_gradient"] = default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(c0[3])), c0)
                                                    else:
                                                        st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(c0)}, {"pos": 1.0, "color": list(c1)}]}
                                                st["fill_color"] = None
                                            elif ftype == "pattern":
                                                pat = get_fill_pattern(st) if 'get_fill_pattern' in globals() else None
                                                if pat is None and 'new_pattern' in globals():
                                                    pat = new_pattern("stripes")
                                                st["fill_pattern"] = pat
                                                st["fill_color"] = None
                                                st["fill_gradient"] = None
                                    pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                    if pfg is not None:
                                        state["fill_gradient_stop"] = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                                        fc = get_gradient_stop_color(pfg, int(state.get("fill_gradient_stop", 0) or 0)) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                        picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                    elif ftype == "solid":
                                        fc = primary_obj.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                                        picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                        state["fill_gradient_stop"] = 0
                            elif color_target == "fill" and comp_style_target is None and state.get("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                for si in sel_list:
                                    if 0 <= si < len(strokes):
                                        fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                        if fg is not None and 'add_gradient_stop' in globals():
                                            si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                            ng, ni = add_gradient_stop(fg, si_clamped)
                                            strokes[si]["fill_gradient"] = ng
                                            strokes[si]["fill_color"] = None
                                pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                if pfg is not None:
                                    ni = min((clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i) + 1, max(0, len(pfg.get("stops") or []) - 1))
                                    state["fill_gradient_stop"] = ni
                                    fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                    picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif color_target == "fill" and comp_style_target is None and state.get("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                for si in sel_list:
                                    if 0 <= si < len(strokes):
                                        fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                        if fg is not None and 'remove_gradient_stop' in globals():
                                            si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                            ng, ni = remove_gradient_stop(fg, si_clamped)
                                            strokes[si]["fill_gradient"] = ng
                                            strokes[si]["fill_color"] = None
                                pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                if pfg is not None:
                                    ni = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                                    state["fill_gradient_stop"] = ni
                                    fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                    picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif color_target == "fill" and comp_style_target is None and state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                                fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
                                if fg is not None:
                                    cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                    pr = state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
                                    # If a stop marker on the ramp is clicked, select that stop.
                                    stops_for_pick = get_gradient_stops(fg) if 'get_gradient_stops' in globals() else list(fg.get("stops") or [])
                                    if stops_for_pick:
                                        best_i = None
                                        best_d = 1e9
                                        for si_pick, st_pick in enumerate(stops_for_pick):
                                            try:
                                                sp = float((st_pick or {}).get("pos", 0.0)) if isinstance(st_pick, dict) else float(st_pick[0])
                                            except Exception:
                                                sp = 0.0
                                            sp = clamp(sp, 0.0, 1.0)
                                            sxp = pr.x + sp * max(1, pr.w - 1)
                                            d = abs(event.pos[0] - sxp)
                                            if d <= 7 and d < best_d:
                                                best_d = d
                                                best_i = si_pick
                                        if best_i is not None:
                                            cur_stop_i = int(best_i)
                                            state["fill_gradient_stop"] = cur_stop_i
                                    rel = (event.pos[0] - pr.x) / max(1, pr.w - 1)
                                    rel = clamp(rel, 0.0, 1.0)
                                    if 'set_gradient_stop_pos' in globals():
                                        for si in sel_list:
                                            if 0 <= si < len(strokes):
                                                sfg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                if sfg is not None:
                                                    sidx = clamp_gradient_stop_index(sfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                                    ng, _ni = set_gradient_stop_pos(sfg, sidx, rel)
                                                    strokes[si]["fill_gradient"] = ng
                                                    strokes[si]["fill_color"] = None
                                        pfg2 = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else None
                                        if pfg2 is not None:
                                            sidx = clamp_gradient_stop_index(pfg2, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                            _ngp, ni = set_gradient_stop_pos(pfg2, sidx, rel)
                                            state["fill_gradient_stop"] = ni
                                            fc = get_gradient_stop_color(_ngp, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                            picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                    fill_stop_pos_drag = True
                                    state["fill_stop_pos_drag"] = True
                            elif color_target == "fill" and comp_style_target is None and any(r.collidepoint(event.pos) for r in (state.get("fill_stop_rects") or {}).values()):
                                items = list((state.get("fill_stop_rects") or {}).items())
                                skey = next((k for k, r in reversed(items) if r.collidepoint(event.pos)), None)
                                if skey is not None:
                                    try:
                                        state["fill_gradient_stop"] = int(skey)
                                    except Exception:
                                        state["fill_gradient_stop"] = 0
                                    fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else None
                                    if fg is not None:
                                        si_clamped = clamp_gradient_stop_index(fg, int(state.get("fill_gradient_stop", 0) or 0)) if 'clamp_gradient_stop_index' in globals() else int(state.get("fill_gradient_stop", 0) or 0)
                                        state["fill_gradient_stop"] = si_clamped
                                        fc = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                                        picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state["sv_rect"].collidepoint(event.pos):
                                picker_drag_sv = True
                                sv = state["sv_rect"]
                                picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                                picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                                col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                if comp_style_target is not None:
                                    si, ci = comp_style_target
                                    if 0 <= si < len(strokes):
                                        cur_sc, _ = _effective_component_style(strokes[si], ci)
                                        alpha = color_alpha(cur_sc, 1.0)
                                        _set_comp_stroke_color(si, ci, col, alpha)
                                else:
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            if color_target == "stroke":
                                                alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                                strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                            else:
                                                fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                if fg is not None:
                                                    stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                    alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                                    strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                else:
                                                    alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                    strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                                    strokes[si]["fill_gradient"] = None
                                state["picker_drag_sv"] = True
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state["hue_rect"].collidepoint(event.pos):
                                picker_drag_hue = True
                                hr = state["hue_rect"]
                                picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                                col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                if comp_style_target is not None:
                                    si, ci = comp_style_target
                                    if 0 <= si < len(strokes):
                                        cur_sc, _ = _effective_component_style(strokes[si], ci)
                                        alpha = color_alpha(cur_sc, 1.0)
                                        _set_comp_stroke_color(si, ci, col, alpha)
                                else:
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            if color_target == "stroke":
                                                alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                                strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                            else:
                                                fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                if fg is not None:
                                                    stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                    alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                                    strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                else:
                                                    alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                    strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                                    strokes[si]["fill_gradient"] = None
                                state["picker_drag_hue"] = True
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                ar = state["alpha_rect"]
                                new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                                if comp_style_target is not None:
                                    si, ci = comp_style_target
                                    if 0 <= si < len(strokes):
                                        cur_sc, _ = _effective_component_style(strokes[si], ci)
                                        base = color_rgb(cur_sc, (0.1,0.1,0.15))
                                        _set_comp_stroke_color(si, ci, base, new_alpha)
                                else:
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            if color_target == "stroke":
                                                strokes[si]["stroke_color"] = set_color_alpha(strokes[si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                                            else:
                                                fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                if fg is not None:
                                                    stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                    cstop = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1)
                                                    strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (cstop[0], cstop[1], cstop[2], new_alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                elif strokes[si].get("fill_color") is not None:
                                                    strokes[si]["fill_color"] = set_color_alpha(strokes[si].get("fill_color"), new_alpha)
                                picker_drag_alpha = True
                                state["picker_drag_alpha"] = True
                            else:
                                # preset swatches (draw_panel populates rects matching active target)
                                rects = state["stroke_swatch_rects"] if color_target == "stroke" else state["fill_swatch_rects"]
                                for i, r in enumerate(rects):
                                    if r.w > 0 and r.collidepoint(event.pos) and i < len(STROKE_SWATCHES):
                                        col = STROKE_SWATCHES[i]
                                        if comp_style_target is not None:
                                            si, ci = comp_style_target
                                            if 0 <= si < len(strokes):
                                                cur_sc, _ = _effective_component_style(strokes[si], ci)
                                                alpha = color_alpha(cur_sc, 1.0)
                                                _set_comp_stroke_color(si, ci, col, alpha)
                                        else:
                                            for si in sel_list:
                                                if 0 <= si < len(strokes):
                                                    if color_target == "stroke":
                                                        alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                                        strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                                    else:
                                                        fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                                        if fg is not None:
                                                            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                                            alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                                            strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                                        else:
                                                            alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                            strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                                            strokes[si]["fill_gradient"] = None
                                        picker_h, picker_s, picker_v = rgb_to_hsv(*col)
                                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                        break
                elif in_canvas(event.pos):
                    cpos = to_canvas(event.pos)
                    if tool_mode == "draw":
                        mods = pygame.key.get_mods()
                        if (mods & pygame.KMOD_ALT) and reference_image and reference_image.get("visible", True):
                            ref_drag = {"offset": (cpos[0] - reference_image.get("x", 0), cpos[1] - reference_image.get("y", 0))}
                            drawing = False
                        elif draw_tool == "eraser":
                            hit_e = hit_test_stroke(cpos, strokes)
                            if hit_e is not None:
                                push_undo()
                                strokes, _ = erase_curve_at(strokes, cpos)
                            drawing = False
                            current_points = []
                            selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
                        elif draw_tool == "bucket":
                            # Geometric bucket fill (ray-casting/planar-face inspired): create a filled
                            # vector shape for the enclosed region under the click, without a stroke.
                            try:
                                from models.fill import bucket_fill_to_beziers
                                segs_fill = bucket_fill_to_beziers(strokes, cpos, simplify_epsilon=1.5, max_points=100)
                                if segs_fill:
                                    push_undo()
                                    fill_color = (bucket_fill_color[0], bucket_fill_color[1],
                                                  bucket_fill_color[2], 1.0)
                                    new_st = new_stroke(
                                        segs_fill,
                                        stroke_color=(0.0, 0.0, 0.0, 0.0),
                                        stroke_width=0.0,
                                        fill_color=fill_color,
                                        algorithm="fit",
                                    )
                                    strokes.append(new_st)
                            except Exception:
                                pass
                            drawing = False
                            current_points = []
                            selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
                        elif draw_tool == "cutter":
                            # Razor: collect the swipe; curves are split on release.
                            cutting = True
                            cut_points = [cpos]
                            drawing = False
                            current_points = []
                        elif draw_tool == "text":
                            # Place a text insertion caret at the clicked point.
                            if text_entry is not None:
                                commit_text_entry()
                            text_entry = {"x": cpos[0], "y": cpos[1], "text": "",
                                          "family": text_family, "size": text_size}
                            drawing = False
                            current_points = []
                            selected_strokes.clear(); selected_point = None
                            selected_curve = None; selected_curves.clear()
                        elif draw_tool == "pen" and draw_shape == "pen":
                            # Bezier pen: click-to-place anchors, drag handles.
                            shift_held = bool(mods & pygame.KMOD_SHIFT)
                            pos = draw_snap_point(cpos, strokes, snap_radius(), shift_held)
                            if pos is None:
                                pos = snap_world(cpos)
                            else:
                                pos = snap_world(pos)
                            now = pygame.time.get_ticks()
                            is_double = (now - _bezier_last_click.get("time", 0) < 400 and
                                         math.hypot(pos[0] - _bezier_last_click.get("pos", (1e9, 1e9))[0],
                                                     pos[1] - _bezier_last_click.get("pos", (1e9, 1e9))[1]) < 8.0)
                            if bezier_pen and _bezier_pen_near_first(pos, max(10.0, float(snap_radius() or 0))) and len(bezier_pen.get("anchors", [])) >= 3:
                                # Close path: drag on first anchor adjusts its handles, finalize on mouseup.
                                first = bezier_pen["anchors"][0]
                                bezier_pen["mouse_down"] = True
                                bezier_pen["dragging"] = True
                                bezier_pen["dragging_first"] = True
                                bezier_pen["down_pos"] = first["pt"]
                                bezier_pen["preview_pt"] = pos
                            elif is_double and bezier_pen and len(bezier_pen.get("anchors", [])) >= 2:
                                _bezier_pen_finish(close_path=False)
                            else:
                                _bezier_pen_add_anchor(pos)
                            _bezier_last_click["time"] = now
                            _bezier_last_click["pos"] = pos
                            drawing = False
                            current_points = []
                        else:
                            # If starting a non-bezier drawing gesture, cancel unfinished bezier path.
                            if bezier_pen is not None:
                                _bezier_pen_cancel()
                            drawing = True
                            shift_held = bool(mods & pygame.KMOD_SHIFT)
                            start_pos = draw_snap_point(cpos, strokes, snap_radius(), shift_held)
                            if start_pos is None:
                                start_pos = snap_world(cpos)
                            current_points = [start_pos]
                    elif redrawing_curve is not None:
                        # Redraw selected stroke/component: focused draw with snap features
                        fixed_start = redrawing_curve.get("fixed_start")
                        if fixed_start is not None:
                            start_pos = tuple(fixed_start)
                        else:
                            shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                            start_pos = draw_snap_point(cpos, strokes, snap_radius(), shift_held) or cpos
                        redrawing_curve["points"] = [start_pos]
                        redrawing_curve["started"] = True
                    else:
                        # Selection mode
                        selected_point = None
                        transform_drag = None
                        mods = pygame.key.get_mods()
                        shift = bool(mods & pygame.KMOD_SHIFT)
                        if eyedropper_pick:
                            hit = hit_test_stroke(cpos, strokes)
                            if hit is not None and 0 <= hit < len(strokes):
                                src_stroke = strokes[hit]
                                src_comp_i = hit_test_component(src_stroke, cpos)
                                if src_comp_i is None:
                                    src_comp_i = 0
                                src_sc, src_sw = _effective_component_style(src_stroke, src_comp_i)
                                src_fc = src_stroke.get("fill_color")
                                src_fg = copy.deepcopy(src_stroke.get("fill_gradient")) if isinstance(src_stroke, dict) else None
                                src_comps = _stroke_components(src_stroke)
                                if 0 <= src_comp_i < len(src_comps):
                                    src_dists = copy.deepcopy(_get_distortion_styles(src_comps[src_comp_i]))
                                else:
                                    src_dists = []
                                had_sel = bool(selected_strokes)
                                if not had_sel:
                                    selected_strokes = {hit}
                                    if selection_submode == "curve":
                                        selected_curve = (hit, src_comp_i)
                                    else:
                                        selected_curve = None
                                else:
                                    push_undo()
                                    for si in list(selected_strokes):
                                        if not (0 <= si < len(strokes)):
                                            continue
                                        st = strokes[si]
                                        st["stroke_width"] = float(src_sw)
                                        st["fill_color"] = copy.deepcopy(src_fc) if src_fc is not None else None
                                        st["fill_gradient"] = copy.deepcopy(src_fg) if src_fg is not None else None
                                        # In curve submode, apply stroke style/waves to the
                                        # selected component but keep fill at stroke level.
                                        if (selection_submode == "curve" and selected_curve
                                                and selected_curve[0] == si and len(selected_strokes) == 1):
                                            ci = selected_curve[1]
                                            comps = _stroke_components(st)
                                            if 0 <= ci < len(comps):
                                                comps[ci] = copy.deepcopy(comps[ci])
                                                comps[ci]["stroke_color"] = copy.deepcopy(src_sc)
                                                comps[ci]["stroke_width"] = float(src_sw)
                                                comps[ci].pop("wave", None)
                                                comps[ci]["styles"] = [s for s in comps[ci].get("styles", []) if not _is_distortion_style(s)]
                                                for wi, wv in enumerate(src_dists):
                                                    _set_distortion_style(comps[ci], wv, wi)
                                                st["components"] = comps
                                        else:
                                            st["stroke_color"] = copy.deepcopy(src_sc)
                                            comps = _stroke_components(st)
                                            if comps:
                                                new_comps = []
                                                for comp in comps:
                                                    comp = copy.deepcopy(comp)
                                                    # clear per-component stroke overrides to apply uniformly
                                                    comp.pop("stroke_color", None)
                                                    comp.pop("stroke_width", None)
                                                    comp.pop("wave", None)
                                                    comp["styles"] = [s for s in comp.get("styles", []) if not _is_distortion_style(s)]
                                                    for wi, wv in enumerate(src_dists):
                                                        _set_distortion_style(comp, wv, wi)
                                                    new_comps.append(comp)
                                                st["components"] = new_comps
                                eyedropper_pick = False
                                state["eyedropper_pick"] = False
                            # If the click missed, stay in pick mode.
                        elif selection_submode == "curve":
                            handled_curve = False
                            # Curve mode: select/edit curves (components) only; node editing is in Nodes mode
                            selected_point = None
                            if curve_cut_mode and (selected_curves or selected_strokes):
                                # Razor swipe across the selected curve/stroke.
                                cutting = True
                                cut_points = [cpos]
                                handled_curve = True
                            if not handled_curve:
                                hit = hit_test_stroke(cpos, strokes)
                                hit_curve = None
                                if hit is not None and 0 <= hit < len(strokes):
                                    comp_i = hit_test_component(strokes[hit], cpos)
                                    if comp_i is not None:
                                        hit_curve = (hit, int(comp_i))
                                if hit_curve is not None:
                                    if state.get("repeat_pick_mode") and state.get("repeat_pick_target"):
                                        tgt = state.get("repeat_pick_target")
                                        try:
                                            tsi, tci, twi = int(tgt[0]), int(tgt[1]), int(tgt[2])
                                        except Exception:
                                            tsi, tci, twi = -1, -1, 0
                                        if 0 <= tsi < len(strokes):
                                            src_si, src_ci = hit_curve
                                            src_comps = _stroke_components(strokes[src_si])
                                            if 0 <= src_ci < len(src_comps):
                                                src_segs = src_comps[src_ci].get("segs") or []
                                                rp = _segs_to_repeat_points(src_segs)
                                                if rp:
                                                    tgt_comps = _stroke_components(strokes[tsi])
                                                    if 0 <= tci < len(tgt_comps):
                                                        tgt_comps[tci] = dict(tgt_comps[tci])
                                                        w = _get_distortion_style(tgt_comps[tci], twi)
                                                        if w.get("type") == "thickness":
                                                            w["thickness_points"] = rp
                                                        else:
                                                            w["repeat_points"] = rp
                                                            w["type"] = "repeat"
                                                        w["enabled"] = True
                                                        _set_distortion_style(tgt_comps[tci], w, twi)
                                                        strokes[tsi]["components"] = tgt_comps
                                        state["repeat_pick_mode"] = False
                                        state["repeat_pick_target"] = None
                                        repeat_pick_mode = False
                                        repeat_pick_target = None
                                        handled_curve = True
                                    elif shift:
                                        if hit_curve in selected_curves:
                                            selected_curves.discard(hit_curve)
                                            if selected_curve == hit_curve:
                                                selected_curve = next(iter(selected_curves), None)
                                        else:
                                            selected_curves.add(hit_curve)
                                            selected_curve = hit_curve
                                        selected_strokes = {si for (si, _ci) in selected_curves}
                                        handled_curve = True
                                    else:
                                        selected_curves = {hit_curve}
                                        selected_curve = hit_curve
                                        selected_strokes = {si for (si, _ci) in selected_curves}
                                        handled_curve = True
                                elif hit is None and not shift:
                                    selected_curves.clear()
                                    selected_curve = None
                                    selected_strokes.clear()
                            # keep active curve consistent with multi-selection
                            if selected_curves and selected_curve not in selected_curves:
                                selected_curve = next(iter(selected_curves), None)
                            if not selected_curves:
                                selected_curve = None
                                # if a stroke was selected via other means, keep stroke selection only
                                # when there are no curve hits; curve mode primarily tracks curves
                                if handled_curve:
                                    selected_strokes.clear()
                        elif selection_submode == "transform":
                            handled = False
                            pending_transform_toggle = None
                            if selected_strokes:
                                bb = combined_obb(strokes, selected_strokes)
                                # Gradient on-canvas handle hit-test (when editing fill gradient)
                                if not handled and state.get("color_target", color_target) == "fill":
                                    _g_primary = None
                                    _g_grad = None
                                    for _gsi in sorted(selected_strokes):
                                        if 0 <= _gsi < len(strokes):
                                            _gst = strokes[_gsi]
                                            _gfg = _gst.get("fill_gradient") if isinstance(_gst, dict) else None
                                            try:
                                                _gfg = get_fill_gradient(_gst) or _gfg
                                            except Exception:
                                                pass
                                            if isinstance(_gfg, dict) and str(_gfg.get("type")) in ("linear", "radial", "conic", "spiral", "diamond", "square"):
                                                _g_primary = _gsi
                                                _g_grad = _gfg
                                                break
                                    if _g_primary is not None and _g_grad is not None:
                                        _ghit, _ginfo = hit_test_gradient_handle(strokes[_g_primary], _g_grad, cpos)
                                        if _ghit is not None:
                                            push_undo()
                                            _gtype = str(_g_grad.get("type", "linear"))
                                            _edit_strokes = []
                                            for _gsi in sorted(selected_strokes):
                                                if 0 <= _gsi < len(strokes):
                                                    _gst = strokes[_gsi]
                                                    _fg2 = _gst.get("fill_gradient") if isinstance(_gst, dict) else None
                                                    try:
                                                        _fg2 = get_fill_gradient(_gst) or _fg2
                                                    except Exception:
                                                        pass
                                                    if isinstance(_fg2, dict) and str(_fg2.get("type")) == _gtype:
                                                        _edit_strokes.append(_gsi)
                                            if not _edit_strokes:
                                                _edit_strokes = [_g_primary]
                                            gradient_drag = {
                                                "handle": _ghit,
                                                "stroke_is": _edit_strokes,
                                                "grad_type": _gtype,
                                                "primary_i": _g_primary,
                                                "bbox": (_ginfo or {}).get("bbox"),
                                            }
                                            handled = True
                                if bb:
                                    eff_pivot = pivot_pos if pivot_pos is not None else (bb["cx"], bb["cy"])
                                    # hit pivot marker first (draggable rotation/scale center)
                                    if not handled and math.hypot(cpos[0] - eff_pivot[0], cpos[1] - eff_pivot[1]) <= 10.0:
                                        pivot_drag = {"start": cpos, "start_pivot": eff_pivot}
                                        handled = True
                                    if not handled:
                                        h = hit_test_bbox_handle(bb, cpos, mode=transform_handle_mode)
                                        if h is not None:
                                            cx, cy = eff_pivot
                                            push_undo()
                                            import copy as _copy
                                            start_strokes = {i: _copy.deepcopy(strokes[i]) for i in sorted(selected_strokes) if 0 <= i < len(strokes)}
                                            transform_drag = {
                                                "handle": h,
                                                "start_mouse": cpos,
                                                "start_strokes": start_strokes,
                                                "center": (cx, cy),
                                                "start_bbox": bb,
                                                "mode": transform_handle_mode,
                                            }
                                            handled = True
                                        elif point_in_bbox(bb, cpos):
                                            # click on selected body: move on drag, toggle scale/rotate mode on click-without-drag
                                            pending_transform_toggle = {
                                                "start": cpos,
                                                "moved": False,
                                                "primed": True,
                                            }
                                            handled = True
                                elif not handled and hit_test_stroke(cpos, strokes) in selected_strokes:
                                    pending_transform_toggle = {"start": cpos, "moved": False, "primed": True}
                                    handled = True
                            if not handled:
                                hit = hit_test_stroke(cpos, strokes)
                                if hit is not None:
                                    _gid = group_id_of(strokes[hit]) if 0 <= hit < len(strokes) else None
                                    _members = set(group_members(strokes, _gid)) if _gid else {hit}
                                    if shift:
                                        if hit in selected_strokes:
                                            selected_strokes -= _members
                                        else:
                                            selected_strokes |= _members
                                        drag_last = None
                                    else:
                                        selected_strokes = set(_members)
                                    if selected_strokes:
                                        primary_i = sorted(selected_strokes)[0]
                                        if 0 <= primary_i < len(strokes):
                                            width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))
                                        # allow immediate drag-move of newly selected (no toggle)
                                        drag_last = cpos
                                    else:
                                        drag_last = None
                                else:
                                    # start marquee selection on empty area
                                    marquee_select = {"start": cpos, "current": cpos, "add": shift}
                                    drag_last = None
                        else:
                            # Nodes mode: point editing only for single selection
                            if len(selected_strokes) == 1:
                                only = next(iter(selected_strokes))
                                if 0 <= only < len(strokes):
                                    try:
                                        disp_segs = stroke_display_segs(strokes[only]) if 'stroke_display_segs' in globals() else None
                                    except Exception:
                                        disp_segs = None
                                    pt_hit = hit_test_point(strokes[only], cpos, segs_override=disp_segs)
                                    if pt_hit is not None:
                                        push_undo()
                                        selected_point = pt_hit; drag_last = cpos
                                    else:
                                        hit = hit_test_stroke(cpos, strokes)
                                        if hit == only:
                                            drag_last = cpos
                                        elif hit is not None:
                                            if shift:
                                                if hit in selected_strokes:
                                                    selected_strokes.discard(hit)
                                                else:
                                                    selected_strokes.add(hit)
                                            else:
                                                selected_strokes = {hit}
                                            if selected_strokes:
                                                primary_i = sorted(selected_strokes)[0]
                                                if 0 <= primary_i < len(strokes):
                                                    width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))
                                            drag_last = cpos if hit is not None else None
                                        else:
                                            if not shift:
                                                selected_strokes.clear()
                                            drag_last = None
                                else:
                                    selected_strokes.clear(); drag_last = None
                            else:
                                # multi or none: selection changes only
                                hit = hit_test_stroke(cpos, strokes)
                                if hit is not None:
                                    if shift:
                                        if hit in selected_strokes:
                                            selected_strokes.discard(hit)
                                        else:
                                            selected_strokes.add(hit)
                                    else:
                                        selected_strokes = {hit}
                                    if selected_strokes:
                                        primary_i = sorted(selected_strokes)[0]
                                        if 0 <= primary_i < len(strokes):
                                            width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))
                                    drag_last = cpos
                                else:
                                    if not shift:
                                        selected_strokes.clear()
                                    drag_last = None
                else:
                    # left bar area (not buttons) - ignore
                    pass

            elif event.type == pygame.MOUSEMOTION:
                if guide_drag is not None:
                    _gp = to_canvas(event.pos)
                    _gval = _gp[0] if guide_drag.get("axis") == "x" else _gp[1]
                    guides = move_guide(guides, guide_drag.get("index", 0), _gval)
                    continue
                if cutting:
                    cpos = clamp_to_canvas(event.pos)
                    if not cut_points or math.hypot(cpos[0] - cut_points[-1][0],
                                                    cpos[1] - cut_points[-1][1]) >= 1.0:
                        cut_points.append(cpos)
                    continue
                if pan_drag is not None:
                    sm = pan_drag["start_mouse"]; sp = pan_drag["start_pan"]
                    cfg.VIEW_PAN_X = sp[0] + (event.pos[0] - sm[0])
                    cfg.VIEW_PAN_Y = sp[1] + (event.pos[1] - sm[1])
                    continue
                if pivot_drag is not None and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    sp0 = pivot_drag.get("start_pivot", cpos)
                    sm = pivot_drag.get("start", cpos)
                    pivot_pos = (sp0[0] + cpos[0] - sm[0], sp0[1] + cpos[1] - sm[1])
                    continue
                if ref_opacity_drag and reference_image is not None:
                    bar = state.get("ref_opacity_rect", pygame.Rect(0,0,0,0))
                    if bar.w > 0:
                        reference_image["opacity"] = clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
                elif obj_opacity_drag and selected_strokes:
                    bar = state.get("obj_opacity_rect", pygame.Rect(0,0,0,0))
                    if bar.w > 0:
                        opacity = clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
                        for si in sorted(selected_strokes):
                            if 0 <= si < len(strokes) and isinstance(strokes[si], dict):
                                strokes[si] = set_appearance(strokes[si], opacity=opacity)
                elif bucket_picker_drag is not None:
                    if bucket_picker_drag == "sv":
                        bucket_pick(state.get("bucket_sv_rect", pygame.Rect(0,0,0,0)), event.pos, "sv")
                    else:
                        bucket_pick(state.get("bucket_hue_rect", pygame.Rect(0,0,0,0)), event.pos, "hue")
                elif ref_drag is not None and reference_image is not None and (pygame.mouse.get_pressed()[0]):
                    cpos = clamp_to_canvas(event.pos)
                    off = ref_drag.get("offset", (0, 0))
                    reference_image["x"] = cpos[0] - off[0]
                    reference_image["y"] = cpos[1] - off[1]
                elif wave_custom_drag is not None and pygame.mouse.get_pressed()[0] and selected_curve and selected_curve[0] in selected_strokes:
                    # hold-drag painting inside the custom wave/profile box
                    box = state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
                    if box.w > 0 and box.h > 0:
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                wi = int(state.get("wave_active_index", 0) or 0)
                                w = _get_distortion_style(comps[comp_i], wi)
                                wave_custom_drag = _custom_wave_paint(w, box, event.pos, wave_custom_drag)
                                state["wave_custom_drag"] = wave_custom_drag
                                _set_distortion_style(comps[comp_i], w, wi)
                                strokes[si]["components"] = comps
                elif wave_slider_drag is not None and pygame.mouse.get_pressed()[0] and selected_curve and selected_curve[0] in selected_strokes:
                    d = wave_slider_drag
                    si, comp_i = d.get("si"), d.get("comp_i")
                    key = d.get("key")
                    r = d.get("rect")
                    lo, hi = d.get("lo", 0.0), d.get("hi", 1.0)
                    wi = int(d.get("wi", 0) or 0)
                    if 0 <= si < len(strokes) and 0 <= comp_i < len(_stroke_components(strokes[si])):
                        comps = _stroke_components(strokes[si])
                        comps[comp_i] = dict(comps[comp_i])
                        w = _get_distortion_style(comps[comp_i], wi)
                        t = (event.pos[0] - r.x) / max(1, r.w - 1)
                        val = lo + clamp(t, 0.0, 1.0) * (hi - lo)
                        if key in ("amplitude", "noise", "phase", "seed", "amount", "location", "handle_rotate", "handle_length"):
                            val = float(int(round(val)))
                        elif key in ("frequency", "noise_scale"):
                            val = float(val)
                        else:
                            val = float(val)
                        w[key] = val
                        _set_distortion_style(comps[comp_i], w, wi)
                        strokes[si]["components"] = comps
                elif (picker_drag_sv or picker_drag_hue or picker_drag_alpha) and selected_strokes and (selection_submode == "transform" or (selection_submode == "curve" and selected_curve)):
                    color_target = state.get("color_target", color_target)
                    sel_list = sorted(selected_strokes)
                    comp_style_target = None
                    if selection_submode == "curve" and selected_curve and len(selected_strokes) == 1 and selected_curve[0] in selected_strokes:
                        comp_style_target = selected_curve
                        color_target = "stroke"
                        state["color_target"] = "stroke"
                    def _apply_comp_stroke_color_drag(si, ci, rgb, alpha):
                        comps = _stroke_components(strokes[si])
                        if 0 <= ci < len(comps):
                            comps[ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
                            strokes[si]["components"] = comps
                    if picker_drag_sv:
                        sv = state["sv_rect"]
                        picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                        picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                        col = hsv_to_rgb(picker_h, picker_s, picker_v)
                        if comp_style_target is not None:
                            si, ci = comp_style_target
                            if 0 <= si < len(strokes):
                                cur_sc, _ = _effective_component_style(strokes[si], ci)
                                alpha = color_alpha(cur_sc, 1.0)
                                _apply_comp_stroke_color_drag(si, ci, col, alpha)
                        else:
                            for si in sel_list:
                                if 0 <= si < len(strokes):
                                    if color_target == "stroke":
                                        alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                        strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                    else:
                                        fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                        if fg is not None:
                                            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                            alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                            strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                        else:
                                            alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                            strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                            strokes[si]["fill_gradient"] = None
                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                    elif picker_drag_hue:
                        hr = state["hue_rect"]
                        picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                        col = hsv_to_rgb(picker_h, picker_s, picker_v)
                        if comp_style_target is not None:
                            si, ci = comp_style_target
                            if 0 <= si < len(strokes):
                                cur_sc, _ = _effective_component_style(strokes[si], ci)
                                alpha = color_alpha(cur_sc, 1.0)
                                _apply_comp_stroke_color_drag(si, ci, col, alpha)
                        else:
                            for si in sel_list:
                                if 0 <= si < len(strokes):
                                    if color_target == "stroke":
                                        alpha = color_alpha(strokes[si].get("stroke_color"), 1.0)
                                        strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                                    else:
                                        fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                        if fg is not None:
                                            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                            alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                            strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                        else:
                                            alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                            strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                            strokes[si]["fill_gradient"] = None
                        state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                    elif picker_drag_alpha:
                        ar = state.get("alpha_rect", pygame.Rect(0,0,0,0))
                        new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                        if comp_style_target is not None:
                            si, ci = comp_style_target
                            if 0 <= si < len(strokes):
                                cur_sc, _ = _effective_component_style(strokes[si], ci)
                                base = color_rgb(cur_sc, (0.1,0.1,0.15))
                                _apply_comp_stroke_color_drag(si, ci, base, new_alpha)
                        else:
                            for si in sel_list:
                                if 0 <= si < len(strokes):
                                    if color_target == "stroke":
                                        strokes[si]["stroke_color"] = set_color_alpha(strokes[si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                                    else:
                                        fg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                        if fg is not None:
                                            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                            cstop = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1)
                                            strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (cstop[0], cstop[1], cstop[2], new_alpha)) if 'set_gradient_stop_color' in globals() else fg
                                        elif strokes[si].get("fill_color") is not None:
                                            strokes[si]["fill_color"] = set_color_alpha(strokes[si].get("fill_color"), new_alpha)
                elif fill_stop_pos_drag and selected_strokes and (selection_submode == "transform" or (selection_submode == "curve" and selected_curve and color_target == "fill")):
                    pr = state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
                    if pr.w > 1:
                        rel = (event.pos[0] - pr.x) / max(1, pr.w - 1)
                    else:
                        rel = 0.0
                    rel = clamp(rel, 0.0, 1.0)
                    cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                    sel_list = sorted(set(int(x) for x in (selected_strokes or [])))
                    primary_si = sel_list[0] if sel_list else -1
                    primary_obj = strokes[primary_si] if (0 <= primary_si < len(strokes)) else None
                    if primary_obj is not None and 'set_gradient_stop_pos' in globals():
                        for si in sel_list:
                            if 0 <= si < len(strokes):
                                sfg = get_fill_gradient(strokes[si]) if 'get_fill_gradient' in globals() else None
                                if sfg is not None:
                                    sidx = clamp_gradient_stop_index(sfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                                    ng, _ni = set_gradient_stop_pos(sfg, sidx, rel)
                                    strokes[si]["fill_gradient"] = ng
                                    strokes[si]["fill_color"] = None
                        pfg2 = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else None
                        if pfg2 is not None:
                            sidx = clamp_gradient_stop_index(pfg2, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                            _ngp, ni = set_gradient_stop_pos(pfg2, sidx, rel)
                            state["fill_gradient_stop"] = ni
                            fc = get_gradient_stop_color(_ngp, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                            picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                elif redrawing_curve is not None and redrawing_curve.get("started") and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    pts = redrawing_curve.get("points", [])
                    fixed_start = redrawing_curve.get("fixed_start")
                    fixed_end = redrawing_curve.get("fixed_end")
                    if fixed_start is not None and pts:
                        pts[0] = tuple(fixed_start)
                    keys = pygame.key.get_pressed()
                    straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    pts = advance_drawing_points(pts, cpos, strokes, snap_radius(), shift_held, straight_line, fixed_end=fixed_end)
                    redrawing_curve["points"] = pts
                elif marquee_select is not None and tool_mode == "selection" and pygame.mouse.get_pressed()[0]:
                    marquee_select["current"] = clamp_to_canvas(event.pos)
                elif tool_mode == "draw" and draw_tool == "pen" and draw_shape == "pen" and bezier_pen is not None:
                    cpos = clamp_to_canvas(event.pos)
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    if bezier_pen.get("mouse_down") and bezier_pen.get("dragging"):
                        # Dragging handle: follow cursor (grid snap only), don't object-snap.
                        cpos = snap_world(cpos)
                        _bezier_pen_update_drag(cpos)
                    else:
                        # Preview next anchor position with object snap.
                        sp = draw_snap_point(cpos, strokes, snap_radius(), shift_held)
                        pos = snap_world(sp if sp is not None else cpos)
                        bezier_pen["preview_pt"] = pos
                elif drawing and tool_mode == "draw" and draw_tool == "pen":
                    cpos = clamp_to_canvas(event.pos)
                    cpos = snap_world(cpos)
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    keys = pygame.key.get_pressed()
                    straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
                    current_points = advance_drawing_points(current_points, cpos, strokes, snap_radius(), shift_held, straight_line)
                elif tool_mode == "selection" and pending_transform_toggle is not None and selected_strokes and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    ptt = pending_transform_toggle
                    if not ptt.get("moved"):
                        dx0 = cpos[0] - ptt["start"][0]; dy0 = cpos[1] - ptt["start"][1]
                        if math.hypot(dx0, dy0) >= 4.0:
                            # threshold exceeded: start move drag instead of mode toggle
                            ptt["moved"] = True
                            pending_transform_toggle = None
                            if drag_last is None:
                                push_undo()
                            drag_last = ptt["start"]
                            # apply initial delta
                            dx = cpos[0] - drag_last[0]; dy = cpos[1] - drag_last[1]
                            if dx != 0 or dy != 0:
                                dx, dy, smart_snap_guides = _snap_move_delta(selected_strokes, dx, dy)
                            else:
                                smart_snap_guides = []
                            if dx != 0 or dy != 0:
                                for si in list(selected_strokes):
                                    if 0 <= si < len(strokes):
                                        strokes[si] = translate_stroke(strokes[si], dx, dy)
                                drag_last = (drag_last[0] + dx, drag_last[1] + dy)
                            else:
                                drag_last = cpos
                    # if not yet moved, wait for threshold or mouseup (toggle)
                elif tool_mode == "selection" and gradient_drag is not None and selected_strokes and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    gd = gradient_drag
                    ghandle = gd.get("handle")
                    gtype = gd.get("grad_type")
                    for si in list(gd.get("stroke_is") or []):
                        if not (0 <= si < len(strokes)):
                            continue
                        st = strokes[si]
                        fg = st.get("fill_gradient") if isinstance(st, dict) else None
                        try:
                            fg = get_fill_gradient(st) or fg
                        except Exception:
                            pass
                        if not isinstance(fg, dict) or str(fg.get("type")) != str(gtype):
                            continue
                        try:
                            bx0, by0, bx1, by1 = gradient_edit_bbox(st)
                        except Exception:
                            bx0, by0, bx1, by1 = 0.0, 0.0, 1.0, 1.0
                        bw = max(1e-6, bx1 - bx0)
                        bh = max(1e-6, by1 - by0)
                        bcx = (bx0 + bx1) * 0.5
                        bcy = (by0 + by1) * 0.5
                        if gtype == "linear":
                            if ghandle == "p1":
                                ang = math.degrees(math.atan2(bcy - cpos[1], bcx - cpos[0]))
                            else:
                                ang = math.degrees(math.atan2(cpos[1] - bcy, cpos[0] - bcx))
                            fg2 = dict(fg)
                            fg2["angle"] = float(ang)
                            try:
                                fg2 = normalize_gradient(fg2)
                            except Exception:
                                pass
                            st["fill_gradient"] = fg2
                        elif gtype in ("radial", "conic", "spiral", "diamond", "square"):
                            fg2 = dict(fg)
                            # current center in world for radius/rotation drags
                            cc = fg2.get("center", [0.5, 0.5])
                            try:
                                rcx = float(cc[0]); rcy = float(cc[1])
                            except Exception:
                                rcx, rcy = 0.5, 0.5
                            gcx = bx0 + clamp(rcx, 0.0, 1.0) * bw
                            gcy = by0 + clamp(rcy, 0.0, 1.0) * bh
                            rr = fg2.get("radii", [0.5, 0.5])
                            try:
                                rrx = float(rr[0]); rry = float(rr[1])
                            except Exception:
                                rrx, rry = 0.5, 0.5
                            try:
                                gang = float(fg2.get("angle", 0.0) or 0.0)
                            except Exception:
                                gang = 0.0
                            aang = math.radians(gang)
                            caa, saa = math.cos(aang), math.sin(aang)
                            dxm = cpos[0] - gcx
                            dym = cpos[1] - gcy
                            # local axis projections (rotated shape axes)
                            lx = dxm * caa + dym * saa
                            ly = -dxm * saa + dym * caa
                            if ghandle == "center":
                                ncx = clamp((cpos[0] - bx0) / bw, 0.0, 1.0)
                                ncy = clamp((cpos[1] - by0) / bh, 0.0, 1.0)
                                fg2["center"] = [ncx, ncy]
                            elif ghandle == "rot":
                                fg2["angle"] = float(math.degrees(math.atan2(dym, dxm)))
                            elif ghandle == "rx":
                                fg2["radii"] = [max(0.01, abs(lx) / bw), max(0.01, abs(rry))]
                            elif ghandle == "ry":
                                fg2["radii"] = [max(0.01, abs(rrx)), max(0.01, abs(ly) / bh)]
                            elif ghandle == "edge":
                                fg2["radii"] = [max(0.01, abs(lx) / bw), max(0.01, abs(ly) / bh)]
                            else:
                                # fallback: move center
                                ncx = clamp((cpos[0] - bx0) / bw, 0.0, 1.0)
                                ncy = clamp((cpos[1] - by0) / bh, 0.0, 1.0)
                                fg2["center"] = [ncx, ncy]
                            try:
                                fg2 = normalize_gradient(fg2)
                            except Exception:
                                pass
                            st["fill_gradient"] = fg2
                    # keep UI fill state in sync for primary gradient
                    if selected_strokes:
                        try:
                            _ps = sorted(selected_strokes)[0]
                            if 0 <= _ps < len(strokes):
                                refresh_selection_ui_state(_ps)
                        except Exception:
                            pass
                elif tool_mode == "selection" and transform_drag is not None and selected_strokes and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    td = transform_drag
                    cx, cy = td["center"]  # pivot/rotation center
                    sx0, sy0 = td["start_mouse"]
                    h = td["handle"]
                    # snap scale/skew handle drags to nearby geometry and show alignment guides
                    if h != "rot" and not str(h).startswith("rot_"):
                        _sr = snap_radius()
                        if _sr > 0:
                            _sel_set = set(selected_strokes)
                            _other = [s for _i, s in enumerate(strokes) if _i not in _sel_set]
                            if _other:
                                _sp = nearest_snap_point(cpos, _other, _sr)
                                if _sp is not None:
                                    cpos = _sp
                                smart_snap_guides = _alignment_guides_for_point(cpos, _other, _sr)
                            else:
                                smart_snap_guides = []
                        else:
                            smart_snap_guides = []
                    else:
                        # rotation/skew: clear positional alignment guides
                        smart_snap_guides = []
                    start_strokes = td.get("start_strokes", {})
                    bb0 = td.get("start_bbox")
                    mode = td.get("mode", "scale")
                    ang = bb0.get("angle", 0.0) if isinstance(bb0, dict) else 0.0
                    ca0, sa0 = math.cos(ang), math.sin(ang)
                    bcx = bb0["cx"] if isinstance(bb0, dict) else (bb0[0]+bb0[2])/2.0
                    bcy = bb0["cy"] if isinstance(bb0, dict) else (bb0[1]+bb0[3])/2.0
                    mods_cur = pygame.key.get_mods()
                    shift_held = bool(mods_cur & pygame.KMOD_SHIFT)
                    ctrl_held = bool(mods_cur & pygame.KMOD_CTRL)
                    def _local_around(origin, pt):
                        ox, oy = origin
                        dx, dy = pt[0] - ox, pt[1] - oy
                        return (dx*ca0 + dy*sa0, -dx*sa0 + dy*ca0)
                    is_rotate = (h == "rot") or h.startswith("rot_")
                    is_skew = h.startswith("skew_")
                    if is_rotate:
                        a0 = math.atan2(sy0 - cy, sx0 - cx)
                        a1 = math.atan2(cpos[1] - cy, cpos[0] - cx)
                        delta = a1 - a0
                        if ctrl_held:
                            step = math.radians(15.0)
                            delta = round(delta / step) * step
                        for i, st0 in start_strokes.items():
                            if 0 <= i < len(strokes):
                                strokes[i] = rotate_stroke_around(st0, cx, cy, delta)
                    elif is_skew:
                        # Skew around pivot/center in local axes
                        lmx, lmy = _local_around((cx, cy), cpos)
                        lsx, lsy = _local_around((cx, cy), (sx0, sy0))
                        skew_x = skew_y = 0.0
                        denom_y = lsy if abs(lsy) > 1e-6 else (1e-6 if lsy >= 0 else -1e-6)
                        denom_x = lsx if abs(lsx) > 1e-6 else (1e-6 if lsx >= 0 else -1e-6)
                        if h == "skew_n":
                            skew_x = clamp((lmx - lsx) / denom_y, -5.0, 5.0)
                        elif h == "skew_s":
                            skew_x = clamp((lmx - lsx) / denom_y, -5.0, 5.0)
                        elif h == "skew_e":
                            skew_y = clamp((lmy - lsy) / denom_x, -5.0, 5.0)
                        elif h == "skew_w":
                            skew_y = clamp((lmy - lsy) / denom_x, -5.0, 5.0)
                        for i, st0 in start_strokes.items():
                            if 0 <= i < len(strokes):
                                strokes[i] = skew_stroke_local(st0, (cx, cy), ang, skew_x, skew_y)
                    else:
                        # scale handles
                        # fixed point: opposite anchor in world (default) or pivot/center if Shift
                        if shift_held:
                            fx, fy = cx, cy
                        else:
                            lax, lay = bbox_handle_anchor_local(h, bb0)
                            fx = bcx + lax * ca0 - lay * sa0
                            fy = bcy + lax * sa0 + lay * ca0
                        def _safe_ratio(cur_d, start_d):
                            if abs(start_d) < 1e-6:
                                return 1.0 if abs(cur_d) < 1e-6 else (20.0 if cur_d > 0 else -20.0)
                            return cur_d / start_d
                        lmx, lmy = _local_around((fx, fy), cpos)
                        lsx, lsy = _local_around((fx, fy), (sx0, sy0))
                        su = sv = 1.0
                        if h in ("e", "w"):
                            su = _safe_ratio(lmx, lsx)
                            sv = 1.0
                        elif h in ("n", "s"):
                            sv = _safe_ratio(lmy, lsy)
                            su = 1.0
                        else:
                            # corner: Ctrl constrains aspect ratio, default free (Inkscape-like)
                            ru = _safe_ratio(lmx, lsx)
                            rv = _safe_ratio(lmy, lsy)
                            if ctrl_held:
                                sratio = ru if abs(ru - 1.0) >= abs(rv - 1.0) else rv
                                su = sv = sratio
                            else:
                                su, sv = ru, rv
                        su = clamp(su, -20.0, 20.0)
                        sv = clamp(sv, -20.0, 20.0)
                        # avoid total collapse
                        if abs(su) < 0.02: su = 0.02 if su >= 0 else -0.02
                        if abs(sv) < 0.02: sv = 0.02 if sv >= 0 else -0.02
                        for i, st0 in start_strokes.items():
                            if 0 <= i < len(strokes):
                                strokes[i] = scale_stroke_local(st0, (fx, fy), ang, su, sv)
                elif tool_mode == "selection" and drag_last is not None and selected_strokes and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    if selection_submode == "nodes" and selected_point is not None and len(selected_strokes) == 1:
                        only = next(iter(selected_strokes))
                        seg_i, pname = selected_point
                        if 0 <= only < len(strokes):
                            strokes[only] = set_stroke_point(strokes[only], seg_i, pname, cpos)
                        drag_last = cpos
                    elif selection_submode in ("transform", "nodes"):
                        # In nodes mode, dragging the stroke (not a point) moves it; curve mode has no drag-move here
                        if selection_submode == "nodes" and selected_point is not None:
                            pass
                        else:
                            dx = cpos[0] - drag_last[0]; dy = cpos[1] - drag_last[1]
                            if dx != 0 or dy != 0:
                                dx, dy, smart_snap_guides = _snap_move_delta(selected_strokes, dx, dy)
                            else:
                                smart_snap_guides = []
                            if dx != 0 or dy != 0:
                                for si in list(selected_strokes):
                                    if 0 <= si < len(strokes):
                                        strokes[si] = translate_stroke(strokes[si], dx, dy)
                                drag_last = (drag_last[0] + dx, drag_last[1] + dy)
                            else:
                                drag_last = cpos
                    else:
                        drag_last = cpos
                # (translation handled above when drag_last is set)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                if pan_drag is not None and not space_panning:
                    pan_drag = None
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if guide_drag is not None:
                    _rs = int(RULER_SIZE)
                    _on_ruler = (event.pos[1] <= TOP_BAR_H + _rs) or (event.pos[0] <= cfg.CANVAS_X + _rs)
                    if _on_ruler:
                        guides = remove_guide(guides, guide_drag.get("index", 0))
                    guide_drag = None
                    continue
                smart_snap_guides = []
                # Bezier pen: commit handle drag or close path on first-anchor release.
                if tool_mode == "draw" and draw_tool == "pen" and draw_shape == "pen" and bezier_pen is not None and bezier_pen.get("mouse_down"):
                    if bezier_pen.get("dragging_first"):
                        _bezier_pen_finish(close_path=True)
                        continue
                    else:
                        bezier_pen["mouse_down"] = False
                        bezier_pen["dragging"] = False
                        continue
                if cutting:
                    cutting = False
                    cpos = clamp_to_canvas(event.pos)
                    if not cut_points or math.hypot(cpos[0] - cut_points[-1][0],
                                                    cpos[1] - cut_points[-1][1]) >= 1.0:
                        cut_points.append(cpos)
                    if len(cut_points) >= 2:
                        only = None
                        if (tool_mode == "selection" and selection_submode == "curve"
                                and selected_strokes):
                            only = set(selected_strokes)
                        new_strokes, cut_idx = cut_strokes_with_path(
                            strokes, cut_points, only_indices=only,
                            gap=cut_gap / 2.0)
                        if cut_idx:
                            push_undo()
                            strokes[:] = new_strokes
                            if tool_mode == "selection":
                                # For single-piece replacements (gap 0) indices are
                                # preserved; for multi-piece splits, select affected
                                # strokes best-effort by mapping original indices.
                                sel_after = set()
                                base = 0
                                cut_set = set(cut_idx)
                                for oi in range(len(strokes) - 0):  # placeholder, recompute below
                                    pass
                                # Recompute mapping from original stroke index to new indices.
                                # We need original count; infer by reversing: iterate over
                                # original strokes isn't directly available, so approximate:
                                # if every cut produced exactly 1 piece total count matches
                                # original; otherwise fall back to selecting all new strokes
                                # in positions of cut regions is complex. Simpler: when in
                                # curve mode (single-stroke selection typical) select same
                                # indices as cut_idx; else leave selection cleared.
                                if selection_submode == "curve":
                                    selected_strokes = set(i for i in cut_idx if 0 <= i < len(strokes))
                                else:
                                    selected_strokes = set(i for i in cut_idx if 0 <= i < len(strokes))
                                selected_curve = None
                                selected_curves.clear()
                                if selection_submode == "curve":
                                    # One-shot action: turn the razor off so the
                                    # new curve halves can be clicked/selected.
                                    curve_cut_mode = False
                                    state["curve_cut_mode"] = False
                            selected_point = None
                            transform_drag = None
                    cut_points = []
                    continue
                if pan_drag is not None and space_panning:
                    pan_drag = None
                pivot_drag = None
                if pending_transform_toggle is not None and tool_mode == "selection" and selection_submode == "transform":
                    if not pending_transform_toggle.get("moved") and selected_strokes:
                        transform_handle_mode = "rotate" if transform_handle_mode == "scale" else "scale"
                    pending_transform_toggle = None
                transform_drag = None
                gradient_drag = None
                if marquee_select is not None and tool_mode == "selection":
                    r = normalize_rect(marquee_select["start"], marquee_select.get("current", marquee_select["start"]))
                    if abs(r[2]-r[0]) >= 3 or abs(r[3]-r[1]) >= 3:
                        picked = {i for i, st in enumerate(strokes) if rects_intersect(r, stroke_bbox(st))}
                        picked = expand_group_selection(strokes, picked)
                        if marquee_select.get("add"):
                            selected_strokes |= picked
                        else:
                            selected_strokes = picked
                    elif not marquee_select.get("add"):
                        selected_strokes.clear()
                    marquee_select = None
                elif redrawing_curve is not None:
                    if redrawing_curve.get("started"):
                        si = redrawing_curve.get("stroke_idx")
                        comp_i = redrawing_curve.get("comp_idx", redrawing_curve.get("seg_idx"))
                        pts = list(redrawing_curve.get("points", []))
                        fixed_start = redrawing_curve.get("fixed_start")
                        fixed_end = redrawing_curve.get("fixed_end")
                        if fixed_start is not None and pts:
                            pts[0] = tuple(fixed_start)
                        cpos = clamp_to_canvas(event.pos)
                        shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                        keys = pygame.key.get_pressed()
                        straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
                        pts = finalize_drawing_points(pts, cpos, strokes, snap_radius(), shift_held, straight_line, fixed_end=fixed_end)
                        if fixed_start is not None:
                            if pts:
                                pts[0] = tuple(fixed_start)
                            else:
                                pts = [tuple(fixed_start)]
                        if fixed_end is not None:
                            if len(pts) == 1:
                                pts.append(tuple(fixed_end))
                            elif pts:
                                pts[-1] = tuple(fixed_end)
                        if si is not None and comp_i is not None and 0 <= si < len(strokes) and len(pts) >= 2:
                            push_undo()
                            strokes[si] = redraw_stroke_component(strokes[si], comp_i, pts)
                        redrawing_curve = None
                    else:
                        # Redraw mode armed but drawing not started yet (e.g. released on button); wait for canvas drag
                        pass
                elif drawing and tool_mode == "draw" and draw_tool == "pen":
                    drawing = False
                    cpos = clamp_to_canvas(event.pos)
                    shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                    keys = pygame.key.get_pressed()
                    straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
                    current_points = finalize_drawing_points(current_points, cpos, strokes, snap_radius(), shift_held, straight_line)
                    if len(current_points) >= 2:
                        raw = list(current_points)
                        shape_segs = None
                        shape_raw = None
                        if draw_shape != "freehand":
                            shape_segs, shape_raw = shape_from_doodle(
                                current_points, draw_shape,
                                variant=triangle_variant if draw_shape == "triangle" else None,
                                corner_radius=corner_radius if draw_shape in ("rect", "square") else None,
                                segments=ellipse_segments if draw_shape in ("ellipse", "circle") else None,
                                constrain=line_constrain if draw_shape == "line" else False,
                                sides=polygon_sides if draw_shape == "polygon" else None,
                                star_points=star_points if draw_shape == "star" else None,
                                star_inner_ratio=star_inner_ratio if draw_shape == "star" else None,
                            )
                        if shape_segs:
                            # Create a collection of connected curves/strokes (one per edge/segment) when possible
                            push_undo()
                            algo_name = f"shape:{draw_shape}"
                            base_raw = shape_raw if shape_raw is not None else list(current_points)
                            new_strokes = []
                            for seg in shape_segs:
                                st = new_stroke([seg], algorithm=algo_name)
                                comp = {
                                    "raw_points": [tuple(seg[0]), tuple(seg[3])],
                                    "draw_max_points": int(max_points_per_curve),
                                    "algorithm": algo_name,
                                    "segs": [seg],
                                }
                                st["components"] = [comp]
                                new_strokes.append(st)
                            if new_strokes:
                                # connect edges together so they form one shape with sharp corners at joins
                                shape_stroke = new_strokes[0]
                                for extra in new_strokes[1:]:
                                    shape_stroke = merge_connected_strokes([shape_stroke, extra])[0]
                                shape_stroke = _close_path_if_needed(shape_stroke)
                                if draw_shape == "line" and line_arrow:
                                    shape_stroke["arrow_end"] = True
                                strokes.append(shape_stroke)
                                strokes = merge_connected_strokes(strokes)
                                if (draw_shape == "line" and line_arrow and strokes
                                        and not any(isinstance(s, dict) and s.get("arrow_end")
                                                    for s in strokes)):
                                    # merging rebuilt the stroke dict; keep the arrowhead
                                    strokes[-1]["arrow_end"] = True
                            selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
                        elif straight_line:
                            push_undo()
                            p0 = tuple(current_points[0])
                            p3 = tuple(current_points[-1])
                            c1 = (p0[0] + (p3[0] - p0[0]) / 3.0, p0[1] + (p3[1] - p0[1]) / 3.0)
                            c2 = (p0[0] + 2.0 * (p3[0] - p0[0]) / 3.0, p0[1] + 2.0 * (p3[1] - p0[1]) / 3.0)
                            beziers = [(p0, c1, c2, p3)]
                            raw = [p0, p3]
                            algo_name = trace_algorithm
                            st = new_stroke(beziers, algorithm=algo_name)
                            comp = {
                                "raw_points": [tuple(p) for p in raw],
                                "draw_max_points": int(max_points_per_curve),
                                "algorithm": algo_name,
                                "segs": list(beziers),
                            }
                            st["components"] = [comp]
                            st = _close_path_if_needed(st)
                            strokes.append(st)
                            strokes = merge_connected_strokes(strokes)
                            selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
                        else:
                            beziers = stroke_to_beziers(
                                current_points, simplify_epsilon=2.5, tension=0.0,
                                max_points=max_points_per_curve, algorithm=trace_algorithm,
                            )
                            algo_name = trace_algorithm
                            if beziers:
                                push_undo()
                                st = new_stroke(beziers, algorithm=algo_name)
                                comp = {
                                    "raw_points": [tuple(p) for p in raw],
                                    "draw_max_points": int(max_points_per_curve),
                                    "algorithm": algo_name,
                                    "segs": list(beziers),
                                }
                                st["components"] = [comp]
                                st = _close_path_if_needed(st)
                                strokes.append(st)
                                strokes = merge_connected_strokes(strokes)
                                selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
                    current_points = []
                elif drawing and tool_mode == "draw" and draw_tool == "eraser":
                    drawing = False
                    current_points = []
                drag_last = None; selected_point = None; transform_drag = None; gradient_drag = None; pivot_drag = None
                picker_drag_sv = False; picker_drag_hue = False; picker_drag_alpha = False; ref_opacity_drag = False; fill_stop_pos_drag = False
                obj_opacity_drag = False
                state["obj_opacity_drag"] = False
                bucket_picker_drag = None
                wave_slider_drag = None
                wave_custom_drag = None
                state["wave_custom_drag"] = None
                state["picker_drag_sv"] = False; state["picker_drag_hue"] = False; state["picker_drag_alpha"] = False; state["fill_stop_pos_drag"] = False
                ref_drag = None
                max_points_per_curve = slider.value

        # Draw scene (Cairo) and blit at canvas offset
        active = current_points if (drawing and tool_mode == "draw") else (redrawing_curve.get("points") if redrawing_curve else None)
        # While placing text, render the typed buffer as a live editable outline.
        render_strokes = strokes
        text_preview_index = None
        if workspace == "library" and shape_states:
            # Library workspace: browse the saved shape states as canvas content.
            _lib = []
            for _sid, _sdef in shape_states.items():
                if not isinstance(_sdef, dict) or not isinstance(_sdef.get("strokes"), list):
                    continue
                _org = _sdef.get("origin") or [0.0, 0.0]
                try:
                    _ox = float(_org[0]); _oy = float(_org[1])
                except Exception:
                    _ox = _oy = 0.0
                for _st in _sdef["strokes"]:
                    if not isinstance(_st, dict):
                        continue
                    _n = copy.deepcopy(_st)
                    _n.pop("shape_state_id", None); _n.pop("shape_state_is_master", None); _n.pop("shape_state_instance_id", None)
                    try:
                        _n = translate_stroke(_n, _ox, _oy)
                    except Exception:
                        pass
                    _lib.append(_n)
            render_strokes = _lib
        if text_entry is not None and str(text_entry.get("text", "")):
            try:
                _tc = hsv_to_rgb(picker_h, picker_s, picker_v)
                _preview = new_text_stroke(text_entry["text"], text_entry["x"],
                                           text_entry["y"], text_entry["family"],
                                           text_entry["size"],
                                           color=(_tc[0], _tc[1], _tc[2], 1.0))
                render_strokes = list(strokes) + [_preview]
                text_preview_index = len(render_strokes) - 1
            except Exception:
                render_strokes = strokes
        _eff_pivot = None
        _grad_edit_info = None
        if tool_mode == "selection" and selection_submode == "transform" and selected_strokes:
            _pobb = combined_obb(strokes, selected_strokes)
            if _pobb:
                _eff_pivot = pivot_pos if pivot_pos is not None else (_pobb["cx"], _pobb["cy"])
            if state.get("color_target", color_target) == "fill":
                for _gsi in sorted(selected_strokes):
                    if 0 <= _gsi < len(strokes):
                        _gst = strokes[_gsi]
                        _gfg = _gst.get("fill_gradient") if isinstance(_gst, dict) else None
                        try:
                            _gfg = get_fill_gradient(_gst) or _gfg
                        except Exception:
                            pass
                        if isinstance(_gfg, dict) and str(_gfg.get("type")) in ("linear", "radial", "conic", "spiral", "diamond", "square"):
                            try:
                                _grad_edit_info = gradient_edit_handles(_gst, _gfg)
                                if isinstance(_grad_edit_info, dict):
                                    _grad_edit_info["stroke_i"] = _gsi
                            except Exception:
                                _grad_edit_info = None
                            break
        # Set OBB on selection (not at creation).
        for _si in list(selected_strokes):
            if 0 <= _si < len(strokes):
                try:
                    get_stroke_obb(strokes[_si])
                except Exception:
                    pass
        draw_scene(
            cairo_surface, render_strokes, active, snap_point=hover_snap,
            selected_indices=selected_strokes, edit_mode=(tool_mode == "selection"),
            selection_submode=selection_submode, selected_curve=selected_curve,
            selected_curves=set(selected_curves),
            snap_kind=hover_snap_kind, redrawing_curve=redrawing_curve,
            ref_img=reference_image,
            pivot_pos=_eff_pivot,
            transform_handle_mode=transform_handle_mode,
            gradient_edit_info=_grad_edit_info,
            guides=guides,
            smart_guides=smart_snap_guides,
            bezier_pen=bezier_pen,
            artboards=artboards,
            active_artboard=active_artboard,
        )
        frame = surface_to_pygame(cairo_surface)
        screen.fill(CANVAS_BACKDROP)
        screen.blit(frame, (cfg.CANVAS_X, TOP_BAR_H))

        # Rulers + guides overlay (view-only).
        if getattr(cfg, "SHOW_RULERS", False):
            _rs = int(RULER_SIZE)
            _vh = cfg.canvas_viewport_height()
            _top = pygame.Rect(cfg.CANVAS_X, TOP_BAR_H, cfg.CANVAS_W, _rs)
            _left = pygame.Rect(cfg.CANVAS_X, TOP_BAR_H, _rs, _vh)
            pygame.draw.rect(screen, RULER_BG_RGB, _top)
            pygame.draw.rect(screen, RULER_BG_RGB, _left)
            pygame.draw.line(screen, PANEL_BORDER, (_top.x, _top.bottom - 1),
                             (_top.right, _top.bottom - 1), BORDER_WIDTH)
            pygame.draw.line(screen, PANEL_BORDER, (_left.right - 1, _left.y),
                             (_left.right - 1, _left.bottom), BORDER_WIDTH)
            _z = float(getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0)
            _px = float(getattr(cfg, "VIEW_PAN_X", 0.0))
            _py = float(getattr(cfg, "VIEW_PAN_Y", 0.0))
            _wx0 = (0.0 - _px) / _z
            _wx1 = (float(cfg.CANVAS_W) - _px) / _z
            _wy0 = (0.0 - _py) / _z
            _wy1 = (float(_vh) - _py) / _z
            _step_x = ruler_ticks(_wx0, _wx1, 10.0, min_pixels=64.0, zoom=_z)
            _step_y = ruler_ticks(_wy0, _wy1, 10.0, min_pixels=48.0, zoom=_z)
            for _x in grid_positions(_wx0, _wx1, _step_x):
                _sx = int(_x * _z + _px + cfg.CANVAS_X)
                if _sx <= _top.x or _sx >= _top.right:
                    continue
                pygame.draw.line(screen, RULER_TICK_RGB, (_sx, _top.bottom - 5),
                                 (_sx, _top.bottom - 1), BORDER_WIDTH)
                _lbl = ruler_font.render(str(int(round(_x))), True, RULER_TEXT_RGB)
                screen.blit(_lbl, (_sx + 2, _top.y + 1))
            for _y in grid_positions(_wy0, _wy1, _step_y):
                _sy = int(_y * _z + _py + TOP_BAR_H)
                if _sy <= _left.y or _sy >= _left.bottom:
                    continue
                pygame.draw.line(screen, RULER_TICK_RGB, (_left.right - 5, _sy),
                                 (_left.right - 1, _sy), BORDER_WIDTH)
                _lbl = ruler_font.render(str(int(round(_y))), True, RULER_TEXT_RGB)
                _lbl = pygame.transform.rotate(_lbl, 90)
                screen.blit(_lbl, (_left.x + 1, _sy + 2))

        # Cutter swipe preview (razor line across the canvas).
        if cutting and len(cut_points) >= 2:
            pts = [(int(to_screen(p)[0]), int(to_screen(p)[1])) for p in cut_points]
            pygame.draw.lines(screen, CUT_COLOR, False, pts, int(EDITOR_LINE_WIDTH_BOLD))
            pygame.draw.circle(screen, SURFACE, pts[0], CUT_HANDLE_RADIUS)
            pygame.draw.circle(screen, CUT_COLOR, pts[0], CUT_HANDLE_RADIUS, BORDER_WIDTH)

        # marquee selection overlay
        if marquee_select is not None and tool_mode == "selection":
            r = normalize_rect(marquee_select["start"], marquee_select.get("current", marquee_select["start"]))
            rx1, ry1, rx2, ry2 = r
            s1 = to_screen((rx1, ry1)); s2 = to_screen((rx2, ry2))
            rect = pygame.Rect(int(min(s1[0],s2[0])), int(min(s1[1],s2[1])), int(abs(s2[0]-s1[0])), int(abs(s2[1]-s1[1])))
            if rect.w > 0 and rect.h > 0:
                overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                overlay.fill(SELECTION_FILL)
                screen.blit(overlay, rect.topleft)
                pygame.draw.rect(screen, SELECTION_BORDER, rect, BORDER_WIDTH)

        # Need swatch rects for this frame's layout - draw panel and capture by recomputing? we passed refs in state but draw_panel fills them during draw
        draw_left_toolbar(screen, mouse_pos, tool_mode, btn_draw, btn_select, btn_undo, btn_redo, bool(undo_stack), bool(redo_stack))
        if not panel_collapsed:
            draw_panel(screen, fonts, mouse_pos, state)
        draw_panel_toggle(screen, mouse_pos, state)
        draw_bottom_shape_toolbar(screen, fonts, mouse_pos, state)
        draw_shape_context_menu(screen, fonts, mouse_pos, state)
        draw_marker_dropdown(screen, fonts, mouse_pos, state)

        # sync picker state/rects from panel for next frame's event handling
        picker_h = state.get("picker_h", picker_h)
        picker_s = state.get("picker_s", picker_s)
        picker_v = state.get("picker_v", picker_v)
        picker_rects["sv"] = state.get("sv_rect", picker_rects["sv"])
        picker_rects["hue"] = state.get("hue_rect", picker_rects["hue"])
        picker_rects["tab_stroke"] = state.get("tab_stroke_rect", picker_rects["tab_stroke"])
        picker_rects["tab_fill"] = state.get("tab_fill_rect", picker_rects["tab_fill"])
        picker_rects["nofill"] = state.get("nofill_rect", picker_rects["nofill"])
        picker_rects["alpha"] = state.get("alpha_rect", picker_rects["alpha"])
        fill_type_prev_rect_cache = state.get("fill_type_prev_rect", fill_type_prev_rect_cache)
        fill_type_next_rect_cache = state.get("fill_type_next_rect", fill_type_next_rect_cache)
        fill_stop_rects_cache = dict(state.get("fill_stop_rects", fill_stop_rects_cache) or {})
        fill_stop_add_rect_cache = state.get("fill_stop_add_rect", fill_stop_add_rect_cache)
        fill_stop_remove_rect_cache = state.get("fill_stop_remove_rect", fill_stop_remove_rect_cache)
        fill_stop_pos_rect_cache = state.get("fill_stop_pos_rect", fill_stop_pos_rect_cache)
        pattern_type_rect_cache = state.get("pattern_type_rect", pattern_type_rect_cache)
        pattern_size_minus_rect_cache = state.get("pattern_size_minus_rect", pattern_size_minus_rect_cache)
        pattern_size_plus_rect_cache = state.get("pattern_size_plus_rect", pattern_size_plus_rect_cache)
        fill_gradient_stop = int(state.get("fill_gradient_stop", fill_gradient_stop) or 0)
        fill_stop_pos_drag = bool(state.get("fill_stop_pos_drag", fill_stop_pos_drag))
        trace_algo_prev_rect_cache = state.get("trace_algo_prev_rect", trace_algo_prev_rect_cache)
        trace_algo_next_rect_cache = state.get("trace_algo_next_rect", trace_algo_next_rect_cache)
        draw_tool_prev_rect_cache = state.get("draw_tool_prev_rect", draw_tool_prev_rect_cache)
        draw_tool_next_rect_cache = state.get("draw_tool_next_rect", draw_tool_next_rect_cache)
        draw_shape_rects_cache = state.get("draw_shape_rects", draw_shape_rects_cache)
        panel_toggle_rect_cache = state.get("panel_toggle_rect", panel_toggle_rect_cache)
        panel_collapsed = bool(state.get("panel_collapsed", panel_collapsed))
        shape_menu_key = state.get("shape_menu_key", shape_menu_key)
        shape_menu_anchor = state.get("shape_menu_anchor", shape_menu_anchor)
        shape_menu_rect = state.get("shape_menu_rect", shape_menu_rect)
        shape_menu_item_rects = state.get("shape_menu_item_rects", shape_menu_item_rects)
        draw_tool_pen_rect_cache = state.get("draw_tool_pen_rect", draw_tool_pen_rect_cache)
        draw_tool_eraser_rect_cache = state.get("draw_tool_eraser_rect", draw_tool_eraser_rect_cache)
        draw_tool_bucket_rect_cache = state.get("draw_tool_bucket_rect", draw_tool_bucket_rect_cache)
        draw_tool_cutter_rect_cache = state.get("draw_tool_cutter_rect", draw_tool_cutter_rect_cache)
        bucket_picker_h = state.get("bucket_picker_h", bucket_picker_h)
        bucket_picker_s = state.get("bucket_picker_s", bucket_picker_s)
        bucket_picker_v = state.get("bucket_picker_v", bucket_picker_v)
        bucket_sv_rect_cache = state.get("bucket_sv_rect", bucket_sv_rect_cache)
        bucket_hue_rect_cache = state.get("bucket_hue_rect", bucket_hue_rect_cache)
        bucket_swatch_rects_cache = state.get("bucket_swatch_rects", bucket_swatch_rects_cache)
        snap_toggle_rect_cache = state.get("snap_toggle_rect", snap_toggle_rect_cache)
        nodes_mode_prev_rect_cache = state.get("nodes_mode_prev_rect", nodes_mode_prev_rect_cache)
        nodes_mode_next_rect_cache = state.get("nodes_mode_next_rect", nodes_mode_next_rect_cache)
        elev_front_rect_cache = state.get("elev_front_rect", elev_front_rect_cache)
        elev_forward_rect_cache = state.get("elev_forward_rect", elev_forward_rect_cache)
        elev_backward_rect_cache = state.get("elev_backward_rect", elev_backward_rect_cache)
        elev_back_rect_cache = state.get("elev_back_rect", elev_back_rect_cache)
        bool_union_rect_cache = state.get("bool_union_rect", bool_union_rect_cache)
        bool_intersect_rect_cache = state.get("bool_intersect_rect", bool_intersect_rect_cache)
        bool_subtract_rect_cache = state.get("bool_subtract_rect", bool_subtract_rect_cache)
        bool_exclude_rect_cache = state.get("bool_exclude_rect", bool_exclude_rect_cache)
        distribute_h_rect_cache = state.get("distribute_h_rect", distribute_h_rect_cache)
        distribute_v_rect_cache = state.get("distribute_v_rect", distribute_v_rect_cache)
        path_close_rect_cache = state.get("path_close_rect", path_close_rect_cache)
        path_reverse_rect_cache = state.get("path_reverse_rect", path_reverse_rect_cache)
        path_add_rect_cache = state.get("path_add_rect", path_add_rect_cache)
        path_delete_rect_cache = state.get("path_delete_rect", path_delete_rect_cache)
        path_smooth_rect_cache = state.get("path_smooth_rect", path_smooth_rect_cache)
        path_corner_rect_cache = state.get("path_corner_rect", path_corner_rect_cache)
        path_expand_rect_cache = state.get("path_expand_rect", path_expand_rect_cache)
        obj_opacity_rect_cache = state.get("obj_opacity_rect", obj_opacity_rect_cache)
        shadow_toggle_rect_cache = state.get("shadow_toggle_rect", shadow_toggle_rect_cache)
        shadow_blur_minus_rect_cache = state.get("shadow_blur_minus_rect", shadow_blur_minus_rect_cache)
        shadow_blur_plus_rect_cache = state.get("shadow_blur_plus_rect", shadow_blur_plus_rect_cache)
        cap_prev_rect_cache = state.get("cap_prev_rect", cap_prev_rect_cache)
        cap_next_rect_cache = state.get("cap_next_rect", cap_next_rect_cache)
        join_prev_rect_cache = state.get("join_prev_rect", join_prev_rect_cache)
        join_next_rect_cache = state.get("join_next_rect", join_next_rect_cache)
        dash_prev_rect_cache = state.get("dash_prev_rect", dash_prev_rect_cache)
        dash_next_rect_cache = state.get("dash_next_rect", dash_next_rect_cache)
        marker_start_rect_cache = state.get("marker_start_rect", marker_start_rect_cache)
        marker_end_rect_cache = state.get("marker_end_rect", marker_end_rect_cache)
        marker_dropdown = state.get("marker_dropdown", marker_dropdown)
        marker_dropdown_rect = state.get("marker_dropdown_rect", marker_dropdown_rect)
        marker_dropdown_item_rects = dict(state.get("marker_dropdown_item_rects", marker_dropdown_item_rects) or {})
        width_profile_prev_rect_cache = state.get("width_profile_prev_rect", width_profile_prev_rect_cache)
        width_profile_next_rect_cache = state.get("width_profile_next_rect", width_profile_next_rect_cache)
        obj_opacity_drag = state.get("obj_opacity_drag", obj_opacity_drag)
        xform_field_focus = state.get("xform_field_focus", xform_field_focus)
        xform_field_buffer = state.get("xform_field_buffer", xform_field_buffer)
        xform_x_rect_cache = state.get("xform_x_rect", xform_x_rect_cache)
        xform_y_rect_cache = state.get("xform_y_rect", xform_y_rect_cache)
        xform_w_rect_cache = state.get("xform_w_rect", xform_w_rect_cache)
        xform_h_rect_cache = state.get("xform_h_rect", xform_h_rect_cache)
        xform_r_rect_cache = state.get("xform_r_rect", xform_r_rect_cache)
        xform_xm_rect_cache = state.get("xform_xm_rect", xform_xm_rect_cache)
        xform_xp_rect_cache = state.get("xform_xp_rect", xform_xp_rect_cache)
        xform_ym_rect_cache = state.get("xform_ym_rect", xform_ym_rect_cache)
        xform_yp_rect_cache = state.get("xform_yp_rect", xform_yp_rect_cache)
        xform_wm_rect_cache = state.get("xform_wm_rect", xform_wm_rect_cache)
        xform_wp_rect_cache = state.get("xform_wp_rect", xform_wp_rect_cache)
        xform_hm_rect_cache = state.get("xform_hm_rect", xform_hm_rect_cache)
        xform_hp_rect_cache = state.get("xform_hp_rect", xform_hp_rect_cache)
        xform_rm_rect_cache = state.get("xform_rm_rect", xform_rm_rect_cache)
        xform_rp_rect_cache = state.get("xform_rp_rect", xform_rp_rect_cache)
        export_dialog_rects = dict(state.get("export_dialog_rects", export_dialog_rects) or {})
        text_edit_rect_cache = state.get("text_edit_rect", text_edit_rect_cache)
        text_font_rect_cache = state.get("text_font_rect", text_font_rect_cache)
        text_size_minus_rect_cache = state.get("text_size_minus_rect", text_size_minus_rect_cache)
        text_size_plus_rect_cache = state.get("text_size_plus_rect", text_size_plus_rect_cache)
        text_on_path_rect_cache = state.get("text_on_path_rect", text_on_path_rect_cache)
        text_off_path_rect_cache = state.get("text_off_path_rect", text_off_path_rect_cache)
        mirror_h_rect_cache = state.get("mirror_h_rect", mirror_h_rect_cache)
        mirror_v_rect_cache = state.get("mirror_v_rect", mirror_v_rect_cache)
        align_left_rect_cache = state.get("align_left_rect", align_left_rect_cache)
        align_hcenter_rect_cache = state.get("align_hcenter_rect", align_hcenter_rect_cache)
        align_right_rect_cache = state.get("align_right_rect", align_right_rect_cache)
        align_top_rect_cache = state.get("align_top_rect", align_top_rect_cache)
        align_vmiddle_rect_cache = state.get("align_vmiddle_rect", align_vmiddle_rect_cache)
        align_bottom_rect_cache = state.get("align_bottom_rect", align_bottom_rect_cache)
        curve_hide_rect_cache = state.get("curve_hide_rect", curve_hide_rect_cache)
        curve_redraw_rect_cache = state.get("curve_redraw_rect", curve_redraw_rect_cache)
        curve_cut_rect_cache = state.get("curve_cut_rect", curve_cut_rect_cache)
        curve_join_rect_cache = state.get("curve_join_rect", curve_join_rect_cache)
        eyedropper_rect_cache = state.get("eyedropper_rect", eyedropper_rect_cache)
        wave_toggle_rect_cache = state.get("wave_toggle_rect", wave_toggle_rect_cache)
        wave_add_rect_cache = state.get("wave_add_rect", wave_add_rect_cache)
        displacement_add_rect_cache = state.get("displacement_add_rect", displacement_add_rect_cache)
        repeat_add_rect_cache = state.get("repeat_add_rect", repeat_add_rect_cache)
        thickness_add_rect_cache = state.get("thickness_add_rect", thickness_add_rect_cache)
        wave_remove_rect_cache = state.get("wave_remove_rect", wave_remove_rect_cache)
        wave_bake_rect_cache = state.get("wave_bake_rect", wave_bake_rect_cache)
        wave_shape_prev_rect_cache = state.get("wave_shape_prev_rect", wave_shape_prev_rect_cache)
        wave_shape_next_rect_cache = state.get("wave_shape_next_rect", wave_shape_next_rect_cache)
        displacement_profile_rects_cache = state.get("displacement_profile_rects", displacement_profile_rects_cache)
        displacement_affect_rects_cache = state.get("displacement_affect_rects", displacement_affect_rects_cache)
        wave_formula_rect_cache = state.get("wave_formula_rect", wave_formula_rect_cache)
        wave_formula_focus = state.get("wave_formula_focus", wave_formula_focus)
        wave_custom_draw = state.get("wave_custom_draw", wave_custom_draw)
        repeat_pick_mode = state.get("repeat_pick_mode", repeat_pick_mode)
        repeat_pick_target = state.get("repeat_pick_target", repeat_pick_target)
        wave_custom_box_rect_cache = state.get("wave_custom_box_rect", wave_custom_box_rect_cache)
        wave_smooth_rect_cache = state.get("wave_smooth_rect", wave_smooth_rect_cache)
        wave_clear_rect_cache = state.get("wave_clear_rect", wave_clear_rect_cache)
        wave_done_rect_cache = state.get("wave_done_rect", wave_done_rect_cache)
        repeat_pick_curve_rect_cache = state.get("repeat_pick_curve_rect", repeat_pick_curve_rect_cache)
        wave_reverse_rect_cache = state.get("wave_reverse_rect", wave_reverse_rect_cache)
        wave_clamp_rect_cache = state.get("wave_clamp_rect", wave_clamp_rect_cache)
        wave_custom_drag = state.get("wave_custom_drag", wave_custom_drag)
        wave_active_index = int(state.get("wave_active_index", wave_active_index) or 0)
        wave_row_rects_cache = state.get("wave_row_rects", wave_row_rects_cache)
        wave_custom_finished = bool(state.get("wave_custom_finished", wave_custom_finished))
        panel_scroll = int(state.get("panel_scroll", panel_scroll) or 0)
        export_scale = float(state.get("export_scale", export_scale) or 1.0)
        export_dpi = int(state.get("export_dpi", export_dpi) or 300)
        _content_bottom = int(state.get("panel_content_bottom", 0) or 0)
        _max_scroll = max(0, _content_bottom + 24 - (cfg.HEIGHT - TOP_BAR_H))
        panel_scroll = max(0, min(panel_scroll, _max_scroll))
        wave_slider_rects_cache = state.get("wave_slider_rects", wave_slider_rects_cache)
        ref_load_rect_cache = state.get("ref_load_rect", ref_load_rect_cache)
        ref_vis_rect_cache = state.get("ref_vis_rect", ref_vis_rect_cache)
        ref_clear_rect_cache = state.get("ref_clear_rect", ref_clear_rect_cache)
        ref_opacity_rect_cache = state.get("ref_opacity_rect", ref_opacity_rect_cache)
        swatch_rects_cache["stroke"] = list(state.get("stroke_swatch_rects", swatch_rects_cache["stroke"]))
        swatch_rects_cache["fill"] = list(state.get("fill_swatch_rects", swatch_rects_cache["fill"]))

        # sync width slider to selected on selection changes shown next frame (simple keep)
        if tool_mode == "selection" and selected_strokes and not width_slider.dragging:
            primary_i = sorted(selected_strokes)[0]
            if 0 <= primary_i < len(strokes):
                width_slider.value = int(round(strokes[primary_i].get("stroke_width", 3)))

        # Top menu bar -- one data-driven source for all menus and dropdowns.
        menu_bar_rects, menu_item_rects = draw_menu_bar(
            screen, font_small, mouse_pos, menu_open, state=state)
        if help_open:
            draw_shortcuts_overlay(screen, font, font_small)
        if export_dialog_open:
            draw_export_dialog(screen, font, font_small, mouse_pos, state)

        pygame.display.flip()
        clock.tick(120)

    pygame.quit()
    return 0
