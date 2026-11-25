"""Gradient-handle drag motion."""
import copy, math, pygame
import config as cfg


def gradient_drag_move(ctx, event):
    if ctx.tool_mode == "selection" and ctx.gradient_drag is not None and ctx.selected_strokes and pygame.mouse.get_pressed()[0]:
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

