"""Split helpers for mouse_motion (SRP)."""
import copy, math, pygame
import config as cfg


def mm_part1(ctx, event):
    if ctx.guide_drag is not None:
        _gp = ctx.to_canvas(event.pos)
        _gval = _gp[0] if ctx.guide_drag.get("axis") == "x" else _gp[1]
        ctx.guides = ctx.move_guide(ctx.guides, ctx.guide_drag.get("index", 0), _gval)
        return True
    if ctx.cutting:
        cpos = ctx.clamp_to_canvas(event.pos)
        if not ctx.cut_points or math.hypot(cpos[0] - ctx.cut_points[-1][0],
                                        cpos[1] - ctx.cut_points[-1][1]) >= 1.0:
            ctx.cut_points.append(cpos)
        return True
    if ctx.pan_drag is not None:
        sm = ctx.pan_drag["start_mouse"]; sp = ctx.pan_drag["start_pan"]
        cfg.VIEW_PAN_X = sp[0] + (event.pos[0] - sm[0])
        cfg.VIEW_PAN_Y = sp[1] + (event.pos[1] - sm[1])
        return True
    if ctx.pivot_drag is not None and pygame.mouse.get_pressed()[0]:
        cpos = ctx.clamp_to_canvas(event.pos)
        sp0 = ctx.pivot_drag.get("start_pivot", cpos)
        sm = ctx.pivot_drag.get("start", cpos)
        ctx.pivot_pos = (sp0[0] + cpos[0] - sm[0], sp0[1] + cpos[1] - sm[1])
        return True
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
    return False


def mm_part2(ctx, event):
    if ctx.wave_custom_drag is not None and pygame.mouse.get_pressed()[0] and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
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
                    ctx.wave_custom_drag = ctx._custom_wave_paint(w, box, event.pos, ctx.wave_custom_drag)
                    ctx.state["ctx.wave_custom_drag"] = ctx.wave_custom_drag
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
    return False

from controllers.mouse_motion_parts2 import mm_part3
