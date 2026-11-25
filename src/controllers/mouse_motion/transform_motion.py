"""transform motion."""
import copy, math, pygame
import config as cfg
from controllers.mouse_motion.gradient_drag_motion import gradient_drag_move


def mm_part3(ctx, event):
    if ctx.tool_mode == "selection" and ctx.pending_transform_toggle is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
        cpos = ctx.clamp_to_canvas(event.pos)
        ptt = ctx.pending_transform_toggle
        if not ptt.get("moved"):
            dx0 = cpos[0] - ptt["start"][0]; dy0 = cpos[1] - ptt["start"][1]
            if math.hypot(dx0, dy0) >= 4.0:
                # threshold exceeded: start move drag instead of mode toggle
                ptt["moved"] = True
                ctx.pending_transform_toggle = None
                if ctx.drag_last is None:
                    ctx.push_undo()
                ctx.drag_last = ptt["start"]
                # apply initial delta
                dx = cpos[0] - ctx.drag_last[0]; dy = cpos[1] - ctx.drag_last[1]
                if dx != 0 or dy != 0:
                    dx, dy, ctx.smart_snap_guides = ctx._snap_move_delta(ctx.selected_strokes, dx, dy)
                else:
                    ctx.smart_snap_guides = []
                if dx != 0 or dy != 0:
                    for si in list(ctx.selected_strokes):
                        if 0 <= si < len(ctx.strokes):
                            ctx.strokes[si] = ctx.translate_stroke(ctx.strokes[si], dx, dy)
                    ctx.drag_last = (ctx.drag_last[0] + dx, ctx.drag_last[1] + dy)
                else:
                    ctx.drag_last = cpos
        # if not yet moved, wait for threshold or mouseup (toggle)
    elif gradient_drag_move(ctx, event):
        return True
    elif ctx.tool_mode == "selection" and ctx.transform_drag is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
        cpos = ctx.clamp_to_canvas(event.pos)
        td = ctx.transform_drag
        cx, cy = td["center"]  # pivot/rotation center
        sx0, sy0 = td["start_mouse"]
        h = td["handle"]
        # snap scale/skew handle drags to nearby geometry and show alignment ctx.guides
        if h != "rot" and not str(h).startswith("rot_"):
            _sr = ctx.snap_radius()
            if _sr > 0:
                _sel_set = set(ctx.selected_strokes)
                _other = [s for _i, s in enumerate(ctx.strokes) if _i not in _sel_set]
                if _other:
                    _sp = ctx.nearest_snap_point(cpos, _other, _sr)
                    if _sp is not None:
                        cpos = _sp
                    ctx.smart_snap_guides = ctx._alignment_guides_for_point(cpos, _other, _sr)
                else:
                    ctx.smart_snap_guides = []
            else:
                ctx.smart_snap_guides = []
        else:
            # rotation/skew: clear positional alignment ctx.guides
            ctx.smart_snap_guides = []
        ctx.start_strokes = td.get("ctx.start_strokes", {})
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
            for i, st0 in ctx.start_strokes.items():
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
            for i, st0 in ctx.start_strokes.items():
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
            for i, st0 in ctx.start_strokes.items():
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes[i] = ctx.scale_stroke_local(st0, (fx, fy), ang, su, sv)
    elif ctx.tool_mode == "selection" and ctx.drag_last is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
        cpos = ctx.clamp_to_canvas(event.pos)
        if ctx.selection_submode == "nodes" and ctx.selected_point is not None and len(ctx.selected_strokes) == 1:
            only = next(iter(ctx.selected_strokes))
            seg_i, pname = ctx.selected_point
            if 0 <= only < len(ctx.strokes):
                ctx.strokes[only] = ctx.set_stroke_point(ctx.strokes[only], seg_i, pname, cpos)
            ctx.drag_last = cpos
        elif ctx.selection_submode in ("transform", "nodes"):
            # In nodes mode, dragging the stroke (not a point) moves it; curve mode has no drag-move here
            if ctx.selection_submode == "nodes" and ctx.selected_point is not None:
                pass
            else:
                dx = cpos[0] - ctx.drag_last[0]; dy = cpos[1] - ctx.drag_last[1]
                if dx != 0 or dy != 0:
                    dx, dy, ctx.smart_snap_guides = ctx._snap_move_delta(ctx.selected_strokes, dx, dy)
                else:
                    ctx.smart_snap_guides = []
                if dx != 0 or dy != 0:
                    for si in list(ctx.selected_strokes):
                        if 0 <= si < len(ctx.strokes):
                            ctx.strokes[si] = ctx.translate_stroke(ctx.strokes[si], dx, dy)
                    ctx.drag_last = (ctx.drag_last[0] + dx, ctx.drag_last[1] + dy)
                else:
                    ctx.drag_last = cpos
        else:
            ctx.drag_last = cpos
    # (translation handled above when ctx.drag_last is set)


    return False
