"""Controller: MOUSEBUTTONDOWN button 1 handler (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

# Canvas click helpers

def _handle_canvas_click(ctx, event):
    ctx.cpos = ctx.to_canvas(event.pos)
    if ctx.tool_mode == "draw":
        ctx.mods = pygame.key.get_mods()
        if (ctx.mods & pygame.KMOD_ALT) and ctx.reference_image and ctx.reference_image.get("visible", True):
            ctx.ref_drag = {"offset": (ctx.cpos[0] - ctx.reference_image.get("x", 0), ctx.cpos[1] - ctx.reference_image.get("y", 0))}
            ctx.drawing = False
        elif ctx.draw_tool == "eraser":
            hit_e = hit_test_stroke(ctx.cpos, ctx.strokes)
            if hit_e is not None:
                ctx.push_undo()
                ctx.strokes, _ = erase_curve_at(ctx.strokes, ctx.cpos)
            ctx.drawing = False
            ctx.current_points = []
            ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
        elif ctx.draw_tool == "bucket":
            # Geometric bucket fill (ray-casting/planar-face inspired): create a filled
            # vector shape for the enclosed region under the click, without a stroke.
            try:
                from models.fill import bucket_fill_to_beziers
                segs_fill = bucket_fill_to_beziers(ctx.strokes, ctx.cpos, simplify_epsilon=1.5, max_points=100)
                if segs_fill:
                    ctx.push_undo()
                    ctx.fill_color = (ctx.bucket_fill_color[0], ctx.bucket_fill_color[1],
                                  ctx.bucket_fill_color[2], 1.0)
                    new_st = ctx.new_stroke(
                        segs_fill,
                        stroke_color=(0.0, 0.0, 0.0, 0.0),
                        stroke_width=0.0,
                        fill_color=ctx.fill_color,
                        algorithm="fit",
                    )
                    ctx.strokes.append(new_st)
            except Exception:
                pass
            ctx.drawing = False
            ctx.current_points = []
            ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
        elif ctx.draw_tool == "cutter":
            # Razor: collect the swipe; curves are split on release.
            ctx.cutting = True
            ctx.cut_points = [ctx.cpos]
            ctx.drawing = False
            ctx.current_points = []
        elif ctx.draw_tool == "text":
            # Place a text insertion caret at the clicked point.
            if ctx.text_entry is not None:
                ctx.commit_text_entry()
            ctx.text_entry = {"x": ctx.cpos[0], "y": ctx.cpos[1], "text": "",
                          "family": ctx.text_family, "size": ctx.text_size}
            ctx.drawing = False
            ctx.current_points = []
            ctx.selected_strokes.clear(); ctx.selected_point = None
            ctx.selected_curve = None; ctx.selected_curves.clear()
        elif ctx.draw_tool == "pen" and ctx.draw_shape == "pen":
            # Bezier pen: click-to-place anchors, drag handles.
            ctx.shift_held = bool(ctx.mods & pygame.KMOD_SHIFT)
            ctx.pos = draw_snap_point(ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held)
            if ctx.pos is None:
                ctx.pos = ctx.snap_world(ctx.cpos)
            else:
                ctx.pos = ctx.snap_world(ctx.pos)
            now = pygame.time.get_ticks()
            is_double = (now - ctx._bezier_last_click.get("time", 0) < 400 and
                         math.hypot(ctx.pos[0] - ctx._bezier_last_click.get("pos", (1e9, 1e9))[0],
                                     ctx.pos[1] - ctx._bezier_last_click.get("pos", (1e9, 1e9))[1]) < 8.0)
            if ctx.bezier_pen and ctx._bezier_pen_near_first(ctx.pos, max(10.0, float(ctx.snap_radius() or 0))) and len(ctx.bezier_pen.get("anchors", [])) >= 3:
                # Close path: drag on first anchor adjusts its handles, finalize on mouseup.
                ctx.first = ctx.bezier_pen["anchors"][0]
                ctx.bezier_pen["mouse_down"] = True
                ctx.bezier_pen["dragging"] = True
                ctx.bezier_pen["dragging_first"] = True
                ctx.bezier_pen["down_pos"] = ctx.first["pt"]
                ctx.bezier_pen["preview_pt"] = ctx.pos
            elif is_double and ctx.bezier_pen and len(ctx.bezier_pen.get("anchors", [])) >= 2:
                ctx._bezier_pen_finish(close_path=False)
            else:
                ctx._bezier_pen_add_anchor(ctx.pos)
            ctx._bezier_last_click["time"] = now
            ctx._bezier_last_click["pos"] = ctx.pos
            ctx.drawing = False
            ctx.current_points = []
        else:
            # If starting a non-bezier drawing gesture, cancel unfinished bezier path.
            if ctx.bezier_pen is not None:
                ctx._bezier_pen_cancel()
            ctx.drawing = True
            ctx.shift_held = bool(ctx.mods & pygame.KMOD_SHIFT)
            start_pos = draw_snap_point(ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held)
            if start_pos is None:
                start_pos = ctx.snap_world(ctx.cpos)
            ctx.current_points = [start_pos]
    elif ctx.redrawing_curve is not None:
        # Redraw selected stroke/component: focused draw with snap features
        ctx.fixed_start = ctx.redrawing_curve.get("fixed_start")
        if ctx.fixed_start is not None:
            start_pos = tuple(ctx.fixed_start)
        else:
            ctx.shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            start_pos = draw_snap_point(ctx.cpos, ctx.strokes, ctx.snap_radius(), ctx.shift_held) or ctx.cpos
        ctx.redrawing_curve["points"] = [start_pos]
        ctx.redrawing_curve["started"] = True
    else:
        # Selection mode
        ctx.selected_point = None
        ctx.transform_drag = None
        ctx.mods = pygame.key.get_mods()
        ctx.shift = bool(ctx.mods & pygame.KMOD_SHIFT)
        if ctx.eyedropper_pick:
            hit = hit_test_stroke(ctx.cpos, ctx.strokes)
            if hit is not None and 0 <= hit < len(ctx.strokes):
                src_stroke = ctx.strokes[hit]
                src_comp_i = hit_test_component(src_stroke, ctx.cpos)
                if src_comp_i is None:
                    src_comp_i = 0
                src_sc, src_sw = _effective_component_style(src_stroke, src_comp_i)
                src_fc = src_stroke.get("fill_color")
                src_fg = copy.deepcopy(src_stroke.get("fill_gradient")) if isinstance(src_stroke, dict) else None
                src_comps = ctx._stroke_components(src_stroke)
                if 0 <= src_comp_i < len(src_comps):
                    src_dists = copy.deepcopy(_get_distortion_styles(src_comps[src_comp_i]))
                else:
                    src_dists = []
                had_sel = bool(ctx.selected_strokes)
                if not had_sel:
                    ctx.selected_strokes = {hit}
                    if ctx.selection_submode == "curve":
                        ctx.selected_curve = (hit, src_comp_i)
                    else:
                        ctx.selected_curve = None
                else:
                    ctx.push_undo()
                    for ctx.si in list(ctx.selected_strokes):
                        if not (0 <= ctx.si < len(ctx.strokes)):
                            continue
                        ctx.st = ctx.strokes[ctx.si]
                        ctx.st["stroke_width"] = float(src_sw)
                        ctx.st["fill_color"] = copy.deepcopy(src_fc) if src_fc is not None else None
                        ctx.st["fill_gradient"] = copy.deepcopy(src_fg) if src_fg is not None else None
                        # In curve submode, apply stroke style/waves to the
                        # selected component but keep fill at stroke level.
                        if (ctx.selection_submode == "curve" and ctx.selected_curve
                                and ctx.selected_curve[0] == ctx.si and len(ctx.selected_strokes) == 1):
                            ctx.ci = ctx.selected_curve[1]
                            ctx.comps = ctx._stroke_components(ctx.st)
                            if 0 <= ctx.ci < len(ctx.comps):
                                ctx.comps[ctx.ci] = copy.deepcopy(ctx.comps[ctx.ci])
                                ctx.comps[ctx.ci]["stroke_color"] = copy.deepcopy(src_sc)
                                ctx.comps[ctx.ci]["stroke_width"] = float(src_sw)
                                ctx.comps[ctx.ci].pop("wave", None)
                                ctx.comps[ctx.ci]["styles"] = [ctx.s for ctx.s in ctx.comps[ctx.ci].get("styles", []) if not _is_distortion_style(ctx.s)]
                                for ctx.wi, wv in enumerate(src_dists):
                                    ctx._set_distortion_style(ctx.comps[ctx.ci], wv, ctx.wi)
                                ctx.st["components"] = ctx.comps
                        else:
                            ctx.st["stroke_color"] = copy.deepcopy(src_sc)
                            ctx.comps = ctx._stroke_components(ctx.st)
                            if ctx.comps:
                                new_comps = []
                                for ctx.comp in ctx.comps:
                                    ctx.comp = copy.deepcopy(ctx.comp)
                                    # clear per-component stroke overrides to apply uniformly
                                    ctx.comp.pop("stroke_color", None)
                                    ctx.comp.pop("stroke_width", None)
                                    ctx.comp.pop("wave", None)
                                    ctx.comp["styles"] = [ctx.s for ctx.s in ctx.comp.get("styles", []) if not _is_distortion_style(ctx.s)]
                                    for ctx.wi, wv in enumerate(src_dists):
                                        ctx._set_distortion_style(ctx.comp, wv, ctx.wi)
                                    new_comps.append(ctx.comp)
                                ctx.st["components"] = new_comps
                ctx.eyedropper_pick = False
                ctx.state["eyedropper_pick"] = False
            # If the click missed, stay in pick mode.
        elif ctx.selection_submode == "curve":
            handled_curve = False
            # Curve mode: select/edit curves (components) only; node editing is in Nodes mode
            ctx.selected_point = None
            if ctx.curve_cut_mode and (ctx.selected_curves or ctx.selected_strokes):
                # Razor swipe across the selected curve/stroke.
                ctx.cutting = True
                ctx.cut_points = [ctx.cpos]
                handled_curve = True
            if not handled_curve:
                hit = hit_test_stroke(ctx.cpos, ctx.strokes)
                hit_curve = None
                if hit is not None and 0 <= hit < len(ctx.strokes):
                    ctx.comp_i = hit_test_component(ctx.strokes[hit], ctx.cpos)
                    if ctx.comp_i is not None:
                        hit_curve = (hit, int(ctx.comp_i))
                if hit_curve is not None:
                    if ctx.state.get("repeat_pick_mode") and ctx.state.get("repeat_pick_target"):
                        tgt = ctx.state.get("repeat_pick_target")
                        try:
                            tsi, tci, twi = int(tgt[0]), int(tgt[1]), int(tgt[2])
                        except Exception:
                            tsi, tci, twi = -1, -1, 0
                        if 0 <= tsi < len(ctx.strokes):
                            src_si, src_ci = hit_curve
                            src_comps = ctx._stroke_components(ctx.strokes[src_si])
                            if 0 <= src_ci < len(src_comps):
                                src_segs = src_comps[src_ci].get("segs") or []
                                rp = _segs_to_repeat_points(src_segs)
                                if rp:
                                    tgt_comps = ctx._stroke_components(ctx.strokes[tsi])
                                    if 0 <= tci < len(tgt_comps):
                                        tgt_comps[tci] = dict(tgt_comps[tci])
                                        ctx.w = ctx._get_distortion_style(tgt_comps[tci], twi)
                                        if ctx.w.get("type") == "thickness":
                                            ctx.w["thickness_points"] = rp
                                        else:
                                            ctx.w["repeat_points"] = rp
                                            ctx.w["type"] = "repeat"
                                        ctx.w["enabled"] = True
                                        ctx._set_distortion_style(tgt_comps[tci], ctx.w, twi)
                                        ctx.strokes[tsi]["components"] = tgt_comps
                        ctx.state["repeat_pick_mode"] = False
                        ctx.state["repeat_pick_target"] = None
                        ctx.repeat_pick_mode = False
                        ctx.repeat_pick_target = None
                        handled_curve = True
                    elif ctx.shift:
                        if hit_curve in ctx.selected_curves:
                            ctx.selected_curves.discard(hit_curve)
                            if ctx.selected_curve == hit_curve:
                                ctx.selected_curve = ctx.next(ctx.iter(ctx.selected_curves), None)
                        else:
                            ctx.selected_curves.add(hit_curve)
                            ctx.selected_curve = hit_curve
                        ctx.selected_strokes = {ctx.si for (ctx.si, _ci) in ctx.selected_curves}
                        handled_curve = True
                    else:
                        ctx.selected_curves = {hit_curve}
                        ctx.selected_curve = hit_curve
                        ctx.selected_strokes = {ctx.si for (ctx.si, _ci) in ctx.selected_curves}
                        handled_curve = True
                elif hit is None and not ctx.shift:
                    ctx.selected_curves.clear()
                    ctx.selected_curve = None
                    ctx.selected_strokes.clear()
            # keep active curve consistent with multi-selection
            if ctx.selected_curves and ctx.selected_curve not in ctx.selected_curves:
                ctx.selected_curve = ctx.next(ctx.iter(ctx.selected_curves), None)
            if not ctx.selected_curves:
                ctx.selected_curve = None
                # if a stroke was selected via other means, keep stroke selection only
                # when there are no curve hits; curve mode primarily tracks curves
                if handled_curve:
                    ctx.selected_strokes.clear()
        elif ctx.selection_submode == "transform":
            ctx.handled = False
            ctx.pending_transform_toggle = None
            if ctx.selected_strokes:
                ctx.bb = ctx.combined_obb(ctx.strokes, ctx.selected_strokes)
                # Gradient on-canvas handle hit-test (when editing fill gradient)
                if not ctx.handled and ctx.state.get("color_target", ctx.color_target) == "fill":
                    _g_primary = None
                    _g_grad = None
                    for ctx._gsi in sorted(ctx.selected_strokes):
                        if 0 <= ctx._gsi < len(ctx.strokes):
                            ctx._gst = ctx.strokes[ctx._gsi]
                            ctx._gfg = ctx._gst.get("fill_gradient") if isinstance(ctx._gst, dict) else None
                            try:
                                ctx._gfg = ctx.get_fill_gradient(ctx._gst) or ctx._gfg
                            except Exception:
                                pass
                            if isinstance(ctx._gfg, dict) and str(ctx._gfg.get("type")) in ("linear", "radial", "conic", "spiral", "diamond", "square"):
                                _g_primary = ctx._gsi
                                _g_grad = ctx._gfg
                                break
                    if _g_primary is not None and _g_grad is not None:
                        _ghit, _ginfo = ctx.hit_test_gradient_handle(ctx.strokes[_g_primary], _g_grad, ctx.cpos)
                        if _ghit is not None:
                            ctx.push_undo()
                            _gtype = str(_g_grad.get("type", "linear"))
                            _edit_strokes = []
                            for ctx._gsi in sorted(ctx.selected_strokes):
                                if 0 <= ctx._gsi < len(ctx.strokes):
                                    ctx._gst = ctx.strokes[ctx._gsi]
                                    _fg2 = ctx._gst.get("fill_gradient") if isinstance(ctx._gst, dict) else None
                                    try:
                                        _fg2 = ctx.get_fill_gradient(ctx._gst) or _fg2
                                    except Exception:
                                        pass
                                    if isinstance(_fg2, dict) and str(_fg2.get("type")) == _gtype:
                                        _edit_strokes.append(ctx._gsi)
                            if not _edit_strokes:
                                _edit_strokes = [_g_primary]
                            ctx.gradient_drag = {
                                "handle": _ghit,
                                "stroke_is": _edit_strokes,
                                "grad_type": _gtype,
                                "primary_i": _g_primary,
                                "bbox": (_ginfo or {}).get("bbox"),
                            }
                            ctx.handled = True
                if ctx.bb:
                    eff_pivot = ctx.pivot_pos if ctx.pivot_pos is not None else (ctx.bb["cx"], ctx.bb["cy"])
                    # hit pivot marker first (draggable rotation/scale center)
                    if not ctx.handled and math.hypot(ctx.cpos[0] - eff_pivot[0], ctx.cpos[1] - eff_pivot[1]) <= 10.0:
                        ctx.pivot_drag = {"start": ctx.cpos, "start_pivot": eff_pivot}
                        ctx.handled = True
                    if not ctx.handled:
                        ctx.h = hit_test_bbox_handle(ctx.bb, ctx.cpos, mode=ctx.transform_handle_mode)
                        if ctx.h is not None:
                            ctx.cx, ctx.cy = eff_pivot
                            ctx.push_undo()
                            import copy as _copy
                            ctx.start_strokes = {ctx.i: _copy.deepcopy(ctx.strokes[ctx.i]) for ctx.i in sorted(ctx.selected_strokes) if 0 <= ctx.i < len(ctx.strokes)}
                            ctx.transform_drag = {
                                "handle": ctx.h,
                                "start_mouse": ctx.cpos,
                                "start_strokes": ctx.start_strokes,
                                "center": (ctx.cx, ctx.cy),
                                "start_bbox": ctx.bb,
                                "mode": ctx.transform_handle_mode,
                            }
                            ctx.handled = True
                        elif point_in_bbox(ctx.bb, ctx.cpos):
                            # click on selected body: move on drag, toggle scale/rotate mode on click-without-drag
                            ctx.pending_transform_toggle = {
                                "start": ctx.cpos,
                                "moved": False,
                                "primed": True,
                            }
                            ctx.handled = True
                elif not ctx.handled and hit_test_stroke(ctx.cpos, ctx.strokes) in ctx.selected_strokes:
                    ctx.pending_transform_toggle = {"start": ctx.cpos, "moved": False, "primed": True}
                    ctx.handled = True
            if not ctx.handled:
                hit = hit_test_stroke(ctx.cpos, ctx.strokes)
                if hit is not None:
                    _gid = group_id_of(ctx.strokes[hit]) if 0 <= hit < len(ctx.strokes) else None
                    _members = set(group_members(ctx.strokes, _gid)) if _gid else {hit}
                    if ctx.shift:
                        if hit in ctx.selected_strokes:
                            ctx.selected_strokes -= _members
                        else:
                            ctx.selected_strokes |= _members
                        ctx.drag_last = None
                    else:
                        ctx.selected_strokes = set(_members)
                    if ctx.selected_strokes:
                        ctx.primary_i = sorted(ctx.selected_strokes)[0]
                        if 0 <= ctx.primary_i < len(ctx.strokes):
                            ctx.width_slider.value = int(round(ctx.strokes[ctx.primary_i].get("stroke_width", 3)))
                        # allow immediate drag-move of newly selected (no toggle)
                        ctx.drag_last = ctx.cpos
                    else:
                        ctx.drag_last = None
                else:
                    # start marquee selection on empty area
                    ctx.marquee_select = {"start": ctx.cpos, "current": ctx.cpos, "add": ctx.shift}
                    ctx.drag_last = None
        else:
            # Nodes mode: point editing only for single selection
            if len(ctx.selected_strokes) == 1:
                ctx.only = ctx.next(ctx.iter(ctx.selected_strokes))
                if 0 <= ctx.only < len(ctx.strokes):
                    try:
                        disp_segs = stroke_display_segs(ctx.strokes[ctx.only]) if 'stroke_display_segs' in ctx.globals() else None
                    except Exception:
                        disp_segs = None
                    pt_hit = hit_test_point(ctx.strokes[ctx.only], ctx.cpos, segs_override=disp_segs)
                    if pt_hit is not None:
                        ctx.push_undo()
                        ctx.selected_point = pt_hit; ctx.drag_last = ctx.cpos
                    else:
                        hit = hit_test_stroke(ctx.cpos, ctx.strokes)
                        if hit == ctx.only:
                            ctx.drag_last = ctx.cpos
                        elif hit is not None:
                            if ctx.shift:
                                if hit in ctx.selected_strokes:
                                    ctx.selected_strokes.discard(hit)
                                else:
                                    ctx.selected_strokes.add(hit)
                            else:
                                ctx.selected_strokes = {hit}
                            if ctx.selected_strokes:
                                ctx.primary_i = sorted(ctx.selected_strokes)[0]
                                if 0 <= ctx.primary_i < len(ctx.strokes):
                                    ctx.width_slider.value = int(round(ctx.strokes[ctx.primary_i].get("stroke_width", 3)))
                            ctx.drag_last = ctx.cpos if hit is not None else None
                        else:
                            if not ctx.shift:
                                ctx.selected_strokes.clear()
                            ctx.drag_last = None
                else:
                    ctx.selected_strokes.clear(); ctx.drag_last = None
            else:
                # multi or none: selection changes only
                hit = hit_test_stroke(ctx.cpos, ctx.strokes)
                if hit is not None:
                    if ctx.shift:
                        if hit in ctx.selected_strokes:
                            ctx.selected_strokes.discard(hit)
                        else:
                            ctx.selected_strokes.add(hit)
                    else:
                        ctx.selected_strokes = {hit}
                    if ctx.selected_strokes:
                        ctx.primary_i = sorted(ctx.selected_strokes)[0]
                        if 0 <= ctx.primary_i < len(ctx.strokes):
                            ctx.width_slider.value = int(round(ctx.strokes[ctx.primary_i].get("stroke_width", 3)))
                    ctx.drag_last = ctx.cpos
                else:
                    if not ctx.shift:
                        ctx.selected_strokes.clear()
                    ctx.drag_last = None
    return None

