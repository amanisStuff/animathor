"""Panel click helpers (split for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

# _handle_panel_click_a

def _handle_panel_click_a(ctx, event):
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
        if ctx.state.get("ref_load_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            ctx.path = pick_reference_image_path()
            if ctx.path:
                ref = load_reference_image(ctx.path)
                if ref is not None:
                    ctx.reference_image = ref
                    ctx.reference_error = None
                else:
                    ctx.reference_error = "Could not load reference image (unsupported or corrupt file)."
            handled_draw_panel = True
        elif ctx.state.get("ref_vis_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            if ctx.reference_image:
                ctx.reference_image["visible"] = not ctx.reference_image.get("visible", True)
            handled_draw_panel = True
        elif ctx.state.get("ref_clear_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            ctx.reference_image = None
            ctx.reference_error = None
            handled_draw_panel = True
        elif ctx.reference_image and ctx.state.get("ref_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            ctx.bar = ctx.state["ref_opacity_rect"]
            ctx.reference_image["opacity"] = ctx.clamp((event.pos[0] - ctx.bar.x) / max(1, ctx.bar.w - 1), 0.0, 1.0)
            ctx.ref_opacity_drag = True
            handled_draw_panel = True
        if not handled_draw_panel:
            if ctx.state.get("snap_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.snap_enabled = not ctx.snap_enabled
            elif ctx.state.get("bucket_sv_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.bucket_pick(ctx.state["bucket_sv_rect"], event.pos, "sv")
                ctx.bucket_picker_drag = "sv"
            elif ctx.state.get("bucket_hue_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.bucket_pick(ctx.state["bucket_hue_rect"], event.pos, "hue")
                ctx.bucket_picker_drag = "hue"
            elif any(ctx.r.collidepoint(event.pos) for ctx.r in ctx.state.get("bucket_swatch_rects", [])):
                for _i, _r in enumerate(ctx.state.get("bucket_swatch_rects", [])):
                    if _r.collidepoint(event.pos) and _i < len(ctx.BUCKET_SWATCHES):
                        ctx.set_bucket_color(ctx.BUCKET_SWATCHES[_i])
                        break
            elif any(ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
                     for ctx.k in ("draw_tool_prev_rect", "draw_tool_next_rect")):
                _dtdir = -1 if ctx.state.get("draw_tool_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
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
                        _adir = -1 if ctx.state.get("trace_algo_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
                        _algos = [ctx.k for ctx.k, _ in TRACE_ALGORITHMS]
                        _cur = ctx.trace_algorithm if ctx.trace_algorithm in _algos else _algos[0]
                        ctx.trace_algorithm = _algos[(_algos.index(_cur) + _adir) % len(_algos)]
    elif ctx.tool_mode == "selection" and any(
        ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for ctx.k in ("nodes_mode_prev_rect", "nodes_mode_next_rect")
    ):
        _matched = True
        _mdir = -1 if ctx.state.get("nodes_mode_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
        _modes = ["transform", "nodes", "curve"]
        _cur = ctx.selection_submode if ctx.selection_submode in _modes else "transform"
        ctx.selection_submode = _modes[(_modes.index(_cur) + _mdir) % len(_modes)]
        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.redrawing_curve = None
        ctx.curve_cut_mode = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and (
        ctx.state.get("elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        ctx.push_undo()
        ctx.sel = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
        if ctx.sel:
            sel_set_local = set(ctx.sel)
            if ctx.state.get("elev_front_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.picked = [ctx.strokes[ctx.i] for ctx.i in ctx.sel]
                remaining = [ctx.st for ctx.i, ctx.st in enumerate(ctx.strokes) if ctx.i not in sel_set_local]
                ctx.strokes[:] = remaining + ctx.picked
                ctx.selected_strokes = set(range(len(remaining), len(ctx.strokes)))
            elif ctx.state.get("elev_back_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                ctx.picked = [ctx.strokes[ctx.i] for ctx.i in ctx.sel]
                remaining = [ctx.st for ctx.i, ctx.st in enumerate(ctx.strokes) if ctx.i not in sel_set_local]
                ctx.strokes[:] = ctx.picked + remaining
                ctx.selected_strokes = set(range(len(ctx.picked)))
            elif ctx.state.get("elev_forward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                for ctx.i in range(len(ctx.strokes) - 2, -1, -1):
                    if ctx.i in ctx.selected_strokes and (ctx.i + 1) not in ctx.selected_strokes:
                        ctx.strokes[ctx.i], ctx.strokes[ctx.i + 1] = ctx.strokes[ctx.i + 1], ctx.strokes[ctx.i]
                        ctx.selected_strokes.discard(ctx.i); ctx.selected_strokes.add(ctx.i + 1)
            elif ctx.state.get("elev_backward_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                for ctx.i in range(1, len(ctx.strokes)):
                    if ctx.i in ctx.selected_strokes and (ctx.i - 1) not in ctx.selected_strokes:
                        ctx.strokes[ctx.i], ctx.strokes[ctx.i - 1] = ctx.strokes[ctx.i - 1], ctx.strokes[ctx.i]
                        ctx.selected_strokes.discard(ctx.i); ctx.selected_strokes.add(ctx.i - 1)
        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.pending_transform_toggle = None
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and len(ctx.selected_strokes) >= 2 and (
        ctx.state.get("bool_union_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("bool_intersect_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("bool_subtract_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("bool_exclude_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        ctx.sel = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
        if len(ctx.sel) >= 2:
            bool_key = ctx.next(
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
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and (
        ctx.state.get("mirror_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("mirror_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("align_left_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("align_hcenter_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("align_right_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("align_top_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("align_vmiddle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("align_bottom_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        ctx.sel = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
        if ctx.sel:
            obb = ctx.combined_obb(ctx.strokes, ctx.sel)
            ctx.bb = ctx.combined_bbox(ctx.strokes, ctx.sel)
            if obb and ctx.bb:
                if ctx.pivot_pos is not None:
                    ctx.cx, ctx.cy = ctx.pivot_pos
                else:
                    ctx.cx, ctx.cy = (ctx.bb[0] + ctx.bb[2]) / 2.0, (ctx.bb[1] + ctx.bb[3]) / 2.0
                ctx.push_undo()
                if ctx.state.get("mirror_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    for ctx.si in ctx.sel:
                        ctx.strokes[ctx.si] = mirror_stroke(ctx.strokes[ctx.si], ctx.cx, ctx.cy, "h")
                elif ctx.state.get("mirror_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    for ctx.si in ctx.sel:
                        ctx.strokes[ctx.si] = mirror_stroke(ctx.strokes[ctx.si], ctx.cx, ctx.cy, "v")
                else:
                    ctx.tx1, ctx.ty1, tx2, ty2 = ctx.bb
                    ctx.tcx, ctx.tcy = (ctx.tx1 + tx2) / 2.0, (ctx.ty1 + ty2) / 2.0
                    for ctx.si in ctx.sel:
                        sbb = ctx.stroke_bbox(ctx.strokes[ctx.si])
                        if not sbb:
                            continue
                        ctx.sx1, ctx.sy1, sx2, sy2 = sbb
                        ctx.scx, ctx.scy = (ctx.sx1 + sx2) / 2.0, (ctx.sy1 + sy2) / 2.0
                        ctx.dx = ctx.dy = 0.0
                        if ctx.state.get("align_left_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            ctx.dx = ctx.tx1 - ctx.sx1
                        elif ctx.state.get("align_hcenter_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            ctx.dx = ctx.tcx - ctx.scx
                        elif ctx.state.get("align_right_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            ctx.dx = tx2 - sx2
                        elif ctx.state.get("align_top_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            ctx.dy = ctx.ty1 - ctx.sy1
                        elif ctx.state.get("align_vmiddle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            ctx.dy = ctx.tcy - ctx.scy
                        elif ctx.state.get("align_bottom_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                            ctx.dy = ty2 - sy2
                        if ctx.dx != 0.0 or ctx.dy != 0.0:
                            ctx.strokes[ctx.si] = ctx.translate_stroke(ctx.strokes[ctx.si], ctx.dx, ctx.dy)
        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.pending_transform_toggle = None
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and len(ctx.selected_strokes) >= 3 and (
        ctx.state.get("distribute_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        ctx.state.get("distribute_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        ctx.sel = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
        ctx.boxes = [ctx.stroke_bbox(ctx.strokes[ctx.si]) for ctx.si in ctx.sel]
        if all(ctx.boxes) and len(ctx.boxes) >= 3:
            horizontal = ctx.state.get("distribute_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
            offsets = distribute_offsets(ctx.boxes, "h" if horizontal else "v")
            ctx.push_undo()
            for ctx.si, (ctx.dx, ctx.dy) in zip(ctx.sel, offsets):
                if ctx.dx or ctx.dy:
                    ctx.strokes[ctx.si] = ctx.translate_stroke(ctx.strokes[ctx.si], ctx.dx, ctx.dy)
        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and (
        any(ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
            for ctx.k in ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                      "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                      "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                      "xform_rm_rect", "xform_rp_rect"))
    ):
        _matched = True
        # Numeric transform: focus/seed value field, or nudge via +/-.
        fields = ("x", "y", "w", "h", "r")
        handled_xform = False
        for fk in fields:
            if ctx.state.get(f"xform_{fk}_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                cur = ctx._xform_current_value(fk)
                if cur is not None:
                    if fk == "r":
                        seed = "0"
                    else:
                        seed = f"{cur:.3f}".rstrip("0").rstrip(".") or "0"
                    ctx.xform_field_focus = fk
                    ctx.xform_field_buffer = seed
                    ctx.state["xform_field_focus"] = fk
                    ctx.state["xform_field_buffer"] = seed
                handled_xform = True
                break
            if ctx.state.get(f"xform_{fk}m_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                ctx.step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
                ctx._apply_xform_field(fk, -ctx.step, relative=True)
                ctx.xform_field_focus = None
                ctx.xform_field_buffer = ""
                ctx.state["xform_field_focus"] = None
                ctx.state["xform_field_buffer"] = ""
                handled_xform = True
                break
            if ctx.state.get(f"xform_{fk}p_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                ctx.step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
                ctx._apply_xform_field(fk, ctx.step, relative=True)
                ctx.xform_field_focus = None
                ctx.xform_field_buffer = ""
                ctx.state["xform_field_focus"] = None
                ctx.state["xform_field_buffer"] = ""
                handled_xform = True
                break
        if handled_xform:
            ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.pending_transform_toggle = None
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and any(
        ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for ctx.k in ("width_profile_prev_rect", "width_profile_next_rect")
    ):
        _matched = True
        wk = "width_profile_prev_rect" if ctx.state.get("width_profile_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else "width_profile_next_rect"
        step_dir = -1 if wk == "width_profile_prev_rect" else 1
        profiles = list(WIDTH_PROFILES) if 'WIDTH_PROFILES' in ctx.globals() else ["uniform", "taper_in", "taper_out", "taper_both", "pressure"]
        if 'apply_width_profile' in ctx.globals():
            ctx.push_undo()
            for ctx.si in sorted(ctx.selected_strokes):
                if 0 <= ctx.si < len(ctx.strokes) and isinstance(ctx.strokes[ctx.si], dict):
                    cur = ctx.strokes[ctx.si].get("width_profile")
                    if cur not in profiles:
                        cur = "uniform"
                    ni = (profiles.index(cur) + step_dir) % len(profiles)
                    ctx.strokes[ctx.si] = apply_width_profile(ctx.strokes[ctx.si], profiles[ni])
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and any(
        ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for ctx.k in ("marker_start_rect", "marker_end_rect")
    ):
        _matched = True
        mk_key = "marker_start_rect" if ctx.state.get("marker_start_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else "marker_end_rect"
        ctx.end = "start" if mk_key == "marker_start_rect" else "end"
        ctx.marker_dropdown = None if ctx.marker_dropdown == ctx.end else ctx.end
        ctx.state["marker_dropdown"] = ctx.marker_dropdown
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and any(
        ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for ctx.k in ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
                  "dash_prev_rect", "dash_next_rect")
    ):
        _matched = True
        skey = ctx.next(ctx.k for ctx.k in ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
                                "dash_prev_rect", "dash_next_rect")
                    if ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
        if skey.startswith("cap_"):
            ctx.field, opts = "line_cap", ["butt", "round", "square"]
        elif skey.startswith("join_"):
            ctx.field, opts = "line_join", ["miter", "round", "bevel"]
        else:
            ctx.field, opts = "dash", [None, "dashed", "dotted"]
        step_dir = -1 if skey.endswith("_prev_rect") else 1
        ctx.push_undo()
        for ctx.si in sorted(ctx.selected_strokes):
            if 0 <= ctx.si < len(ctx.strokes) and isinstance(ctx.strokes[ctx.si], dict):
                updated = dict(ctx.strokes[ctx.si])
                cur = updated.get(ctx.field)
                if ctx.field == "dash" and cur not in opts:
                    cur = None
                if cur not in opts:
                    cur = opts[0]
                idx = (opts.index(cur) + step_dir) % len(opts)
                updated[ctx.field] = opts[idx]
                ctx.strokes[ctx.si] = updated
    elif ctx.tool_mode == "selection" and ctx.selected_strokes and ctx.state.get(
        "text_edit_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        _ti = ctx.next(ctx.iter(sorted(ctx.selected_strokes)), None)
        if _ti is not None and 0 <= _ti < len(ctx.strokes) and \
                isinstance(ctx.strokes[_ti], dict) and ctx.strokes[_ti].get("is_text"):
            _ts = ctx.strokes[_ti]
            # Re-open the text editor seeded with existing content.
            ctx.tool_mode = "draw"; ctx.draw_tool = "text"
            ctx.drawing = False; ctx.current_points = []
            ctx.text_family = _ts.get("font_family", ctx.text_family)
            ctx.text_size = float(_ts.get("font_size", ctx.text_size))
            ctx.text_entry = {"x": float(_ts.get("text_x", 0.0)),
                          "y": float(_ts.get("text_y", 0.0)),
                          "text": str(_ts.get("text_content", "")),
                          "family": ctx.text_family, "size": ctx.text_size,
                          "edit_index": _ti}
            ctx.selected_strokes.clear()
    elif ctx.tool_mode == "selection" and ctx.selected_strokes and ctx.state.get(
        "text_font_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        _ti = ctx.next(ctx.iter(sorted(ctx.selected_strokes)), None)
        if _ti is not None and 0 <= _ti < len(ctx.strokes) and \
                isinstance(ctx.strokes[_ti], dict) and ctx.strokes[_ti].get("is_text"):
            ctx.push_undo()
            _fams = tuple(ctx.FONT_FAMILIES)
            _cur = ctx.strokes[_ti].get("font_family", ctx.text_family)
            _next = _fams[(_fams.index(_cur) + 1) % len(_fams)] if _cur in _fams else _fams[0]
            ctx.strokes[_ti] = update_text_stroke(ctx.strokes[_ti], font_family=_next)
            ctx.text_family = _next
    elif ctx.tool_mode == "selection" and ctx.selected_strokes and any(
        ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for ctx.k in ("text_size_minus_rect", "text_size_plus_rect")):
        _matched = True
        _ti = ctx.next(ctx.iter(sorted(ctx.selected_strokes)), None)
        _key = "text_size_plus_rect" if ctx.state.get(
            "text_size_plus_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) \
            else "text_size_minus_rect"
        if _ti is not None and 0 <= _ti < len(ctx.strokes) and \
                isinstance(ctx.strokes[_ti], dict) and ctx.strokes[_ti].get("is_text"):
            ctx.push_undo()
            _sz = float(ctx.strokes[_ti].get("font_size", 36.0))
            _sz = max(4.0, min(400.0, _sz + (2.0 if _key == "text_size_plus_rect" else -2.0)))
            ctx.strokes[_ti] = update_text_stroke(ctx.strokes[_ti], font_size=_sz)
            ctx.text_size = _sz
    elif ctx.tool_mode == "selection" and ctx.state.get("text_on_path_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.sel = [ctx.i for ctx.i in sorted(ctx.selected_strokes) if 0 <= ctx.i < len(ctx.strokes)]
        if len(ctx.sel) == 2:
            ctx.a, ctx.b = ctx.strokes[ctx.sel[0]], ctx.strokes[ctx.sel[1]]
            text_i = path_i = None
            if isinstance(ctx.a, dict) and ctx.a.get("is_text") and not (isinstance(ctx.b, dict) and ctx.b.get("is_text")):
                text_i, path_i = ctx.sel[0], ctx.sel[1]
            elif isinstance(ctx.b, dict) and ctx.b.get("is_text") and not (isinstance(ctx.a, dict) and ctx.a.get("is_text")):
                text_i, path_i = ctx.sel[1], ctx.sel[0]
            if text_i is not None and path_i is not None:
                try:
                    from models.strokes import segs_of as _segs_of_tp
                    psegs = list(_segs_of_tp(ctx.strokes[path_i]) or [])
                except Exception:
                    psegs = list((ctx.strokes[path_i] or {}).get("segs") or [])
                if psegs:
                    try:
                        from models.text import set_text_path as _set_text_path
                        ctx.push_undo()
                        ctx.strokes[text_i] = _set_text_path(ctx.strokes[text_i], psegs, 0.0)
                        ctx.selected_strokes = {text_i}
                        ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
                    except Exception:
                        pass
    elif ctx.tool_mode == "selection" and ctx.state.get("text_off_path_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        if len(ctx.selected_strokes) == 1:
            _ti = ctx.next(ctx.iter(ctx.selected_strokes))
            if 0 <= _ti < len(ctx.strokes) and isinstance(ctx.strokes[_ti], dict) and ctx.strokes[_ti].get("is_text") and ctx.strokes[_ti].get("text_path"):
                try:
                    from models.text import clear_text_path as _clear_text_path
                    ctx.push_undo()
                    ctx.strokes[_ti] = _clear_text_path(ctx.strokes[_ti])
                except Exception:
                    pass
    elif ctx.tool_mode == "selection" and ctx.selected_strokes and ctx.state.get(
        "obj_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.bar = ctx.state["obj_opacity_rect"]
        ctx.opacity = ctx.clamp((event.pos[0] - ctx.bar.x) / max(1, ctx.bar.w - 1), 0.0, 1.0)
        ctx.push_undo()
        for ctx.si in sorted(ctx.selected_strokes):
            if 0 <= ctx.si < len(ctx.strokes) and isinstance(ctx.strokes[ctx.si], dict):
                ctx.strokes[ctx.si] = set_appearance(ctx.strokes[ctx.si], opacity=ctx.opacity)
        ctx.obj_opacity_drag = True
        ctx.state["obj_opacity_drag"] = True
    elif ctx.tool_mode == "selection" and ctx.selected_strokes and any(
        ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for ctx.k in ("shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")
    ):
        _matched = True
        appear_keys = ("shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")
        appear_key = ctx.next(ctx.k for ctx.k in appear_keys
                          if ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
        ctx.push_undo()
        for ctx.si in sorted(ctx.selected_strokes):
            if not (0 <= ctx.si < len(ctx.strokes)) or not isinstance(ctx.strokes[ctx.si], dict):
                continue
            app = get_appearance(ctx.strokes[ctx.si])
            if appear_key == "shadow_toggle_rect":
                ctx.shadow = app["shadow"] if app["shadow"] is not None else {
                    "dx": 6.0, "dy": 6.0, "blur": 6.0,
                    "opacity": 0.35, "color": (0.0, 0.0, 0.0, 1.0)}
                ctx.strokes[ctx.si] = set_appearance(ctx.strokes[ctx.si], shadow=ctx.shadow if app["shadow"] is None else None)
            else:
                ctx.shadow = app["shadow"]
                if ctx.shadow is None:
                    ctx.shadow = {"dx": 6.0, "dy": 6.0, "blur": 6.0,
                              "opacity": 0.35, "color": (0.0, 0.0, 0.0, 1.0)}
                ctx.step = -2.0 if appear_key == "shadow_blur_minus_rect" else 2.0
                ctx.shadow = dict(ctx.shadow)
                ctx.shadow["blur"] = max(0.0, min(64.0, float(ctx.shadow.get("blur", 4.0)) + ctx.step))
                ctx.strokes[ctx.si] = set_appearance(ctx.strokes[ctx.si], shadow=ctx.shadow)
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "nodes" and any(
        ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for ctx.k in ("path_close_rect", "path_reverse_rect", "path_add_rect",
                  "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                  "path_expand_rect")
    ):
        _matched = True
        path_keys = ("path_close_rect", "path_reverse_rect", "path_add_rect",
                     "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                     "path_expand_rect")
        path_key = ctx.next(ctx.k for ctx.k in path_keys
                        if ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
        sel_idx = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
        if sel_idx:
            ctx.si = sel_idx[0]
            ctx.st = ctx.strokes[ctx.si]
            ctx.seg_i, ctx.pname = ctx.selected_point if ctx.selected_point else (0, "p0")
            if ctx.pname not in ("p0", "p3"):
                ctx.pname = "p0" if ctx.pname == "c1" else "p3"
            ctx.seg_i = max(0, min(int(ctx.seg_i), len(segs_of(ctx.st)) - 1))
            ctx.push_undo()
            if path_key == "path_close_rect":
                ctx.strokes[ctx.si] = set_path_closed(ctx.st, not _is_closed_segs(segs_of(ctx.st)))
            elif path_key == "path_reverse_rect":
                ctx.strokes[ctx.si] = reverse_stroke(ctx.st)
            elif path_key == "path_add_rect":
                ctx.strokes[ctx.si] = add_anchor_at(ctx.st, ctx.seg_i, 0.5)
                ctx.selected_point = (ctx.seg_i, "p0")
            elif path_key == "path_delete_rect":
                ctx.strokes[ctx.si] = delete_anchor(ctx.st, ctx.seg_i, ctx.pname)
                ctx.selected_point = None
            elif path_key == "path_smooth_rect":
                ctx.strokes[ctx.si] = set_anchor_smooth(ctx.st, ctx.seg_i, ctx.pname, True)
            elif path_key == "path_expand_rect":
                expanded = expand_stroke_outline(ctx.st)
                if expanded is not None:
                    ctx.strokes[ctx.si] = expanded
                else:
                    # Nothing to expand (zero-width path): undo the push.
                    ctx.strokes[ctx.si] = ctx.st
                    if ctx.undo_stack:
                        ctx.undo_stack.pop()
                ctx.selected_point = None
            else:
                ctx.strokes[ctx.si] = set_anchor_smooth(ctx.st, ctx.seg_i, ctx.pname, False)
            ctx.transform_drag = None; ctx.drag_last = None
    elif ctx.tool_mode == "selection" and ctx.state.get("eyedropper_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.eyedropper_pick = not ctx.eyedropper_pick
        ctx.state["eyedropper_pick"] = ctx.eyedropper_pick
        ctx.cutting = False; ctx.cut_points = []
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.state.get("curve_join_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        if len(ctx.selected_curves) >= 2:
            by_stroke = {}
            for ctx.si, ctx.ci in list(ctx.selected_curves):
                by_stroke.setdefault(ctx.si, set()).add(int(ctx.ci))
            results = {}
            for ctx.si, ctx.idxs in by_stroke.items():
                if 0 <= ctx.si < len(ctx.strokes):
                    new_st, index_map = join_components_in_stroke(ctx.strokes[ctx.si], ctx.idxs)
                    if index_map is not None:
                        results[ctx.si] = (new_st, index_map, ctx.idxs)
            if results:
                ctx.push_undo()
                new_selected_curves = set()
                for ctx.si, ctx.idxs in by_stroke.items():
                    if ctx.si in results:
                        new_st, index_map, _idxs2 = results[ctx.si]
                        ctx.strokes[ctx.si] = new_st
                        for ctx.ci in ctx.idxs:
                            new_selected_curves.add((ctx.si, int(index_map.get(ctx.ci, ctx.ci))))
                    elif 0 <= ctx.si < len(ctx.strokes):
                        for ctx.ci in ctx.idxs:
                            new_selected_curves.add((ctx.si, int(ctx.ci)))
                ctx.selected_curves = new_selected_curves
                ctx.selected_curve = ctx.next(ctx.iter(ctx.selected_curves), None)
                ctx.selected_strokes = {ctx.si for ctx.si, _ in ctx.selected_curves}
        ctx.selected_point = None; ctx.transform_drag = None; ctx.drag_last = None
        ctx.eyedropper_pick = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.state.get("curve_cut_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        ctx.curve_cut_mode = not ctx.curve_cut_mode
        ctx.state["curve_cut_mode"] = ctx.curve_cut_mode
        ctx.cutting = False; ctx.cut_points = []
        ctx.selected_point = None; ctx.transform_drag = None; ctx.drag_last = None
        ctx.eyedropper_pick = False
    elif ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.state.get("curve_redraw_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        if ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
            ctx.si, ctx.comp_i = ctx.selected_curve
            ctx.fixed_start = ctx.fixed_end = None
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.segs = segs_of(ctx.strokes[ctx.si])
                ranges = _component_ranges(ctx.strokes[ctx.si])
                if 0 <= ctx.comp_i < len(ranges):
                    s0, ctx.s1 = ranges[ctx.comp_i]
                    if ctx.s1 > s0 and ctx.s1 <= len(ctx.segs):
                        ctx.fixed_start = tuple(ctx.segs[s0][0])
                        ctx.fixed_end = tuple(ctx.segs[ctx.s1 - 1][3])
            ctx.redrawing_curve = {
                "stroke_idx": ctx.si, "comp_idx": ctx.comp_i, "points": [],
                "started": False, "fixed_start": ctx.fixed_start, "fixed_end": ctx.fixed_end,
            }
            ctx.selected_point = None; ctx.transform_drag = None; ctx.drag_last = None
    return "handled" if _matched else None
