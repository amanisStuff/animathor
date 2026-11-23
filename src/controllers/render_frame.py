"""Render frame (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

def render_frame(ctx):
    # Draw scene (Cairo) and blit at canvas offset
    ctx.active = ctx.current_points if (ctx.drawing and ctx.tool_mode == "draw") else (ctx.redrawing_curve.get("points") if ctx.redrawing_curve else None)
    # While placing text, render the typed buffer as a live editable outline.
    render_strokes = ctx.strokes
    text_preview_index = None
    if ctx.workspace == "library" and ctx.shape_states:
        # Library workspace: browse the saved shape states as canvas content.
        _lib = []
        for _sid, _sdef in ctx.shape_states.items():
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
                ctx._n = copy.deepcopy(_st)
                ctx._n.pop("shape_state_id", None); ctx._n.pop("shape_state_is_master", None); ctx._n.pop("shape_state_instance_id", None)
                try:
                    ctx._n = ctx.translate_stroke(ctx._n, _ox, _oy)
                except Exception:
                    pass
                _lib.append(ctx._n)
        render_strokes = _lib
    if ctx.text_entry is not None and str(ctx.text_entry.get("text", "")):
        try:
            _tc = ctx.hsv_to_rgb(ctx.picker_h, ctx.picker_s, ctx.picker_v)
            _preview = ctx.new_text_stroke(ctx.text_entry["text"], ctx.text_entry["x"],
                                       ctx.text_entry["y"], ctx.text_entry["family"],
                                       ctx.text_entry["size"],
                                       color=(_tc[0], _tc[1], _tc[2], 1.0))
            render_strokes = list(ctx.strokes) + [_preview]
            text_preview_index = len(render_strokes) - 1
        except Exception:
            render_strokes = ctx.strokes
    _eff_pivot = None
    _grad_edit_info = None
    if ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes:
        _pobb = combined_obb(ctx.strokes, ctx.selected_strokes)
        if _pobb:
            _eff_pivot = ctx.pivot_pos if ctx.pivot_pos is not None else (_pobb["cx"], _pobb["cy"])
        if ctx.state.get("color_target", ctx.color_target) == "fill":
            for _gsi in sorted(ctx.selected_strokes):
                if 0 <= _gsi < len(ctx.strokes):
                    _gst = ctx.strokes[_gsi]
                    _gfg = _gst.get("fill_gradient") if isinstance(_gst, dict) else None
                    try:
                        _gfg = ctx.get_fill_gradient(_gst) or _gfg
                    except Exception:
                        pass
                    if isinstance(_gfg, dict) and str(_gfg.get("type")) in ("linear", "radial", "conic", "spiral", "diamond", "square"):
                        try:
                            _grad_edit_info = ctx.gradient_edit_handles(_gst, _gfg)
                            if isinstance(_grad_edit_info, dict):
                                _grad_edit_info["stroke_i"] = _gsi
                        except Exception:
                            _grad_edit_info = None
                        break
    # Set OBB on selection (not at creation).
    for _si in list(ctx.selected_strokes):
        if 0 <= _si < len(ctx.strokes):
            try:
                ctx.get_stroke_obb(ctx.strokes[_si])
            except Exception:
                pass
    draw_scene(
        ctx.cairo_surface, render_strokes, ctx.active, snap_point=ctx.hover_snap,
        selected_indices=ctx.selected_strokes, edit_mode=(ctx.tool_mode == "selection"),
        selection_submode=ctx.selection_submode, selected_curve=ctx.selected_curve,
        selected_curves=set(ctx.selected_curves),
        snap_kind=ctx.hover_snap_kind, redrawing_curve=ctx.redrawing_curve,
        ref_img=ctx.reference_image,
        pivot_pos=_eff_pivot,
        transform_handle_mode=ctx.transform_handle_mode,
        gradient_edit_info=_grad_edit_info,
        guides=ctx.guides,
        smart_guides=ctx.smart_snap_guides,
        bezier_pen=ctx.bezier_pen,
        artboards=ctx.artboards,
        active_artboard=ctx.active_artboard,
    )
    ctx.frame = surface_to_pygame(ctx.cairo_surface)
    ctx.screen.fill(CANVAS_BACKDROP)
    ctx.screen.blit(ctx.frame, (cfg.CANVAS_X, ctx.TOP_BAR_H))

    # Rulers + guides overlay (view-only).
    if getattr(cfg, "SHOW_RULERS", False):
        _rs = int(RULER_SIZE)
        _vh = cfg.canvas_viewport_height()
        _top = pygame.Rect(cfg.CANVAS_X, ctx.TOP_BAR_H, cfg.CANVAS_W, _rs)
        _left = pygame.Rect(cfg.CANVAS_X, ctx.TOP_BAR_H, _rs, _vh)
        pygame.draw.rect(ctx.screen, RULER_BG_RGB, _top)
        pygame.draw.rect(ctx.screen, RULER_BG_RGB, _left)
        pygame.draw.line(ctx.screen, PANEL_BORDER, (_top.x, _top.bottom - 1),
                         (_top.right, _top.bottom - 1), BORDER_WIDTH)
        pygame.draw.line(ctx.screen, PANEL_BORDER, (_left.right - 1, _left.y),
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
            pygame.draw.line(ctx.screen, RULER_TICK_RGB, (_sx, _top.bottom - 5),
                             (_sx, _top.bottom - 1), BORDER_WIDTH)
            _lbl = ctx.ruler_font.render(str(int(round(_x))), True, RULER_TEXT_RGB)
            ctx.screen.blit(_lbl, (_sx + 2, _top.y + 1))
        for _y in grid_positions(_wy0, _wy1, _step_y):
            _sy = int(_y * _z + _py + ctx.TOP_BAR_H)
            if _sy <= _left.y or _sy >= _left.bottom:
                continue
            pygame.draw.line(ctx.screen, RULER_TICK_RGB, (_left.right - 5, _sy),
                             (_left.right - 1, _sy), BORDER_WIDTH)
            _lbl = ctx.ruler_font.render(str(int(round(_y))), True, RULER_TEXT_RGB)
            _lbl = pygame.transform.rotate(_lbl, 90)
            ctx.screen.blit(_lbl, (_left.x + 1, _sy + 2))

    # Cutter swipe preview (razor line across the canvas).
    if ctx.cutting and len(ctx.cut_points) >= 2:
        ctx.pts = [(int(ctx.to_screen(ctx.p)[0]), int(ctx.to_screen(ctx.p)[1])) for ctx.p in ctx.cut_points]
        pygame.draw.lines(ctx.screen, CUT_COLOR, False, ctx.pts, int(EDITOR_LINE_WIDTH_BOLD))
        pygame.draw.circle(ctx.screen, SURFACE, ctx.pts[0], CUT_HANDLE_RADIUS)
        pygame.draw.circle(ctx.screen, CUT_COLOR, ctx.pts[0], CUT_HANDLE_RADIUS, BORDER_WIDTH)

    # marquee selection overlay
    if ctx.marquee_select is not None and ctx.tool_mode == "selection":
        ctx.r = normalize_rect(ctx.marquee_select["start"], ctx.marquee_select.get("current", ctx.marquee_select["start"]))
        rx1, ry1, rx2, ry2 = ctx.r
        ctx.s1 = ctx.to_screen((rx1, ry1)); s2 = ctx.to_screen((rx2, ry2))
        ctx.rect = pygame.Rect(int(min(ctx.s1[0],s2[0])), int(min(ctx.s1[1],s2[1])), int(abs(s2[0]-ctx.s1[0])), int(abs(s2[1]-ctx.s1[1])))
        if ctx.rect.w > 0 and ctx.rect.h > 0:
            overlay = pygame.Surface((ctx.rect.w, ctx.rect.h), pygame.SRCALPHA)
            overlay.fill(SELECTION_FILL)
            ctx.screen.blit(overlay, ctx.rect.topleft)
            pygame.draw.rect(ctx.screen, SELECTION_BORDER, ctx.rect, BORDER_WIDTH)

    # Need swatch rects for this frame's layout - draw panel and capture by recomputing? we passed refs in state but draw_panel fills them during draw
    draw_left_toolbar(ctx.screen, ctx.mouse_pos, ctx.tool_mode, ctx.btn_draw, ctx.btn_select, ctx.btn_undo, ctx.btn_redo, bool(ctx.undo_stack), bool(ctx.redo_stack))
    if not ctx.panel_collapsed:
        draw_panel(ctx.screen, ctx.fonts, ctx.mouse_pos, ctx.state)
    draw_panel_toggle(ctx.screen, ctx.mouse_pos, ctx.state)
    draw_bottom_shape_toolbar(ctx.screen, ctx.fonts, ctx.mouse_pos, ctx.state)
    draw_shape_context_menu(ctx.screen, ctx.fonts, ctx.mouse_pos, ctx.state)
    draw_marker_dropdown(ctx.screen, ctx.fonts, ctx.mouse_pos, ctx.state)

    # sync picker state/rects from panel for next frame's event handling
    ctx.picker_h = ctx.state.get("picker_h", ctx.picker_h)
    ctx.picker_s = ctx.state.get("picker_s", ctx.picker_s)
    ctx.picker_v = ctx.state.get("picker_v", ctx.picker_v)
    ctx.picker_rects["sv"] = ctx.state.get("sv_rect", ctx.picker_rects["sv"])
    ctx.picker_rects["hue"] = ctx.state.get("hue_rect", ctx.picker_rects["hue"])
    ctx.picker_rects["tab_stroke"] = ctx.state.get("tab_stroke_rect", ctx.picker_rects["tab_stroke"])
    ctx.picker_rects["tab_fill"] = ctx.state.get("tab_fill_rect", ctx.picker_rects["tab_fill"])
    ctx.picker_rects["nofill"] = ctx.state.get("nofill_rect", ctx.picker_rects["nofill"])
    ctx.picker_rects["alpha"] = ctx.state.get("alpha_rect", ctx.picker_rects["alpha"])
    ctx.fill_type_prev_rect_cache = ctx.state.get("fill_type_prev_rect", ctx.fill_type_prev_rect_cache)
    ctx.fill_type_next_rect_cache = ctx.state.get("fill_type_next_rect", ctx.fill_type_next_rect_cache)
    ctx.fill_stop_rects_cache = dict(ctx.state.get("fill_stop_rects", ctx.fill_stop_rects_cache) or {})
    ctx.fill_stop_add_rect_cache = ctx.state.get("fill_stop_add_rect", ctx.fill_stop_add_rect_cache)
    ctx.fill_stop_remove_rect_cache = ctx.state.get("fill_stop_remove_rect", ctx.fill_stop_remove_rect_cache)
    ctx.fill_stop_pos_rect_cache = ctx.state.get("fill_stop_pos_rect", ctx.fill_stop_pos_rect_cache)
    ctx.pattern_type_rect_cache = ctx.state.get("pattern_type_rect", ctx.pattern_type_rect_cache)
    ctx.pattern_size_minus_rect_cache = ctx.state.get("pattern_size_minus_rect", ctx.pattern_size_minus_rect_cache)
    ctx.pattern_size_plus_rect_cache = ctx.state.get("pattern_size_plus_rect", ctx.pattern_size_plus_rect_cache)
    ctx.fill_gradient_stop = int(ctx.state.get("fill_gradient_stop", ctx.fill_gradient_stop) or 0)
    ctx.fill_stop_pos_drag = bool(ctx.state.get("fill_stop_pos_drag", ctx.fill_stop_pos_drag))
    ctx.trace_algo_prev_rect_cache = ctx.state.get("trace_algo_prev_rect", ctx.trace_algo_prev_rect_cache)
    ctx.trace_algo_next_rect_cache = ctx.state.get("trace_algo_next_rect", ctx.trace_algo_next_rect_cache)
    ctx.draw_tool_prev_rect_cache = ctx.state.get("draw_tool_prev_rect", ctx.draw_tool_prev_rect_cache)
    ctx.draw_tool_next_rect_cache = ctx.state.get("draw_tool_next_rect", ctx.draw_tool_next_rect_cache)
    ctx.draw_shape_rects_cache = ctx.state.get("draw_shape_rects", ctx.draw_shape_rects_cache)
    ctx.panel_toggle_rect_cache = ctx.state.get("panel_toggle_rect", ctx.panel_toggle_rect_cache)
    ctx.panel_collapsed = bool(ctx.state.get("panel_collapsed", ctx.panel_collapsed))
    ctx.shape_menu_key = ctx.state.get("shape_menu_key", ctx.shape_menu_key)
    ctx.shape_menu_anchor = ctx.state.get("shape_menu_anchor", ctx.shape_menu_anchor)
    ctx.shape_menu_rect = ctx.state.get("shape_menu_rect", ctx.shape_menu_rect)
    ctx.shape_menu_item_rects = ctx.state.get("shape_menu_item_rects", ctx.shape_menu_item_rects)
    ctx.draw_tool_pen_rect_cache = ctx.state.get("draw_tool_pen_rect", ctx.draw_tool_pen_rect_cache)
    ctx.draw_tool_eraser_rect_cache = ctx.state.get("draw_tool_eraser_rect", ctx.draw_tool_eraser_rect_cache)
    ctx.draw_tool_bucket_rect_cache = ctx.state.get("draw_tool_bucket_rect", ctx.draw_tool_bucket_rect_cache)
    ctx.draw_tool_cutter_rect_cache = ctx.state.get("draw_tool_cutter_rect", ctx.draw_tool_cutter_rect_cache)
    ctx.bucket_picker_h = ctx.state.get("bucket_picker_h", ctx.bucket_picker_h)
    ctx.bucket_picker_s = ctx.state.get("bucket_picker_s", ctx.bucket_picker_s)
    ctx.bucket_picker_v = ctx.state.get("bucket_picker_v", ctx.bucket_picker_v)
    ctx.bucket_sv_rect_cache = ctx.state.get("bucket_sv_rect", ctx.bucket_sv_rect_cache)
    ctx.bucket_hue_rect_cache = ctx.state.get("bucket_hue_rect", ctx.bucket_hue_rect_cache)
    ctx.bucket_swatch_rects_cache = ctx.state.get("bucket_swatch_rects", ctx.bucket_swatch_rects_cache)
    ctx.snap_toggle_rect_cache = ctx.state.get("snap_toggle_rect", ctx.snap_toggle_rect_cache)
    ctx.nodes_mode_prev_rect_cache = ctx.state.get("nodes_mode_prev_rect", ctx.nodes_mode_prev_rect_cache)
    ctx.nodes_mode_next_rect_cache = ctx.state.get("nodes_mode_next_rect", ctx.nodes_mode_next_rect_cache)
    ctx.elev_front_rect_cache = ctx.state.get("elev_front_rect", ctx.elev_front_rect_cache)
    ctx.elev_forward_rect_cache = ctx.state.get("elev_forward_rect", ctx.elev_forward_rect_cache)
    ctx.elev_backward_rect_cache = ctx.state.get("elev_backward_rect", ctx.elev_backward_rect_cache)
    ctx.elev_back_rect_cache = ctx.state.get("elev_back_rect", ctx.elev_back_rect_cache)
    ctx.bool_union_rect_cache = ctx.state.get("bool_union_rect", ctx.bool_union_rect_cache)
    ctx.bool_intersect_rect_cache = ctx.state.get("bool_intersect_rect", ctx.bool_intersect_rect_cache)
    ctx.bool_subtract_rect_cache = ctx.state.get("bool_subtract_rect", ctx.bool_subtract_rect_cache)
    ctx.bool_exclude_rect_cache = ctx.state.get("bool_exclude_rect", ctx.bool_exclude_rect_cache)
    ctx.distribute_h_rect_cache = ctx.state.get("distribute_h_rect", ctx.distribute_h_rect_cache)
    ctx.distribute_v_rect_cache = ctx.state.get("distribute_v_rect", ctx.distribute_v_rect_cache)
    ctx.path_close_rect_cache = ctx.state.get("path_close_rect", ctx.path_close_rect_cache)
    ctx.path_reverse_rect_cache = ctx.state.get("path_reverse_rect", ctx.path_reverse_rect_cache)
    ctx.path_add_rect_cache = ctx.state.get("path_add_rect", ctx.path_add_rect_cache)
    ctx.path_delete_rect_cache = ctx.state.get("path_delete_rect", ctx.path_delete_rect_cache)
    ctx.path_smooth_rect_cache = ctx.state.get("path_smooth_rect", ctx.path_smooth_rect_cache)
    ctx.path_corner_rect_cache = ctx.state.get("path_corner_rect", ctx.path_corner_rect_cache)
    ctx.path_expand_rect_cache = ctx.state.get("path_expand_rect", ctx.path_expand_rect_cache)
    ctx.obj_opacity_rect_cache = ctx.state.get("obj_opacity_rect", ctx.obj_opacity_rect_cache)
    ctx.shadow_toggle_rect_cache = ctx.state.get("shadow_toggle_rect", ctx.shadow_toggle_rect_cache)
    ctx.shadow_blur_minus_rect_cache = ctx.state.get("shadow_blur_minus_rect", ctx.shadow_blur_minus_rect_cache)
    ctx.shadow_blur_plus_rect_cache = ctx.state.get("shadow_blur_plus_rect", ctx.shadow_blur_plus_rect_cache)
    ctx.cap_prev_rect_cache = ctx.state.get("cap_prev_rect", ctx.cap_prev_rect_cache)
    ctx.cap_next_rect_cache = ctx.state.get("cap_next_rect", ctx.cap_next_rect_cache)
    ctx.join_prev_rect_cache = ctx.state.get("join_prev_rect", ctx.join_prev_rect_cache)
    ctx.join_next_rect_cache = ctx.state.get("join_next_rect", ctx.join_next_rect_cache)
    ctx.dash_prev_rect_cache = ctx.state.get("dash_prev_rect", ctx.dash_prev_rect_cache)
    ctx.dash_next_rect_cache = ctx.state.get("dash_next_rect", ctx.dash_next_rect_cache)
    ctx.marker_start_rect_cache = ctx.state.get("marker_start_rect", ctx.marker_start_rect_cache)
    ctx.marker_end_rect_cache = ctx.state.get("marker_end_rect", ctx.marker_end_rect_cache)
    ctx.marker_dropdown = ctx.state.get("marker_dropdown", ctx.marker_dropdown)
    ctx.marker_dropdown_rect = ctx.state.get("marker_dropdown_rect", ctx.marker_dropdown_rect)
    ctx.marker_dropdown_item_rects = dict(ctx.state.get("marker_dropdown_item_rects", ctx.marker_dropdown_item_rects) or {})
    ctx.width_profile_prev_rect_cache = ctx.state.get("width_profile_prev_rect", ctx.width_profile_prev_rect_cache)
    ctx.width_profile_next_rect_cache = ctx.state.get("width_profile_next_rect", ctx.width_profile_next_rect_cache)
    ctx.obj_opacity_drag = ctx.state.get("obj_opacity_drag", ctx.obj_opacity_drag)
    ctx.xform_field_focus = ctx.state.get("xform_field_focus", ctx.xform_field_focus)
    ctx.xform_field_buffer = ctx.state.get("xform_field_buffer", ctx.xform_field_buffer)
    ctx.xform_x_rect_cache = ctx.state.get("xform_x_rect", ctx.xform_x_rect_cache)
    ctx.xform_y_rect_cache = ctx.state.get("xform_y_rect", ctx.xform_y_rect_cache)
    ctx.xform_w_rect_cache = ctx.state.get("xform_w_rect", ctx.xform_w_rect_cache)
    ctx.xform_h_rect_cache = ctx.state.get("xform_h_rect", ctx.xform_h_rect_cache)
    ctx.xform_r_rect_cache = ctx.state.get("xform_r_rect", ctx.xform_r_rect_cache)
    ctx.xform_xm_rect_cache = ctx.state.get("xform_xm_rect", ctx.xform_xm_rect_cache)
    ctx.xform_xp_rect_cache = ctx.state.get("xform_xp_rect", ctx.xform_xp_rect_cache)
    ctx.xform_ym_rect_cache = ctx.state.get("xform_ym_rect", ctx.xform_ym_rect_cache)
    ctx.xform_yp_rect_cache = ctx.state.get("xform_yp_rect", ctx.xform_yp_rect_cache)
    ctx.xform_wm_rect_cache = ctx.state.get("xform_wm_rect", ctx.xform_wm_rect_cache)
    ctx.xform_wp_rect_cache = ctx.state.get("xform_wp_rect", ctx.xform_wp_rect_cache)
    ctx.xform_hm_rect_cache = ctx.state.get("xform_hm_rect", ctx.xform_hm_rect_cache)
    ctx.xform_hp_rect_cache = ctx.state.get("xform_hp_rect", ctx.xform_hp_rect_cache)
    ctx.xform_rm_rect_cache = ctx.state.get("xform_rm_rect", ctx.xform_rm_rect_cache)
    ctx.xform_rp_rect_cache = ctx.state.get("xform_rp_rect", ctx.xform_rp_rect_cache)
    ctx.export_dialog_rects = dict(ctx.state.get("export_dialog_rects", ctx.export_dialog_rects) or {})
    ctx.text_edit_rect_cache = ctx.state.get("text_edit_rect", ctx.text_edit_rect_cache)
    ctx.text_font_rect_cache = ctx.state.get("text_font_rect", ctx.text_font_rect_cache)
    ctx.text_size_minus_rect_cache = ctx.state.get("text_size_minus_rect", ctx.text_size_minus_rect_cache)
    ctx.text_size_plus_rect_cache = ctx.state.get("text_size_plus_rect", ctx.text_size_plus_rect_cache)
    ctx.text_on_path_rect_cache = ctx.state.get("text_on_path_rect", ctx.text_on_path_rect_cache)
    ctx.text_off_path_rect_cache = ctx.state.get("text_off_path_rect", ctx.text_off_path_rect_cache)
    ctx.mirror_h_rect_cache = ctx.state.get("mirror_h_rect", ctx.mirror_h_rect_cache)
    ctx.mirror_v_rect_cache = ctx.state.get("mirror_v_rect", ctx.mirror_v_rect_cache)
    ctx.align_left_rect_cache = ctx.state.get("align_left_rect", ctx.align_left_rect_cache)
    ctx.align_hcenter_rect_cache = ctx.state.get("align_hcenter_rect", ctx.align_hcenter_rect_cache)
    ctx.align_right_rect_cache = ctx.state.get("align_right_rect", ctx.align_right_rect_cache)
    ctx.align_top_rect_cache = ctx.state.get("align_top_rect", ctx.align_top_rect_cache)
    ctx.align_vmiddle_rect_cache = ctx.state.get("align_vmiddle_rect", ctx.align_vmiddle_rect_cache)
    ctx.align_bottom_rect_cache = ctx.state.get("align_bottom_rect", ctx.align_bottom_rect_cache)
    ctx.curve_hide_rect_cache = ctx.state.get("curve_hide_rect", ctx.curve_hide_rect_cache)
    ctx.curve_redraw_rect_cache = ctx.state.get("curve_redraw_rect", ctx.curve_redraw_rect_cache)
    ctx.curve_cut_rect_cache = ctx.state.get("curve_cut_rect", ctx.curve_cut_rect_cache)
    ctx.curve_join_rect_cache = ctx.state.get("curve_join_rect", ctx.curve_join_rect_cache)
    ctx.eyedropper_rect_cache = ctx.state.get("eyedropper_rect", ctx.eyedropper_rect_cache)
    ctx.wave_toggle_rect_cache = ctx.state.get("wave_toggle_rect", ctx.wave_toggle_rect_cache)
    ctx.wave_add_rect_cache = ctx.state.get("wave_add_rect", ctx.wave_add_rect_cache)
    ctx.displacement_add_rect_cache = ctx.state.get("displacement_add_rect", ctx.displacement_add_rect_cache)
    ctx.repeat_add_rect_cache = ctx.state.get("repeat_add_rect", ctx.repeat_add_rect_cache)
    ctx.thickness_add_rect_cache = ctx.state.get("thickness_add_rect", ctx.thickness_add_rect_cache)
    ctx.wave_remove_rect_cache = ctx.state.get("wave_remove_rect", ctx.wave_remove_rect_cache)
    ctx.wave_bake_rect_cache = ctx.state.get("wave_bake_rect", ctx.wave_bake_rect_cache)
    ctx.wave_shape_prev_rect_cache = ctx.state.get("wave_shape_prev_rect", ctx.wave_shape_prev_rect_cache)
    ctx.wave_shape_next_rect_cache = ctx.state.get("wave_shape_next_rect", ctx.wave_shape_next_rect_cache)
    ctx.displacement_profile_rects_cache = ctx.state.get("displacement_profile_rects", ctx.displacement_profile_rects_cache)
    ctx.displacement_affect_rects_cache = ctx.state.get("displacement_affect_rects", ctx.displacement_affect_rects_cache)
    ctx.wave_formula_rect_cache = ctx.state.get("wave_formula_rect", ctx.wave_formula_rect_cache)
    ctx.wave_formula_focus = ctx.state.get("wave_formula_focus", ctx.wave_formula_focus)
    ctx.wave_custom_draw = ctx.state.get("wave_custom_draw", ctx.wave_custom_draw)
    ctx.repeat_pick_mode = ctx.state.get("repeat_pick_mode", ctx.repeat_pick_mode)
    ctx.repeat_pick_target = ctx.state.get("repeat_pick_target", ctx.repeat_pick_target)
    ctx.wave_custom_box_rect_cache = ctx.state.get("wave_custom_box_rect", ctx.wave_custom_box_rect_cache)
    ctx.wave_smooth_rect_cache = ctx.state.get("wave_smooth_rect", ctx.wave_smooth_rect_cache)
    ctx.wave_clear_rect_cache = ctx.state.get("wave_clear_rect", ctx.wave_clear_rect_cache)
    ctx.wave_done_rect_cache = ctx.state.get("wave_done_rect", ctx.wave_done_rect_cache)
    ctx.repeat_pick_curve_rect_cache = ctx.state.get("repeat_pick_curve_rect", ctx.repeat_pick_curve_rect_cache)
    ctx.wave_reverse_rect_cache = ctx.state.get("wave_reverse_rect", ctx.wave_reverse_rect_cache)
    ctx.wave_clamp_rect_cache = ctx.state.get("wave_clamp_rect", ctx.wave_clamp_rect_cache)
    ctx.wave_custom_drag = ctx.state.get("wave_custom_drag", ctx.wave_custom_drag)
    ctx.wave_active_index = int(ctx.state.get("wave_active_index", ctx.wave_active_index) or 0)
    ctx.wave_row_rects_cache = ctx.state.get("wave_row_rects", ctx.wave_row_rects_cache)
    ctx.wave_custom_finished = bool(ctx.state.get("wave_custom_finished", ctx.wave_custom_finished))
    ctx.panel_scroll = int(ctx.state.get("panel_scroll", ctx.panel_scroll) or 0)
    ctx.export_scale = float(ctx.state.get("export_scale", ctx.export_scale) or 1.0)
    ctx.export_dpi = int(ctx.state.get("export_dpi", ctx.export_dpi) or 300)
    _content_bottom = int(ctx.state.get("panel_content_bottom", 0) or 0)
    _max_scroll = max(0, _content_bottom + 24 - (cfg.HEIGHT - ctx.TOP_BAR_H))
    ctx.panel_scroll = max(0, min(ctx.panel_scroll, _max_scroll))
    ctx.wave_slider_rects_cache = ctx.state.get("wave_slider_rects", ctx.wave_slider_rects_cache)
    ctx.ref_load_rect_cache = ctx.state.get("ref_load_rect", ctx.ref_load_rect_cache)
    ctx.ref_vis_rect_cache = ctx.state.get("ref_vis_rect", ctx.ref_vis_rect_cache)
    ctx.ref_clear_rect_cache = ctx.state.get("ref_clear_rect", ctx.ref_clear_rect_cache)
    ctx.ref_opacity_rect_cache = ctx.state.get("ref_opacity_rect", ctx.ref_opacity_rect_cache)
    ctx.swatch_rects_cache["stroke"] = list(ctx.state.get("stroke_swatch_rects", ctx.swatch_rects_cache["stroke"]))
    ctx.swatch_rects_cache["fill"] = list(ctx.state.get("fill_swatch_rects", ctx.swatch_rects_cache["fill"]))

    # sync width slider to selected on selection changes shown next frame (simple keep)
    if ctx.tool_mode == "selection" and ctx.selected_strokes and not ctx.width_slider.dragging:
        ctx.primary_i = sorted(ctx.selected_strokes)[0]
        if 0 <= ctx.primary_i < len(ctx.strokes):
            ctx.width_slider.value = int(round(ctx.strokes[ctx.primary_i].get("stroke_width", 3)))

    # Top menu bar -- one data-driven source for all menus and dropdowns.
    ctx.menu_bar_rects, ctx.menu_item_rects = draw_menu_bar(
        ctx.screen, ctx.font_small, ctx.mouse_pos, ctx.menu_open, state=ctx.state)
    if ctx.help_open:
        draw_shortcuts_overlay(ctx.screen, ctx.font, ctx.font_small)
    if ctx.export_dialog_open:
        draw_export_dialog(ctx.screen, ctx.font, ctx.font_small, ctx.mouse_pos, ctx.state)

    pygame.display.flip()
    ctx.clock.tick(120)

    pygame.quit()
    return 0
    return None
