"""Transform fields / align / distribute / mirror panel actions."""
import copy, math, pygame
import config as cfg

from models.appearance import get_appearance, set_appearance
from models.geometry import distribute_offsets, expand_stroke_outline
from models.strokes import (
    WIDTH_PROFILES,
    _component_ranges,
    _is_closed_segs,
    add_anchor_at,
    apply_width_profile,
    delete_anchor,
    join_components_in_stroke,
    mirror_stroke,
    reverse_stroke,
    segs_of,
    set_anchor_smooth,
    set_path_closed,
)
from models.text import update_text_stroke

def _handle_panel_click_a_p2(ctx, event):
    if ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes and (
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
        skey = next(ctx.k for ctx.k in ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
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
        _ti = next(iter(sorted(ctx.selected_strokes)), None)
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
        _ti = next(iter(sorted(ctx.selected_strokes)), None)
        if _ti is not None and 0 <= _ti < len(ctx.strokes) and \
                isinstance(ctx.strokes[_ti], dict) and ctx.strokes[_ti].get("is_text"):
            ctx.push_undo()
            _fams = tuple(ctx.FONT_FAMILIES)
            _cur = ctx.strokes[_ti].get("font_family", ctx.text_family)
            _next = _fams[(_fams.index(_cur) + 1) % len(_fams)] if _cur in _fams else _fams[0]
            ctx.strokes[_ti] = update_text_stroke(ctx.strokes[_ti], font_family=_next)
            ctx.text_family = _next
    return None

def _handle_panel_click_a_p3(ctx, event):
    if ctx.tool_mode == "selection" and ctx.selected_strokes and any(
        ctx.state.get(ctx.k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for ctx.k in ("text_size_minus_rect", "text_size_plus_rect")):
        _matched = True
        _ti = next(iter(sorted(ctx.selected_strokes)), None)
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
            _ti = next(iter(ctx.selected_strokes))
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
        appear_key = next(ctx.k for ctx.k in appear_keys
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
        path_key = next(ctx.k for ctx.k in path_keys
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
                ctx.selected_curve = next(iter(ctx.selected_curves), None)
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
    return None



# Semantic aliases
handle_transform_align = _handle_panel_click_a_p2
handle_transform_nudge = _handle_panel_click_a_p3
