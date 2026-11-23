"""Controller: mouse motion handler (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

def handle_mousemotion(ctx, event):
    if True:  # MOUSEMOTION
        if ctx.guide_drag is not None:
            _gp = ctx.to_canvas(event.pos)
            _gval = _gp[0] if ctx.guide_drag.get("axis") == "x" else _gp[1]
            guides = ctx.move_guide(guides, ctx.guide_drag.get("index", 0), _gval)
            return
        if ctx.cutting:
            cpos = ctx.clamp_to_canvas(event.pos)
            if not ctx.cut_points or math.hypot(cpos[0] - ctx.cut_points[-1][0],
                                            cpos[1] - ctx.cut_points[-1][1]) >= 1.0:
                ctx.cut_points.append(cpos)
            return
        if ctx.pan_drag is not None:
            sm = ctx.pan_drag["start_mouse"]; sp = ctx.pan_drag["start_pan"]
            cfg.VIEW_PAN_X = sp[0] + (event.pos[0] - sm[0])
            cfg.VIEW_PAN_Y = sp[1] + (event.pos[1] - sm[1])
            return
        if ctx.pivot_drag is not None and pygame.mouse.get_pressed()[0]:
            cpos = ctx.clamp_to_canvas(event.pos)
            sp0 = ctx.pivot_drag.get("start_pivot", cpos)
            sm = ctx.pivot_drag.get("start", cpos)
            pivot_pos = (sp0[0] + cpos[0] - sm[0], sp0[1] + cpos[1] - sm[1])
            return
        if ctx.ref_opacity_drag and ctx.reference_image is not None:
            bar = ctx.state.get("ref_opacity_rect", pygame.Rect(0,0,0,0))
            if bar.w > 0:
                ctx.reference_image["opacity"] = ctx.clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
        elif ctx.obj_opacity_drag and ctx.selected_strokes:
            bar = ctx.state.get("obj_opacity_rect", pygame.Rect(0,0,0,0))
            if bar.w > 0:
                opacity = ctx.clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
                for si in sorted(ctx.selected_strokes):
                    if 0 <= si < len(ctx.strokes) and isinstance(ctx.strokes[si], dict):
                        ctx.strokes[si] = ctx.set_appearance(ctx.strokes[si], opacity=opacity)
        elif ctx.bucket_picker_drag is not None:
            if ctx.bucket_picker_drag == "sv":
                ctx.bucket_pick(ctx.state.get("bucket_sv_rect", pygame.Rect(0,0,0,0)), event.pos, "sv")
            else:
                ctx.bucket_pick(ctx.state.get("bucket_hue_rect", pygame.Rect(0,0,0,0)), event.pos, "hue")
        elif ctx.ref_drag is not None and ctx.reference_image is not None and (pygame.mouse.get_pressed()[0]):
            cpos = ctx.clamp_to_canvas(event.pos)
            off = ctx.ref_drag.get("offset", (0, 0))
            ctx.reference_image["x"] = cpos[0] - off[0]
            ctx.reference_image["y"] = cpos[1] - off[1]
        elif wave_custom_drag is not None and pygame.mouse.get_pressed()[0] and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
            # hold-drag painting inside the custom wave/profile box
            box = ctx.state.get("wave_custom_box_rect", pygame.Rect(0, 0, 0, 0))
            if box.w > 0 and box.h > 0:
                si, comp_i = ctx.selected_curve
                if 0 <= si < len(ctx.strokes):
                    comps = ctx._stroke_components(ctx.strokes[si])
                    if 0 <= comp_i < len(comps):
                        comps[comp_i] = dict(comps[comp_i])
                        wi = int(ctx.state.get("wave_active_index", 0) or 0)
                        w = ctx._get_distortion_style(comps[comp_i], wi)
                        wave_custom_drag = ctx._custom_wave_paint(w, box, event.pos, wave_custom_drag)
                        ctx.state["wave_custom_drag"] = wave_custom_drag
                        ctx._set_distortion_style(comps[comp_i], w, wi)
                        ctx.strokes[si]["components"] = comps
        elif ctx.wave_slider_drag is not None and pygame.mouse.get_pressed()[0] and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
            d = ctx.wave_slider_drag
            si, comp_i = d.get("si"), d.get("comp_i")
            key = d.get("key")
            r = d.get("rect")
            lo, hi = d.get("lo", 0.0), d.get("hi", 1.0)
            wi = int(d.get("wi", 0) or 0)
            if 0 <= si < len(ctx.strokes) and 0 <= comp_i < len(ctx._stroke_components(ctx.strokes[si])):
                comps = ctx._stroke_components(ctx.strokes[si])
                comps[comp_i] = dict(comps[comp_i])
                w = ctx._get_distortion_style(comps[comp_i], wi)
                t = (event.pos[0] - r.x) / max(1, r.w - 1)
                val = lo + ctx.clamp(t, 0.0, 1.0) * (hi - lo)
                if key in ("amplitude", "noise", "phase", "seed", "amount", "location", "handle_rotate", "handle_length"):
                    val = float(int(round(val)))
                elif key in ("frequency", "noise_scale"):
                    val = float(val)
                else:
                    val = float(val)
                w[key] = val
                ctx._set_distortion_style(comps[comp_i], w, wi)
                ctx.strokes[si]["components"] = comps
        elif (ctx.picker_drag_sv or ctx.picker_drag_hue or ctx.picker_drag_alpha) and ctx.selected_strokes and (ctx.selection_submode == "transform" or (ctx.selection_submode == "curve" and ctx.selected_curve)):
            color_target = ctx.state.get("color_target", color_target)
            sel_list = sorted(ctx.selected_strokes)
            comp_style_target = None
            if ctx.selection_submode == "curve" and ctx.selected_curve and len(ctx.selected_strokes) == 1 and ctx.selected_curve[0] in ctx.selected_strokes:
                comp_style_target = ctx.selected_curve
                color_target = "stroke"
                ctx.state["color_target"] = "stroke"
            def _apply_comp_stroke_color_drag(si, ci, rgb, alpha):
                comps = ctx._stroke_components(ctx.strokes[si])
                if 0 <= ci < len(comps):
                    comps[ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
                    ctx.strokes[si]["components"] = comps
            if ctx.picker_drag_sv:
                sv = ctx.state["sv_rect"]
                picker_s = ctx.clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
                picker_v = ctx.clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
                col = ctx.hsv_to_rgb(picker_h, picker_s, picker_v)
                if comp_style_target is not None:
                    si, ci = comp_style_target
                    if 0 <= si < len(ctx.strokes):
                        cur_sc, _ = ctx._effective_component_style(ctx.strokes[si], ci)
                        alpha = ctx.color_alpha(cur_sc, 1.0)
                        _apply_comp_stroke_color_drag(si, ci, col, alpha)
                else:
                    for si in sel_list:
                        if 0 <= si < len(ctx.strokes):
                            if color_target == "stroke":
                                alpha = ctx.color_alpha(ctx.strokes[si].get("stroke_color"), 1.0)
                                ctx.strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                            else:
                                fg = ctx.get_fill_gradient(ctx.strokes[si]) if 'get_fill_gradient' in globals() else None
                                if fg is not None:
                                    stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                    alpha = ctx.color_alpha(ctx.get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                    ctx.strokes[si]["fill_gradient"] = ctx.set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                else:
                                    alpha = ctx.color_alpha(ctx.strokes[si].get("fill_color"), 1.0)
                                    ctx.strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                    ctx.strokes[si]["fill_gradient"] = None
                ctx.state["picker_h"] = picker_h; ctx.state["picker_s"] = picker_s; ctx.state["picker_v"] = picker_v
            elif ctx.picker_drag_hue:
                hr = ctx.state["hue_rect"]
                picker_h = ctx.clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
                col = ctx.hsv_to_rgb(picker_h, picker_s, picker_v)
                if comp_style_target is not None:
                    si, ci = comp_style_target
                    if 0 <= si < len(ctx.strokes):
                        cur_sc, _ = ctx._effective_component_style(ctx.strokes[si], ci)
                        alpha = ctx.color_alpha(cur_sc, 1.0)
                        _apply_comp_stroke_color_drag(si, ci, col, alpha)
                else:
                    for si in sel_list:
                        if 0 <= si < len(ctx.strokes):
                            if color_target == "stroke":
                                alpha = ctx.color_alpha(ctx.strokes[si].get("stroke_color"), 1.0)
                                ctx.strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                            else:
                                fg = ctx.get_fill_gradient(ctx.strokes[si]) if 'get_fill_gradient' in globals() else None
                                if fg is not None:
                                    stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                    alpha = ctx.color_alpha(ctx.get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1), 1.0)
                                    ctx.strokes[si]["fill_gradient"] = ctx.set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals() else fg
                                else:
                                    alpha = ctx.color_alpha(ctx.strokes[si].get("fill_color"), 1.0)
                                    ctx.strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                    ctx.strokes[si]["fill_gradient"] = None
                ctx.state["picker_h"] = picker_h; ctx.state["picker_s"] = picker_s; ctx.state["picker_v"] = picker_v
            elif ctx.picker_drag_alpha:
                ar = ctx.state.get("alpha_rect", pygame.Rect(0,0,0,0))
                new_alpha = ctx.clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
                if comp_style_target is not None:
                    si, ci = comp_style_target
                    if 0 <= si < len(ctx.strokes):
                        cur_sc, _ = ctx._effective_component_style(ctx.strokes[si], ci)
                        base = ctx.color_rgb(cur_sc, (0.1,0.1,0.15))
                        _apply_comp_stroke_color_drag(si, ci, base, new_alpha)
                else:
                    for si in sel_list:
                        if 0 <= si < len(ctx.strokes):
                            if color_target == "stroke":
                                ctx.strokes[si]["stroke_color"] = ctx.set_color_alpha(ctx.strokes[si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                            else:
                                fg = ctx.get_fill_gradient(ctx.strokes[si]) if 'get_fill_gradient' in globals() else None
                                if fg is not None:
                                    stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                    cstop = ctx.get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals() else (0,0,0,1)
                                    ctx.strokes[si]["fill_gradient"] = ctx.set_gradient_stop_color(fg, stop_i, (cstop[0], cstop[1], cstop[2], new_alpha)) if 'set_gradient_stop_color' in globals() else fg
                                elif ctx.strokes[si].get("fill_color") is not None:
                                    ctx.strokes[si]["fill_color"] = ctx.set_color_alpha(ctx.strokes[si].get("fill_color"), new_alpha)
        elif ctx.fill_stop_pos_drag and ctx.selected_strokes and (ctx.selection_submode == "transform" or (ctx.selection_submode == "curve" and ctx.selected_curve and color_target == "fill")):
            pr = ctx.state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
            if pr.w > 1:
                rel = (event.pos[0] - pr.x) / max(1, pr.w - 1)
            else:
                rel = 0.0
            rel = ctx.clamp(rel, 0.0, 1.0)
            cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
            sel_list = sorted(set(int(x) for x in (ctx.selected_strokes or [])))
            primary_si = sel_list[0] if sel_list else -1
            primary_obj = ctx.strokes[primary_si] if (0 <= primary_si < len(ctx.strokes)) else None
            if primary_obj is not None and 'set_gradient_stop_pos' in globals():
                for si in sel_list:
                    if 0 <= si < len(ctx.strokes):
                        sfg = ctx.get_fill_gradient(ctx.strokes[si]) if 'get_fill_gradient' in globals() else None
                        if sfg is not None:
                            sidx = ctx.clamp_gradient_stop_index(sfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                            ng, _ni = ctx.set_gradient_stop_pos(sfg, sidx, rel)
                            ctx.strokes[si]["fill_gradient"] = ng
                            ctx.strokes[si]["fill_color"] = None
                pfg2 = ctx.get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals() else None
                if pfg2 is not None:
                    sidx = ctx.clamp_gradient_stop_index(pfg2, cur_stop_i) if 'clamp_gradient_stop_index' in globals() else cur_stop_i
                    _ngp, ni = ctx.set_gradient_stop_pos(pfg2, sidx, rel)
                    ctx.state["fill_gradient_stop"] = ni
                    fc = ctx.get_gradient_stop_color(_ngp, ni) if 'get_gradient_stop_color' in globals() else (1.0, 1.0, 1.0, 1.0)
                    picker_h, picker_s, picker_v = ctx.rgb_to_hsv(*fc)
                    ctx.state["picker_h"] = picker_h; ctx.state["picker_s"] = picker_s; ctx.state["picker_v"] = picker_v
        elif ctx.redrawing_curve is not None and ctx.redrawing_curve.get("started") and pygame.mouse.get_pressed()[0]:
            cpos = ctx.clamp_to_canvas(event.pos)
            pts = ctx.redrawing_curve.get("points", [])
            fixed_start = ctx.redrawing_curve.get("fixed_start")
            fixed_end = ctx.redrawing_curve.get("fixed_end")
            if fixed_start is not None and pts:
                pts[0] = tuple(fixed_start)
            keys = pygame.key.get_pressed()
            straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
            shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            pts = ctx.advance_drawing_points(pts, cpos, ctx.strokes, ctx.snap_radius(), shift_held, straight_line, fixed_end=fixed_end)
            ctx.redrawing_curve["points"] = pts
        elif ctx.marquee_select is not None and ctx.tool_mode == "selection" and pygame.mouse.get_pressed()[0]:
            ctx.marquee_select["current"] = ctx.clamp_to_canvas(event.pos)
        elif ctx.tool_mode == "draw" and ctx.draw_tool == "pen" and ctx.draw_shape == "pen" and ctx.bezier_pen is not None:
            cpos = ctx.clamp_to_canvas(event.pos)
            shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            if ctx.bezier_pen.get("mouse_down") and ctx.bezier_pen.get("dragging"):
                # Dragging handle: follow cursor (grid snap only), don't object-snap.
                cpos = ctx.snap_world(cpos)
                ctx._bezier_pen_update_drag(cpos)
            else:
                # Preview next anchor position with object snap.
                sp = ctx.draw_snap_point(cpos, ctx.strokes, ctx.snap_radius(), shift_held)
                pos = ctx.snap_world(sp if sp is not None else cpos)
                ctx.bezier_pen["preview_pt"] = pos
        elif ctx.drawing and ctx.tool_mode == "draw" and ctx.draw_tool == "pen":
            cpos = ctx.clamp_to_canvas(event.pos)
            cpos = ctx.snap_world(cpos)
            shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            keys = pygame.key.get_pressed()
            straight_line = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) if keys else False
            current_points = ctx.advance_drawing_points(current_points, cpos, ctx.strokes, ctx.snap_radius(), shift_held, straight_line)
        elif ctx.tool_mode == "selection" and pending_transform_toggle is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
            cpos = ctx.clamp_to_canvas(event.pos)
            ptt = pending_transform_toggle
            if not ptt.get("moved"):
                dx0 = cpos[0] - ptt["start"][0]; dy0 = cpos[1] - ptt["start"][1]
                if math.hypot(dx0, dy0) >= 4.0:
                    # threshold exceeded: start move drag instead of mode toggle
                    ptt["moved"] = True
                    pending_transform_toggle = None
                    if drag_last is None:
                        ctx.push_undo()
                    drag_last = ptt["start"]
                    # apply initial delta
                    dx = cpos[0] - drag_last[0]; dy = cpos[1] - drag_last[1]
                    if dx != 0 or dy != 0:
                        dx, dy, smart_snap_guides = ctx._snap_move_delta(ctx.selected_strokes, dx, dy)
                    else:
                        smart_snap_guides = []
                    if dx != 0 or dy != 0:
                        for si in list(ctx.selected_strokes):
                            if 0 <= si < len(ctx.strokes):
                                ctx.strokes[si] = ctx.translate_stroke(ctx.strokes[si], dx, dy)
                        drag_last = (drag_last[0] + dx, drag_last[1] + dy)
                    else:
                        drag_last = cpos
            # if not yet moved, wait for threshold or mouseup (toggle)
        elif ctx.tool_mode == "selection" and ctx.gradient_drag is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
            cpos = ctx.clamp_to_canvas(event.pos)
            gd = ctx.gradient_drag
            ghandle = gd.get("handle")
            gtype = gd.get("grad_type")
            for si in list(gd.get("stroke_is") or []):
                if not (0 <= si < len(ctx.strokes)):
                    continue
                st = ctx.strokes[si]
                fg = st.get("fill_gradient") if isinstance(st, dict) else None
                try:
                    fg = ctx.get_fill_gradient(st) or fg
                except Exception:
                    pass
                if not isinstance(fg, dict) or str(fg.get("type")) != str(gtype):
                    continue
                try:
                    bx0, by0, bx1, by1 = ctx.gradient_edit_bbox(st)
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
                        fg2 = ctx.normalize_gradient(fg2)
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
                    gcx = bx0 + ctx.clamp(rcx, 0.0, 1.0) * bw
                    gcy = by0 + ctx.clamp(rcy, 0.0, 1.0) * bh
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
                        ncx = ctx.clamp((cpos[0] - bx0) / bw, 0.0, 1.0)
                        ncy = ctx.clamp((cpos[1] - by0) / bh, 0.0, 1.0)
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
                        ncx = ctx.clamp((cpos[0] - bx0) / bw, 0.0, 1.0)
                        ncy = ctx.clamp((cpos[1] - by0) / bh, 0.0, 1.0)
                        fg2["center"] = [ncx, ncy]
                    try:
                        fg2 = ctx.normalize_gradient(fg2)
                    except Exception:
                        pass
                    st["fill_gradient"] = fg2
            # keep UI fill ctx.state in sync for primary gradient
            if ctx.selected_strokes:
                try:
                    _ps = sorted(ctx.selected_strokes)[0]
                    if 0 <= _ps < len(ctx.strokes):
                        ctx.refresh_selection_ui_state(_ps)
                except Exception:
                    pass
        elif ctx.tool_mode == "selection" and ctx.transform_drag is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
            cpos = ctx.clamp_to_canvas(event.pos)
            td = ctx.transform_drag
            cx, cy = td["center"]  # pivot/rotation center
            sx0, sy0 = td["start_mouse"]
            h = td["handle"]
            # snap scale/skew handle drags to nearby geometry and show alignment guides
            if h != "rot" and not str(h).startswith("rot_"):
                _sr = ctx.snap_radius()
                if _sr > 0:
                    _sel_set = set(ctx.selected_strokes)
                    _other = [s for _i, s in enumerate(ctx.strokes) if _i not in _sel_set]
                    if _other:
                        _sp = ctx.nearest_snap_point(cpos, _other, _sr)
                        if _sp is not None:
                            cpos = _sp
                        smart_snap_guides = ctx._alignment_guides_for_point(cpos, _other, _sr)
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
                    if 0 <= i < len(ctx.strokes):
                        ctx.strokes[i] = ctx.rotate_stroke_around(st0, cx, cy, delta)
            elif is_skew:
                # Skew around pivot/center in local axes
                lmx, lmy = _local_around((cx, cy), cpos)
                lsx, lsy = _local_around((cx, cy), (sx0, sy0))
                skew_x = skew_y = 0.0
                denom_y = lsy if abs(lsy) > 1e-6 else (1e-6 if lsy >= 0 else -1e-6)
                denom_x = lsx if abs(lsx) > 1e-6 else (1e-6 if lsx >= 0 else -1e-6)
                if h == "skew_n":
                    skew_x = ctx.clamp((lmx - lsx) / denom_y, -5.0, 5.0)
                elif h == "skew_s":
                    skew_x = ctx.clamp((lmx - lsx) / denom_y, -5.0, 5.0)
                elif h == "skew_e":
                    skew_y = ctx.clamp((lmy - lsy) / denom_x, -5.0, 5.0)
                elif h == "skew_w":
                    skew_y = ctx.clamp((lmy - lsy) / denom_x, -5.0, 5.0)
                for i, st0 in start_strokes.items():
                    if 0 <= i < len(ctx.strokes):
                        ctx.strokes[i] = ctx.skew_stroke_local(st0, (cx, cy), ang, skew_x, skew_y)
            else:
                # scale handles
                # fixed point: opposite anchor in world (default) or pivot/center if Shift
                if shift_held:
                    fx, fy = cx, cy
                else:
                    lax, lay = ctx.bbox_handle_anchor_local(h, bb0)
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
                su = ctx.clamp(su, -20.0, 20.0)
                sv = ctx.clamp(sv, -20.0, 20.0)
                # avoid total collapse
                if abs(su) < 0.02: su = 0.02 if su >= 0 else -0.02
                if abs(sv) < 0.02: sv = 0.02 if sv >= 0 else -0.02
                for i, st0 in start_strokes.items():
                    if 0 <= i < len(ctx.strokes):
                        ctx.strokes[i] = ctx.scale_stroke_local(st0, (fx, fy), ang, su, sv)
        elif ctx.tool_mode == "selection" and drag_last is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
            cpos = ctx.clamp_to_canvas(event.pos)
            if ctx.selection_submode == "nodes" and ctx.selected_point is not None and len(ctx.selected_strokes) == 1:
                only = next(iter(ctx.selected_strokes))
                seg_i, pname = ctx.selected_point
                if 0 <= only < len(ctx.strokes):
                    ctx.strokes[only] = ctx.set_stroke_point(ctx.strokes[only], seg_i, pname, cpos)
                drag_last = cpos
            elif ctx.selection_submode in ("transform", "nodes"):
                # In nodes mode, dragging the stroke (not a point) moves it; curve mode has no drag-move here
                if ctx.selection_submode == "nodes" and ctx.selected_point is not None:
                    pass
                else:
                    dx = cpos[0] - drag_last[0]; dy = cpos[1] - drag_last[1]
                    if dx != 0 or dy != 0:
                        dx, dy, smart_snap_guides = ctx._snap_move_delta(ctx.selected_strokes, dx, dy)
                    else:
                        smart_snap_guides = []
                    if dx != 0 or dy != 0:
                        for si in list(ctx.selected_strokes):
                            if 0 <= si < len(ctx.strokes):
                                ctx.strokes[si] = ctx.translate_stroke(ctx.strokes[si], dx, dy)
                        drag_last = (drag_last[0] + dx, drag_last[1] + dy)
                    else:
                        drag_last = cpos
            else:
                drag_last = cpos
        # (translation handled above when drag_last is set)

