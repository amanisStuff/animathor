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
from models.geometry import bbox_handle_anchor_local, bbox_handle_local_positions
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
    pivot_pos = None  # custom rotation/scale pivot (world coords); None = bbox center
    pivot_drag = None  # {"offset": (dx,dy)} while dragging pivot
    pending_transform_toggle = None  # click-on-selected-body candidate to toggle scale/rotate
    prev_selection_set = set()
    marquee_select = None  # {"start": (x,y), "current": (x,y), "add": bool}
    max_points_per_curve = 4
    boost_points = False
    NORMAL_MAX_POINTS = 5
    BOOST_MAX_POINTS = 100
    trace_algorithm = "fit"  # "fit", "catmull-rom", "single" (per new stroke)
    draw_shape = "freehand"  # "freehand" or standard shape key from DRAW_SHAPES
    triangle_variant = "isosceles"  # "isosceles", "right", "equilateral"
    line_constrain = False  # snap line shapes to 45-degree directions
    line_arrow = False  # draw an arrowhead at the end of line shapes
    corner_radius = 0  # percent of the rect/square min side (0-50)
    ellipse_segments = 4  # bezier arcs used for ellipse/circle
    draw_tool = "pen"  # "pen", "eraser", "bucket", or "cutter"
    cutting = False  # razor swipe in progress
    cut_points = []  # canvas-space points of the swipe
    cut_gap = 0  # optional visible gap left by the razor (canvas px, total)
    curve_cut_mode = False  # Split curve toggle in selection Curve mode
    eyedropper_pick = False  # one-shot style picker in selection mode
    selected_curves = set()  # set of (stroke_idx, comp_idx) in curve mode

    font = pygame.font.SysFont(None, 24)
    font_small = pygame.font.SysFont(None, 20)
    font_title = pygame.font.SysFont(None, 30)
    fonts = (font, font_small, font_title)

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
    trace_algo_rects_cache = {}
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
    nodes_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_front_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_forward_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_backward_rect_cache = pygame.Rect(0, 0, 0, 0)
    elev_back_rect_cache = pygame.Rect(0, 0, 0, 0)
    bool_union_rect_cache = pygame.Rect(0, 0, 0, 0)
    bool_intersect_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_hide_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_redraw_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_cut_rect_cache = pygame.Rect(0, 0, 0, 0)
    curve_join_rect_cache = pygame.Rect(0, 0, 0, 0)
    eyedropper_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_toggle_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_add_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_remove_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_shape_rects_cache = {}
    wave_formula_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_formula_focus = False
    wave_custom_draw = False
    wave_custom_box_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_smooth_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_reverse_rect_cache = pygame.Rect(0, 0, 0, 0)
    wave_custom_drag = None
    wave_active_index = 0
    wave_row_rects_cache = []
    wave_custom_finished = False
    wave_slider_rects_cache = {}
    wave_slider_drag = None
    panel_scroll = 0
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
    menu_open = None
    menu_bar_rect = pygame.Rect(0, 0, 0, 0)
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
        # reset custom pivot and transform mode when selection is cleared or membership changes
        if not selected_strokes or selected_strokes != prev_selection_set:
            pivot_pos = None
            transform_handle_mode = "scale"
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
        state = {
            "tool_mode": tool_mode, "max_points": max_points_per_curve, "boost_points": boost_points,
            "snap_enabled": snap_enabled,
            "NORMAL_MAX_POINTS": NORMAL_MAX_POINTS, "BOOST_MAX_POINTS": BOOST_MAX_POINTS,
            "slider": slider, "width_slider": width_slider, "buttons": buttons,
            "stroke_count": len(strokes), "selected_strokes": set(selected_strokes), "selected_obj": sel_obj,
            "stroke_swatch_rects": stroke_swatch_rects, "fill_swatch_rects": fill_swatch_rects,
            "color_target": color_target, "picker_h": picker_h, "picker_s": picker_s, "picker_v": picker_v,
            "picker_drag_sv": picker_drag_sv, "picker_drag_hue": picker_drag_hue, "picker_drag_alpha": picker_drag_alpha,
            "sv_rect": picker_rects["sv"], "hue_rect": picker_rects["hue"],
            "tab_stroke_rect": picker_rects["tab_stroke"], "tab_fill_rect": picker_rects["tab_fill"],
            "nofill_rect": picker_rects["nofill"], "alpha_rect": picker_rects["alpha"],
            "selection_submode": selection_submode,
            "nodes_toggle_rect": nodes_toggle_rect_cache,
            "elev_front_rect": elev_front_rect_cache,
            "elev_forward_rect": elev_forward_rect_cache,
            "elev_backward_rect": elev_backward_rect_cache,
            "elev_back_rect": elev_back_rect_cache,
            "bool_union_rect": bool_union_rect_cache,
            "bool_intersect_rect": bool_intersect_rect_cache,
            "trace_algorithm": trace_algorithm,
            "trace_algo_rects": trace_algo_rects_cache,
            "draw_shape": draw_shape,
            "draw_shape_rects": draw_shape_rects_cache,
            "draw_shape_variant": triangle_variant,
            "line_constrain": line_constrain,
            "line_arrow": line_arrow,
            "corner_radius": corner_radius,
            "ellipse_segments": ellipse_segments,
            "shape_menu_key": shape_menu_key,
            "shape_menu_anchor": shape_menu_anchor,
            "shape_menu_rect": shape_menu_rect,
            "shape_menu_item_rects": shape_menu_item_rects,
            "panel_collapsed": panel_collapsed,
            "panel_toggle_rect": panel_toggle_rect_cache,
            "draw_tool": draw_tool,
            "draw_tool_pen_rect": draw_tool_pen_rect_cache,
            "draw_tool_eraser_rect": draw_tool_eraser_rect_cache,
            "draw_tool_bucket_rect": draw_tool_bucket_rect_cache,
            "draw_tool_cutter_rect": draw_tool_cutter_rect_cache,
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
            "wave_remove_rect": wave_remove_rect_cache,
            "wave_shape_rects": wave_shape_rects_cache,
            "wave_formula_rect": wave_formula_rect_cache,
            "wave_formula_focus": wave_formula_focus,
            "wave_custom_draw": wave_custom_draw,
            "wave_custom_box_rect": wave_custom_box_rect_cache,
            "wave_smooth_rect": wave_smooth_rect_cache,
            "wave_reverse_rect": wave_reverse_rect_cache,
            "wave_custom_drag": wave_custom_drag,
            "wave_active_index": wave_active_index,
            "wave_row_rects": wave_row_rects_cache,
            "wave_custom_finished": wave_custom_finished,
            "panel_scroll": panel_scroll,
            "wave_slider_rects": wave_slider_rects_cache,
            "strokes": strokes,
            "reference_image": reference_image,
            "reference_error": reference_error,
            "ref_load_rect": ref_load_rect_cache,
            "ref_vis_rect": ref_vis_rect_cache,
            "ref_clear_rect": ref_clear_rect_cache,
            "ref_opacity_rect": ref_opacity_rect_cache,
        }

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
                if wave_formula_focus and tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes:
                    si, comp_i = selected_curve
                    if 0 <= si < len(strokes):
                        comps = _stroke_components(strokes[si])
                        if 0 <= comp_i < len(comps):
                            comps[comp_i] = dict(comps[comp_i])
                            wi = int(state.get("wave_active_index", 0) or 0)
                            w = _get_wave_style(comps[comp_i], wi)
                            formula = str(w.get("formula", "sin(x)") or "")
                            if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                                wave_formula_focus = False
                                state["wave_formula_focus"] = False
                            elif event.key == pygame.K_BACKSPACE:
                                formula = formula[:-1]
                                w["formula"] = formula
                                _set_wave_style(comps[comp_i], w, wi)
                                strokes[si]["components"] = comps
                            elif event.unicode and event.unicode.isprintable():
                                formula += event.unicode
                                w["formula"] = formula
                                _set_wave_style(comps[comp_i], w, wi)
                                strokes[si]["components"] = comps
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
                        try:
                            if document_path is None:
                                document_path = pick_save_document_path()
                            if document_path:
                                save_document(document_path, strokes, {"view": {"zoom": cfg.VIEW_ZOOM, "pan": [cfg.VIEW_PAN_X, cfg.VIEW_PAN_Y]}})
                        except Exception:
                            pass
                    elif ctrl and event.key == pygame.K_s and shift:
                        try:
                            path = pick_save_document_path()
                            if path:
                                document_path = path
                                save_document(document_path, strokes, {"view": {"zoom": cfg.VIEW_ZOOM, "pan": [cfg.VIEW_PAN_X, cfg.VIEW_PAN_Y]}})
                        except Exception:
                            pass
                    elif ctrl and event.key == pygame.K_o:
                        try:
                            path = pick_open_document_path()
                            if path:
                                loaded = load_document(path)
                                push_undo()
                                strokes.clear(); strokes.extend(loaded)
                                selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
                                transform_drag = None; drag_last = None; redrawing_curve = None
                                document_path = path
                        except Exception:
                            pass
                    elif ctrl and shift and event.key == pygame.K_e:
                        try:
                            path = pick_export_image_path()
                            if path:
                                export_scene_image(path, strokes, ref_img=reference_image,
                                                 view_zoom=getattr(cfg, "VIEW_ZOOM", 1.0),
                                                 view_pan=(getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0)),
                                                 size=(cfg.CANVAS_W, cfg.canvas_viewport_height()))
                        except Exception:
                            pass
                    # --- Select / clipboard / duplicate ---
                    elif ctrl and event.key == pygame.K_a:
                        selected_strokes = set(range(len(strokes)))
                        selected_point = None; selected_curve = None
                    elif ctrl and event.key == pygame.K_d:
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
                    elif ctrl and event.key == pygame.K_c and not shift:
                        # copy selected strokes (Ctrl+C)
                        if selected_strokes:
                            clipboard_strokes = [_copy_stroke(strokes[i]) for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                    elif ctrl and event.key == pygame.K_x:
                        if selected_strokes:
                            clipboard_strokes = [_copy_stroke(strokes[i]) for i in sorted(selected_strokes) if 0 <= i < len(strokes)]
                            push_undo()
                            for i in sorted(selected_strokes, reverse=True):
                                if 0 <= i < len(strokes):
                                    strokes.pop(i)
                            selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
                    elif ctrl and event.key == pygame.K_v:
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
                    # --- View ---
                    elif ctrl and event.key == pygame.K_0:
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
                    elif ctrl and event.key == pygame.K_1:
                        cfg.VIEW_ZOOM = 1.0; cfg.VIEW_PAN_X = 0.0; cfg.VIEW_PAN_Y = 0.0
                    # --- Undo / Redo ---
                    elif ctrl and event.key == pygame.K_z:
                        if shift:
                            if do_redo():
                                selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
                        else:
                            if do_undo():
                                selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
                        selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
                    elif ctrl and event.key == pygame.K_y:
                        if do_redo():
                            selected_strokes = {i for i in selected_strokes if 0 <= i < len(strokes)}
                        selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None; selected_curves.clear(); redrawing_curve = None
                    # --- Tool switching (single-key, no modifiers) ---
                    elif not ctrl and event.key == pygame.K_v:
                        tool_mode = "selection"; drawing = False; current_points = []
                        selected_point = None; drag_last = None; transform_drag = None
                        curve_cut_mode = False
                        eyedropper_pick = False
                    elif not ctrl and event.key == pygame.K_i:
                        tool_mode = "selection"; drawing = False; current_points = []
                        eyedropper_pick = True
                        cutting = False; cut_points = []
                        curve_cut_mode = False
                        redrawing_curve = None
                        selected_point = None; drag_last = None; transform_drag = None
                    elif not ctrl and event.key == pygame.K_b:
                        tool_mode = "draw"; draw_tool = "pen"; drawing = False; current_points = []
                        selected_strokes.clear(); selected_point = None; transform_drag = None
                        eyedropper_pick = False
                    elif not ctrl and event.key == pygame.K_e:
                        tool_mode = "draw"; draw_tool = "eraser"; drawing = False; current_points = []
                        selected_strokes.clear(); selected_point = None; transform_drag = None
                        eyedropper_pick = False
                    elif not ctrl and event.key == pygame.K_f:
                        tool_mode = "draw"; draw_tool = "bucket"; drawing = False; current_points = []
                        selected_strokes.clear(); selected_point = None; transform_drag = None
                        eyedropper_pick = False
                    elif not ctrl and event.key == pygame.K_c:
                        tool_mode = "draw"; draw_tool = "cutter"; drawing = False; current_points = []
                        cutting = False; cut_points = []
                        selected_strokes.clear(); selected_point = None; transform_drag = None
                        eyedropper_pick = False
                    elif not ctrl and event.key == pygame.K_s:
                        snap_enabled = not snap_enabled
                    elif event.key == pygame.K_SPACE:
                        space_panning = True
                    # --- Editing ---
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and tool_mode == "selection":
                        if selected_strokes:
                            push_undo()
                            for i in sorted(selected_strokes, reverse=True):
                                if 0 <= i < len(strokes):
                                    strokes.pop(i)
                            selected_strokes.clear(); selected_point = None; transform_drag = None; selected_curve = None
                    elif event.key == pygame.K_n and tool_mode == "selection":
                        modes = ["transform", "nodes", "curve"]
                        selection_submode = modes[(modes.index(selection_submode) + 1) % len(modes)] if selection_submode in modes else "transform"
                        selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; redrawing_curve = None
                        curve_cut_mode = False
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
                # Right-click a bottom-bar shape tool: its options popup above the button.
                _shape_rects = state.get("draw_shape_rects", {})
                _rc_hit = next((k for k, r in _shape_rects.items() if r.collidepoint(event.pos)), None)
                if _rc_hit is not None:
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
                    if menu_bar_rect.collidepoint(event.pos):
                        menu_open = None if menu_open == "file" else "file"
                    else:
                        menu_open = None
                    menu_handled = True
                elif menu_open == "file":
                    mi = menu_item_rects
                    if mi.get("save", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        try:
                            if document_path is None:
                                document_path = pick_save_document_path()
                            if document_path:
                                save_document(document_path, strokes, {"view": {"zoom": cfg.VIEW_ZOOM, "pan": [cfg.VIEW_PAN_X, cfg.VIEW_PAN_Y]}})
                        except Exception:
                            pass
                        menu_open = None
                        menu_handled = True
                    elif mi.get("save_as", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        try:
                            path = pick_save_document_path()
                            if path:
                                document_path = path
                                save_document(document_path, strokes, {"view": {"zoom": cfg.VIEW_ZOOM, "pan": [cfg.VIEW_PAN_X, cfg.VIEW_PAN_Y]}})
                        except Exception:
                            pass
                        menu_open = None
                        menu_handled = True
                    elif mi.get("open", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        try:
                            path = pick_open_document_path()
                            if path:
                                loaded = load_document(path)
                                push_undo()
                                strokes.clear(); strokes.extend(loaded)
                                selected_strokes.clear(); selected_point = None; selected_curve = None; selected_curves.clear()
                                transform_drag = None; drag_last = None; redrawing_curve = None
                                document_path = path
                        except Exception:
                            pass
                        menu_open = None
                        menu_handled = True
                    elif mi.get("export", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        try:
                            path = pick_export_image_path()
                            if path:
                                export_scene_image(path, strokes, ref_img=reference_image,
                                                   view_zoom=getattr(cfg, "VIEW_ZOOM", 1.0),
                                                   view_pan=(getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0)),
                                                   size=(cfg.CANVAS_W, cfg.canvas_viewport_height()))
                        except Exception:
                            pass
                        menu_open = None
                        menu_handled = True
                    else:
                        menu_open = None
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
                        elif _menu_hit in ("fit", "catmull-rom", "single"):
                            trace_algorithm = _menu_hit
                            shape_menu_key = None
                        elif _menu_hit in ("isosceles", "right", "equilateral"):
                            triangle_variant = _menu_hit
                            # Picking a type implies the triangle tool.
                            draw_shape = "triangle"
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
                    tool_mode = "selection"; drawing = False; current_points = []; selected_point = None; drag_last = None; transform_drag = None; selection_submode = "transform"
                    curve_cut_mode = False
                elif any(r.collidepoint(event.pos) for r in state.get("draw_shape_rects", {}).values()):
                    # Bottom toolbar: pick a shape or a drawing tool.
                    for _shape_key, _shape_rect in state.get("draw_shape_rects", {}).items():
                        if _shape_rect.collidepoint(event.pos):
                            if _shape_key in ("eraser", "bucket", "cutter"):
                                draw_tool = _shape_key
                            else:
                                draw_shape = _shape_key
                                draw_tool = "pen"
                            break
                    tool_mode = "draw"
                    drawing = False
                    current_points = []
                    selected_strokes.clear(); selected_point = None; transform_drag = None
                elif event.pos[0] >= cfg.PANEL_X:
                    # Right panel interactions
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
                            elif state.get("draw_tool_pen_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                draw_tool = "pen"
                            elif state.get("draw_tool_eraser_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                draw_tool = "eraser"
                            elif state.get("draw_tool_bucket_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                draw_tool = "bucket"
                            elif state.get("draw_tool_cutter_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                draw_tool = "cutter"
                                cutting = False; cut_points = []
                            else:
                                picked_shape = False
                                for key, r in state.get("draw_shape_rects", {}).items():
                                    if r.collidepoint(event.pos):
                                        draw_shape = key
                                        picked_shape = True
                                        break
                                if not picked_shape:
                                    for key, r in state.get("trace_algo_rects", {}).items():
                                        if r.collidepoint(event.pos):
                                            trace_algorithm = key
                                            break
                    elif tool_mode == "selection" and state.get("nodes_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        r = state["nodes_toggle_rect"]
                        rel = (event.pos[0] - r.x) / max(1, r.w)
                        if rel < 1/3:
                            selection_submode = "transform"
                        elif rel < 2/3:
                            selection_submode = "nodes"
                        else:
                            selection_submode = "curve"
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
                        state.get("bool_intersect_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                    ):
                        sel = sorted(i for i in selected_strokes if 0 <= i < len(strokes))
                        if len(sel) >= 2:
                            is_union = state.get("bool_union_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
                            op = "union" if is_union else "intersection"
                            try:
                                from models.boolean import boolean_segs
                                result_segs = boolean_segs([strokes[i] for i in sel], op=op)
                            except Exception:
                                result_segs = None
                            if result_segs:
                                push_undo()
                                primary = strokes[sel[0]]
                                fill_col = primary.get("fill_color") if isinstance(primary, dict) else None
                                if fill_col is None:
                                    fill_col = (0.45, 0.72, 1.0, 1.0)
                                new_st = new_stroke(
                                    result_segs,
                                    stroke_color=(0.0, 0.0, 0.0, 0.0),
                                    stroke_width=0.0,
                                    fill_color=fill_col,
                                    algorithm="fit",
                                )
                                for i in reversed(sel):
                                    del strokes[i]
                                strokes.append(new_st)
                                selected_strokes = {len(strokes) - 1}
                                selected_point = None; selected_curve = None; selected_curves.clear(); transform_drag = None; drag_last = None; pending_transform_toggle = None
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
                                n = len(_get_wave_styles(comps[comp_i]))
                                w = default_wave_params()
                                w["enabled"] = True
                                _set_wave_style(comps[comp_i], w, n)
                                strokes[si]["components"] = comps
                                state["wave_active_index"] = n
                                state["wave_custom_finished"] = False
                        wave_formula_focus = False
                        state["wave_formula_focus"] = False
                        state["wave_custom_draw"] = False
                    elif tool_mode == "selection" and selection_submode == "curve" and selected_curve and selected_curve[0] in selected_strokes and state.get("wave_remove_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                wi = int(state.get("wave_active_index", 0) or 0)
                                _remove_wave_style(comps[comp_i], wi)
                                strokes[si]["components"] = comps
                                n = len(_get_wave_styles(comps[comp_i]))
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
                                w = _get_wave_style(comps[comp_i], wi)
                                w["enabled"] = not bool(w.get("enabled"))
                                _set_wave_style(comps[comp_i], w, wi)
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
                        # formula input focus
                        f_rect = state.get("wave_formula_rect", pygame.Rect(0,0,0,0))
                        if f_rect.collidepoint(event.pos) and f_rect.w > 0 and f_rect.h > 0:
                            wave_formula_focus = True
                            state["wave_formula_focus"] = True
                            _w_hit = True
                        # Reverse direction toggle for the active wave layer
                        rev_r = state.get("wave_reverse_rect", pygame.Rect(0, 0, 0, 0))
                        if rev_r.w > 0 and rev_r.h > 0 and rev_r.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_wave_style(comps[comp_i], wi)
                                    w["reverse"] = not bool(w.get("reverse"))
                                    w["enabled"] = True
                                    _set_wave_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                            _w_hit = True
                        # Smooth button: relax the painted custom samples
                        smooth_r = state.get("wave_smooth_rect", pygame.Rect(0, 0, 0, 0))
                        if smooth_r.w > 0 and smooth_r.h > 0 and smooth_r.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_wave_style(comps[comp_i], wi)
                                    w["custom_points"] = _custom_smooth_samples(w.get("custom_points"))
                                    w["enabled"] = True
                                    _set_wave_style(comps[comp_i], w, wi)
                                    strokes[si]["components"] = comps
                            _w_hit = True
                        # custom wave draw mode: pressing inside the box starts
                        # a paint stroke (LMMS Bit Invader style)
                        box = state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
                        if box.w > 0 and box.h > 0 and box.collidepoint(event.pos):
                            si, comp_i = selected_curve
                            if 0 <= si < len(strokes):
                                comps = _stroke_components(strokes[si])
                                if 0 <= comp_i < len(comps):
                                    comps[comp_i] = dict(comps[comp_i])
                                    w = _get_wave_style(comps[comp_i], wi)
                                    # resume editing if it was finished with Esc
                                    state["wave_custom_finished"] = False
                                    state["wave_custom_draw"] = True
                                    # painting implies wanting it visible
                                    w["enabled"] = True
                                    wave_custom_drag = _custom_wave_paint(w, box, event.pos, None)
                                    state["wave_custom_drag"] = wave_custom_drag
                                    _set_wave_style(comps[comp_i], w, wi)
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
                                            w = _get_wave_style(comps[comp_i], wi)
                                            t = (event.pos[0] - r.x) / max(1, r.w - 1)
                                            val = lo + clamp(t, 0.0, 1.0) * (hi - lo)
                                            if key in ("amplitude", "noise", "phase", "seed"):
                                                val = float(int(round(val)))
                                            else:
                                                val = float(val)
                                            w[key] = val
                                            w["enabled"] = True
                                            _set_wave_style(comps[comp_i], w, wi)
                                            strokes[si]["components"] = comps
                                            wave_slider_drag = {"key": key, "rect": r, "lo": lo, "hi": hi, "si": si, "comp_i": comp_i, "wi": wi}
                                    _w_hit = True
                                    break
                        if not _w_hit:
                            for key, r in (state.get("wave_shape_rects") or {}).items():
                                if r.collidepoint(event.pos):
                                    si, comp_i = selected_curve
                                    if 0 <= si < len(strokes):
                                        comps = _stroke_components(strokes[si])
                                        if 0 <= comp_i < len(comps):
                                            comps[comp_i] = dict(comps[comp_i])
                                            w = _get_wave_style(comps[comp_i], wi)
                                            w["shape"] = key
                                            w["enabled"] = True
                                            if key == "custom":
                                                # enter custom wave draw mode
                                                w["shape"] = "custom"
                                                if "custom_points" not in w:
                                                    w["custom_points"] = []
                                            _set_wave_style(comps[comp_i], w, wi)
                                            strokes[si]["components"] = comps
                                            if key == "custom":
                                                state["wave_custom_draw"] = True
                                                state["wave_custom_finished"] = False
                                                state["wave_formula_focus"] = False
                                            else:
                                                state["wave_custom_draw"] = False
                                                state["wave_custom_finished"] = False
                                    _w_hit = True
                                    break
                        if not _w_hit and selected_strokes and (selection_submode == "transform" or (selection_submode == "curve" and selected_curve)):
                            # Modern color picker interactions
                            comp_style_target = None
                            if selection_submode == "curve" and selected_curve and len(selected_strokes) == 1 and selected_curve[0] in selected_strokes:
                                comp_style_target = selected_curve
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
                                    if comp_style_target is not None:
                                        sc, _sw = _effective_component_style(primary_obj, comp_style_target[1])
                                        sc = sc or (0.1, 0.1, 0.15)
                                    else:
                                        sc = primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
                                    picker_h, picker_s, picker_v = rgb_to_hsv(*sc)
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state["tab_fill_rect"].collidepoint(event.pos) and comp_style_target is None:
                                    color_target = "fill"
                                    fc = primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
                                    picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and color_target == "fill" and comp_style_target is None:
                                    for si in sel_list:
                                        if 0 <= si < len(strokes):
                                            strokes[si]["fill_color"] = None
                                elif primary_obj is not None and state["sv_rect"].collidepoint(event.pos):
                                    picker_drag_sv = True
                                    sv = state["sv_rect"]
                                    picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                                    picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                                    col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                    if comp_style_target is not None and color_target == "stroke":
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
                                                    alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                    strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                    state["picker_drag_sv"] = True
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state["hue_rect"].collidepoint(event.pos):
                                    picker_drag_hue = True
                                    hr = state["hue_rect"]
                                    picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                                    col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                    if comp_style_target is not None and color_target == "stroke":
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
                                                    alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                    strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                    state["picker_drag_hue"] = True
                                    state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                elif primary_obj is not None and state.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                    ar = state["alpha_rect"]
                                    new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                                    if comp_style_target is not None and color_target == "stroke":
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
                                            if comp_style_target is not None and color_target == "stroke":
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
                                                            alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                            strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                            picker_h, picker_s, picker_v = rgb_to_hsv(*col)
                                            state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                                            break
                    elif tool_mode == "selection" and selected_strokes and selection_submode == "transform":
                        # Modern color picker interactions (shape-level in transform, stroke-level per selected curve in curve mode)
                        comp_style_target = None
                        if selection_submode == "curve" and selected_curve and len(selected_strokes) == 1 and selected_curve[0] in selected_strokes:
                            comp_style_target = selected_curve
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
                                if comp_style_target is not None:
                                    sc, _sw = _effective_component_style(primary_obj, comp_style_target[1])
                                    sc = sc or (0.1, 0.1, 0.15)
                                else:
                                    sc = primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
                                picker_h, picker_s, picker_v = rgb_to_hsv(*sc)
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state["tab_fill_rect"].collidepoint(event.pos) and comp_style_target is None:
                                color_target = "fill"
                                fc = primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
                                picker_h, picker_s, picker_v = rgb_to_hsv(*fc)
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and color_target == "fill" and comp_style_target is None:
                                for si in sel_list:
                                    if 0 <= si < len(strokes):
                                        strokes[si]["fill_color"] = None
                            elif state["sv_rect"].collidepoint(event.pos):
                                picker_drag_sv = True
                                sv = state["sv_rect"]
                                picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                                picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                                col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                if comp_style_target is not None and color_target == "stroke":
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
                                                alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                state["picker_drag_sv"] = True
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state["hue_rect"].collidepoint(event.pos):
                                picker_drag_hue = True
                                hr = state["hue_rect"]
                                picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                                col = hsv_to_rgb(picker_h, picker_s, picker_v)
                                if comp_style_target is not None and color_target == "stroke":
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
                                                alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                state["picker_drag_hue"] = True
                                state["picker_h"] = picker_h; state["picker_s"] = picker_s; state["picker_v"] = picker_v
                            elif state.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                ar = state["alpha_rect"]
                                new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                                if comp_style_target is not None and color_target == "stroke":
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
                                        if comp_style_target is not None and color_target == "stroke":
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
                                                        alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                                        strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
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
                        else:
                            drawing = True
                            shift_held = bool(mods & pygame.KMOD_SHIFT)
                            start_pos = draw_snap_point(cpos, strokes, snap_radius(), shift_held) or cpos
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
                                src_comps = _stroke_components(src_stroke)
                                if 0 <= src_comp_i < len(src_comps):
                                    src_waves = copy.deepcopy(_get_wave_styles(src_comps[src_comp_i]))
                                else:
                                    src_waves = []
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
                                                comps[ci]["styles"] = [s for s in comps[ci].get("styles", []) if not (isinstance(s, dict) and s.get("type") == "wave")]
                                                for wi, wv in enumerate(src_waves):
                                                    _set_wave_style(comps[ci], wv, wi)
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
                                                    comp["styles"] = [s for s in comp.get("styles", []) if not (isinstance(s, dict) and s.get("type") == "wave")]
                                                    for wi, wv in enumerate(src_waves):
                                                        _set_wave_style(comp, wv, wi)
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
                                    if shift:
                                        if hit_curve in selected_curves:
                                            selected_curves.discard(hit_curve)
                                            if selected_curve == hit_curve:
                                                selected_curve = next(iter(selected_curves), None)
                                        else:
                                            selected_curves.add(hit_curve)
                                            selected_curve = hit_curve
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
                                if bb:
                                    eff_pivot = pivot_pos if pivot_pos is not None else (bb["cx"], bb["cy"])
                                    # hit pivot marker first (draggable rotation/scale center)
                                    if math.hypot(cpos[0] - eff_pivot[0], cpos[1] - eff_pivot[1]) <= 10.0:
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
                                elif hit_test_stroke(cpos, strokes) in selected_strokes:
                                    pending_transform_toggle = {"start": cpos, "moved": False, "primed": True}
                                    handled = True
                            if not handled:
                                hit = hit_test_stroke(cpos, strokes)
                                if hit is not None:
                                    if shift:
                                        if hit in selected_strokes:
                                            selected_strokes.discard(hit)
                                        else:
                                            selected_strokes.add(hit)
                                        drag_last = None
                                    else:
                                        selected_strokes = {hit}
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
                                    pt_hit = hit_test_point(strokes[only], cpos)
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
                    # hold-drag painting inside the custom wave box
                    box = state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
                    if box.w > 0 and box.h > 0:
                        si, comp_i = selected_curve
                        if 0 <= si < len(strokes):
                            comps = _stroke_components(strokes[si])
                            if 0 <= comp_i < len(comps):
                                comps[comp_i] = dict(comps[comp_i])
                                wi = int(state.get("wave_active_index", 0) or 0)
                                w = _get_wave_style(comps[comp_i], wi)
                                wave_custom_drag = _custom_wave_paint(w, box, event.pos, wave_custom_drag)
                                state["wave_custom_drag"] = wave_custom_drag
                                _set_wave_style(comps[comp_i], w, wi)
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
                        w = _get_wave_style(comps[comp_i], wi)
                        t = (event.pos[0] - r.x) / max(1, r.w - 1)
                        val = lo + clamp(t, 0.0, 1.0) * (hi - lo)
                        if key in ("amplitude", "noise", "phase", "seed"):
                            val = float(int(round(val)))
                        else:
                            val = float(val)
                        w[key] = val
                        w["enabled"] = True
                        _set_wave_style(comps[comp_i], w, wi)
                        strokes[si]["components"] = comps
                elif (picker_drag_sv or picker_drag_hue or picker_drag_alpha) and selected_strokes and (selection_submode == "transform" or (selection_submode == "curve" and selected_curve and color_target == "stroke")):
                    sel_list = sorted(selected_strokes)
                    comp_style_target = None
                    if selection_submode == "curve" and selected_curve and len(selected_strokes) == 1 and selected_curve[0] in selected_strokes and color_target == "stroke":
                        comp_style_target = selected_curve
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
                                        alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                        strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
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
                                        alpha = color_alpha(strokes[si].get("fill_color"), 1.0)
                                        strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
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
                                    elif strokes[si].get("fill_color") is not None:
                                        strokes[si]["fill_color"] = set_color_alpha(strokes[si].get("fill_color"), new_alpha)
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
                elif drawing and tool_mode == "draw" and draw_tool == "pen":
                    cpos = clamp_to_canvas(event.pos)
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
                                for si in list(selected_strokes):
                                    if 0 <= si < len(strokes):
                                        strokes[si] = translate_stroke(strokes[si], dx, dy)
                                drag_last = cpos
                    # if not yet moved, wait for threshold or mouseup (toggle)
                elif tool_mode == "selection" and transform_drag is not None and selected_strokes and pygame.mouse.get_pressed()[0]:
                    cpos = clamp_to_canvas(event.pos)
                    td = transform_drag
                    cx, cy = td["center"]  # pivot/rotation center
                    sx0, sy0 = td["start_mouse"]
                    h = td["handle"]
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
                                for si in list(selected_strokes):
                                    if 0 <= si < len(strokes):
                                        strokes[si] = translate_stroke(strokes[si], dx, dy)
                                drag_last = cpos
                    else:
                        drag_last = cpos
                # (translation handled above when drag_last is set)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                if pan_drag is not None and not space_panning:
                    pan_drag = None
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
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
                if marquee_select is not None and tool_mode == "selection":
                    r = normalize_rect(marquee_select["start"], marquee_select.get("current", marquee_select["start"]))
                    if abs(r[2]-r[0]) >= 3 or abs(r[3]-r[1]) >= 3:
                        picked = {i for i, st in enumerate(strokes) if rects_intersect(r, stroke_bbox(st))}
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
                drag_last = None; selected_point = None; transform_drag = None; pivot_drag = None
                picker_drag_sv = False; picker_drag_hue = False; picker_drag_alpha = False; ref_opacity_drag = False
                bucket_picker_drag = None
                wave_slider_drag = None
                wave_custom_drag = None
                state["wave_custom_drag"] = None
                state["picker_drag_sv"] = False; state["picker_drag_hue"] = False; state["picker_drag_alpha"] = False
                ref_drag = None
                max_points_per_curve = slider.value

        # Draw scene (Cairo) and blit at canvas offset
        active = current_points if (drawing and tool_mode == "draw") else (redrawing_curve.get("points") if redrawing_curve else None)
        _eff_pivot = None
        if tool_mode == "selection" and selection_submode == "transform" and selected_strokes:
            _pobb = combined_obb(strokes, selected_strokes)
            if _pobb:
                _eff_pivot = pivot_pos if pivot_pos is not None else (_pobb["cx"], _pobb["cy"])
        draw_scene(
            cairo_surface, strokes, active, snap_point=hover_snap,
            selected_indices=selected_strokes, edit_mode=(tool_mode == "selection"),
            selection_submode=selection_submode, selected_curve=selected_curve,
            selected_curves=set(selected_curves),
            snap_kind=hover_snap_kind, redrawing_curve=redrawing_curve,
            ref_img=reference_image,
            pivot_pos=_eff_pivot,
            transform_handle_mode=transform_handle_mode,
        )
        frame = surface_to_pygame(cairo_surface)
        screen.fill((230, 233, 238))
        screen.blit(frame, (cfg.CANVAS_X, TOP_BAR_H))

        # Cutter swipe preview (razor line across the canvas).
        if cutting and len(cut_points) >= 2:
            pts = [(int(to_screen(p)[0]), int(to_screen(p)[1])) for p in cut_points]
            pygame.draw.lines(screen, (225, 70, 70), False, pts, 2)
            pygame.draw.circle(screen, (255, 255, 255), pts[0], 3)
            pygame.draw.circle(screen, (225, 70, 70), pts[0], 3, 1)

        # marquee selection overlay
        if marquee_select is not None and tool_mode == "selection":
            r = normalize_rect(marquee_select["start"], marquee_select.get("current", marquee_select["start"]))
            rx1, ry1, rx2, ry2 = r
            s1 = to_screen((rx1, ry1)); s2 = to_screen((rx2, ry2))
            rect = pygame.Rect(int(min(s1[0],s2[0])), int(min(s1[1],s2[1])), int(abs(s2[0]-s1[0])), int(abs(s2[1]-s1[1])))
            if rect.w > 0 and rect.h > 0:
                overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                overlay.fill((80, 140, 240, 35))
                screen.blit(overlay, rect.topleft)
                pygame.draw.rect(screen, (60, 120, 220), rect, 1)

        # Need swatch rects for this frame's layout - draw panel and capture by recomputing? we passed refs in state but draw_panel fills them during draw
        draw_left_toolbar(screen, mouse_pos, tool_mode, btn_draw, btn_select, btn_undo, btn_redo, bool(undo_stack), bool(redo_stack))
        if not panel_collapsed:
            draw_panel(screen, fonts, mouse_pos, state)
        draw_panel_toggle(screen, mouse_pos, state)
        draw_bottom_shape_toolbar(screen, fonts, mouse_pos, state)
        draw_shape_context_menu(screen, fonts, mouse_pos, state)

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
        trace_algo_rects_cache = state.get("trace_algo_rects", trace_algo_rects_cache)
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
        nodes_toggle_rect_cache = state.get("nodes_toggle_rect", nodes_toggle_rect_cache)
        elev_front_rect_cache = state.get("elev_front_rect", elev_front_rect_cache)
        elev_forward_rect_cache = state.get("elev_forward_rect", elev_forward_rect_cache)
        elev_backward_rect_cache = state.get("elev_backward_rect", elev_backward_rect_cache)
        elev_back_rect_cache = state.get("elev_back_rect", elev_back_rect_cache)
        bool_union_rect_cache = state.get("bool_union_rect", bool_union_rect_cache)
        bool_intersect_rect_cache = state.get("bool_intersect_rect", bool_intersect_rect_cache)
        curve_hide_rect_cache = state.get("curve_hide_rect", curve_hide_rect_cache)
        curve_redraw_rect_cache = state.get("curve_redraw_rect", curve_redraw_rect_cache)
        curve_cut_rect_cache = state.get("curve_cut_rect", curve_cut_rect_cache)
        curve_join_rect_cache = state.get("curve_join_rect", curve_join_rect_cache)
        eyedropper_rect_cache = state.get("eyedropper_rect", eyedropper_rect_cache)
        wave_toggle_rect_cache = state.get("wave_toggle_rect", wave_toggle_rect_cache)
        wave_add_rect_cache = state.get("wave_add_rect", wave_add_rect_cache)
        wave_remove_rect_cache = state.get("wave_remove_rect", wave_remove_rect_cache)
        wave_shape_rects_cache = state.get("wave_shape_rects", wave_shape_rects_cache)
        wave_formula_rect_cache = state.get("wave_formula_rect", wave_formula_rect_cache)
        wave_formula_focus = state.get("wave_formula_focus", wave_formula_focus)
        wave_custom_draw = state.get("wave_custom_draw", wave_custom_draw)
        wave_custom_box_rect_cache = state.get("wave_custom_box_rect", wave_custom_box_rect_cache)
        wave_smooth_rect_cache = state.get("wave_smooth_rect", wave_smooth_rect_cache)
        wave_reverse_rect_cache = state.get("wave_reverse_rect", wave_reverse_rect_cache)
        wave_custom_drag = state.get("wave_custom_drag", wave_custom_drag)
        wave_active_index = int(state.get("wave_active_index", wave_active_index) or 0)
        wave_row_rects_cache = state.get("wave_row_rects", wave_row_rects_cache)
        wave_custom_finished = bool(state.get("wave_custom_finished", wave_custom_finished))
        panel_scroll = int(state.get("panel_scroll", panel_scroll) or 0)
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

        # Top menu bar
        menu_bar = pygame.Rect(0, 0, cfg.WIDTH, TOP_BAR_H)
        pygame.draw.rect(screen, (250, 251, 253), menu_bar)
        pygame.draw.line(screen, PANEL_BORDER, (0, TOP_BAR_H - 1), (cfg.WIDTH, TOP_BAR_H - 1), 1)
        file_label = font_small.render("File", True, TEXT_COLOR)
        menu_bar_rect = pygame.Rect(6, 2, file_label.get_width() + 16, TOP_BAR_H - 4)
        mbg = TOOL_ACTIVE if (menu_open == "file" or menu_bar_rect.collidepoint(mouse_pos)) else (250, 251, 253)
        pygame.draw.rect(screen, mbg, menu_bar_rect, border_radius=4)
        screen.blit(file_label, (menu_bar_rect.x + 8, menu_bar_rect.y + 4))
        menu_item_rects = {}
        if menu_open == "file":
            items = [
                ("save", "Save", "save", "Save (Ctrl+S)"),
                ("save_as", "Save As...", "save", "Save As (Ctrl+Shift+S)"),
                ("open", "Open...", "open", "Open (Ctrl+O)"),
                ("export", "Export PNG/SVG...", "export", "Export PNG/SVG (Ctrl+Shift+E)"),
            ]
            mw = 220
            ih = 28
            mx, my = menu_bar_rect.x, TOP_BAR_H
            drop = pygame.Rect(mx, my, mw, ih * len(items))
            pygame.draw.rect(screen, (255, 255, 255), drop)
            pygame.draw.rect(screen, PANEL_BORDER, drop, 1)
            menu_tip = None
            for i, (key, label, icon_name, tip_text) in enumerate(items):
                r = pygame.Rect(mx, my + i * ih, mw, ih)
                menu_item_rects[key] = r
                hovered = r.collidepoint(mouse_pos)
                bg = BUTTON_HOVER if hovered else (255, 255, 255)
                pygame.draw.rect(screen, bg, r)
                draw_icon(screen, icon_name,
                          pygame.Rect(r.x + 6, r.centery - 10, 20, 20),
                          color=TEXT_COLOR, size=20)
                t = font_small.render(label, True, TEXT_COLOR)
                screen.blit(t, (r.x + 32, r.y + 6))
                if hovered:
                    menu_tip = tip_text
            if menu_tip:
                draw_tooltip(screen, mouse_pos, menu_tip)

        pygame.display.flip()
        clock.tick(120)

    pygame.quit()
    return 0
