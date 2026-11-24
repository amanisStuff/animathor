"""Color/fill panel actions - tabs/stops/picker domain (semantic)."""
import pygame

from models.geometry import (
    add_gradient_stop,
    clamp_gradient_stop_index,
    color_alpha,
    color_rgb,
    color_rgba,
    default_mesh_gradient,
    get_gradient_stop_color,
    get_gradient_stops,
    remove_gradient_stop,
    set_color_alpha,
    set_gradient_stop_color,
    set_gradient_stop_pos,
)
from models.pattern import get_fill_pattern, new_pattern
from models.strokes import _effective_component_style


def handle_c_tabs_filltype(ctx, event):
    if ctx.state["tab_stroke_rect"].collidepoint(event.pos):
        ctx.color_target = "stroke"
        ctx.state["color_target"] = ctx.color_target
        if ctx._c_comp_style_target is not None:
            sc, _sw = _effective_component_style(ctx._c_primary_obj, ctx._c_comp_style_target[1])
            sc = sc or (0.1, 0.1, 0.15)
        else:
            sc = ctx._c_primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
        ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*sc)
        ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
    elif ctx.state["tab_fill_rect"].collidepoint(event.pos) and ctx._c_comp_style_target is None:
        ctx.color_target = "fill"
        ctx.state["color_target"] = ctx.color_target
        fg = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else (ctx._c_primary_obj.get("fill_gradient") if isinstance(ctx._c_primary_obj.get("fill_gradient"), dict) and ctx._c_primary_obj.get("fill_gradient", {}).get("type") in ("linear","radial") else None)
        if fg is not None:
            stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
            fc = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
        else:
            fc = ctx._c_primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
        ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
        ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
    elif ctx.state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and ctx.color_target == "fill" and ctx._c_comp_style_target is None:
        for ctx.si in ctx._c_sel_list:
            if 0 <= ctx.si < len(ctx.strokes):
                ctx.strokes[ctx.si]["fill_color"] = None
                ctx.strokes[ctx.si]["fill_gradient"] = None
    elif ctx.color_target == "fill" and ctx._c_comp_style_target is None and any(
        ctx.state.get(ctx.k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for ctx.k in ("fill_type_prev_rect", "fill_type_next_rect")
    ):
        _fdir = -1 if ctx.state.get("fill_type_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
        _fmodes = ["solid", "linear", "radial", "conic", "spiral", "diamond", "square", "mesh", "pattern"]
        _pfg_cur = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else (ctx._c_primary_obj.get("fill_gradient") if isinstance(ctx._c_primary_obj.get("fill_gradient"), dict) else None)
        _ppat_cur = get_fill_pattern(ctx._c_primary_obj) if 'get_fill_pattern' in ctx.globals() else ctx._c_primary_obj.get("fill_pattern")
        if _ppat_cur is not None:
            _cur_fill_mode = "pattern"
        elif _pfg_cur is not None:
            _cur_fill_mode = str(_pfg_cur.get("type", "linear"))
        elif ctx._c_primary_obj.get("fill_color") is not None:
            _cur_fill_mode = "solid"
        else:
            _cur_fill_mode = "solid"
        if _cur_fill_mode not in _fmodes:
            _cur_fill_mode = "solid"
        ftype = _fmodes[(_fmodes.index(_cur_fill_mode) + _fdir) % len(_fmodes)]
        if ftype is not None:
            cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
            grad_types = ("linear", "radial", "conic", "spiral", "diamond", "square", "mesh")
            for ctx.si in ctx._c_sel_list:
                if 0 <= ctx.si < len(ctx.strokes):
                    ctx.st = ctx.strokes[ctx.si]
                    fg = ctx.get_fill_gradient(ctx.st) if 'get_fill_gradient' in ctx.globals() else (ctx.st.get("fill_gradient") if isinstance(ctx.st.get("fill_gradient"), dict) else None)
                    if ftype == "solid":
                        if fg is not None:
                            si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else max(0, min(cur_stop_i, max(0, len(fg.get("stops") or []) - 1)))
                            col0 = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in ctx.globals() else (0.0, 0.0, 0.0, 1.0)
                        else:
                            col0 = ctx.st.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                        ctx.st["fill_color"] = tuple(color_rgba(col0, (0.45, 0.72, 1.0, 1.0)))
                        ctx.st["fill_gradient"] = None
                    elif ftype in grad_types:
                        if fg is not None and str(fg.get("type")) in grad_types:
                            if ftype == "mesh" or str(fg.get("type")) == "mesh":
                                ctx.base = ctx.st.get("fill_color")
                                if ctx.base is None and isinstance(fg.get("stops"), list) and fg.get("stops"):
                                    try:
                                        ctx.base = get_gradient_stop_color(fg, 0) if 'get_gradient_stop_color' in ctx.globals() else (fg.get("stops")[0] or {}).get("color")
                                    except Exception:
                                        ctx.base = None
                                ctx.base = color_rgba(ctx.base or (0.2, 0.4, 0.9, 1.0), (0.2, 0.4, 0.9, 1.0))
                                c1m = (1.0, 1.0, 1.0, float(ctx.base[3]))
                                if ftype == "mesh" and 'default_mesh_gradient' in ctx.globals():
                                    ctx.st["fill_gradient"] = default_mesh_gradient(ctx.base, c1m)
                                elif ftype == "linear" and 'default_linear_gradient' in ctx.globals():
                                    ctx.st["fill_gradient"] = ctx.default_linear_gradient(ctx.base, c1m, 0.0)
                                elif ftype == "radial" and 'default_radial_gradient' in ctx.globals():
                                    ctx.st["fill_gradient"] = ctx.default_radial_gradient((1.0, 1.0, 1.0, float(ctx.base[3])), ctx.base)
                                elif 'default_shaped_gradient' in ctx.globals():
                                    ctx.st["fill_gradient"] = ctx.default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(ctx.base[3])), ctx.base)
                                else:
                                    ctx.st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(ctx.base)}, {"pos": 1.0, "color": list(c1m)}]}
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
                                if 'normalize_gradient' in ctx.globals():
                                    try:
                                        ng = ctx.normalize_gradient(ng)
                                    except Exception:
                                        pass
                                ctx.st["fill_gradient"] = ng
                        else:
                            ctx.base = ctx.st.get("fill_color") or (0.2, 0.4, 0.9, 1.0)
                            c0 = color_rgba(ctx.base, (0.2, 0.4, 0.9, 1.0))
                            ctx.c1 = (1.0, 1.0, 1.0, float(c0[3]))
                            if ftype == "mesh" and 'default_mesh_gradient' in ctx.globals():
                                ctx.st["fill_gradient"] = default_mesh_gradient(c0, ctx.c1)
                            elif ftype == "linear" and 'default_linear_gradient' in ctx.globals():
                                ctx.st["fill_gradient"] = ctx.default_linear_gradient(c0, ctx.c1, 0.0)
                            elif ftype == "radial" and 'default_radial_gradient' in ctx.globals():
                                ctx.st["fill_gradient"] = ctx.default_radial_gradient((1.0, 1.0, 1.0, float(c0[3])), c0)
                            elif 'default_shaped_gradient' in ctx.globals():
                                ctx.st["fill_gradient"] = ctx.default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(c0[3])), c0)
                            else:
                                ctx.st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(c0)}, {"pos": 1.0, "color": list(ctx.c1)}]}
                        ctx.st["fill_color"] = None
                    elif ftype == "pattern":
                        pat = get_fill_pattern(ctx.st) if 'get_fill_pattern' in ctx.globals() else None
                        if pat is None and 'new_pattern' in ctx.globals():
                            pat = new_pattern("stripes")
                        ctx.st["fill_pattern"] = pat
                        ctx.st["fill_color"] = None
                        ctx.st["fill_gradient"] = None
            pfg = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else (ctx._c_primary_obj.get("fill_gradient") if isinstance(ctx._c_primary_obj.get("fill_gradient"), dict) else None)
            if pfg is not None:
                ctx.state["fill_gradient_stop"] = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                fc = get_gradient_stop_color(pfg, int(ctx.state.get("fill_gradient_stop", 0) or 0)) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
            elif ftype == "solid":
                fc = ctx._c_primary_obj.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                ctx.state["fill_gradient_stop"] = 0
        return True
    return False


def handle_c_stops(ctx, event):
    if ctx.color_target == "fill" and ctx._c_comp_style_target is None and ctx.state.get("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
        cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
        for ctx.si in ctx._c_sel_list:
            if 0 <= ctx.si < len(ctx.strokes):
                fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                if fg is not None and 'add_gradient_stop' in ctx.globals():
                    si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                    ng, ni = add_gradient_stop(fg, si_clamped)
                    ctx.strokes[ctx.si]["fill_gradient"] = ng
                    ctx.strokes[ctx.si]["fill_color"] = None
        pfg = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else (ctx._c_primary_obj.get("fill_gradient") if isinstance(ctx._c_primary_obj.get("fill_gradient"), dict) else None)
        if pfg is not None:
            ni = min((clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i) + 1, max(0, len(pfg.get("stops") or []) - 1))
            ctx.state["fill_gradient_stop"] = ni
            fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
            ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
            ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
    elif ctx.color_target == "fill" and ctx._c_comp_style_target is None and ctx.state.get("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
        cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
        for ctx.si in ctx._c_sel_list:
            if 0 <= ctx.si < len(ctx.strokes):
                fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                if fg is not None and 'remove_gradient_stop' in ctx.globals():
                    si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                    ng, ni = remove_gradient_stop(fg, si_clamped)
                    ctx.strokes[ctx.si]["fill_gradient"] = ng
                    ctx.strokes[ctx.si]["fill_color"] = None
        pfg = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else (ctx._c_primary_obj.get("fill_gradient") if isinstance(ctx._c_primary_obj.get("fill_gradient"), dict) else None)
        if pfg is not None:
            ni = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
            ctx.state["fill_gradient_stop"] = ni
            fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
            ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
            ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
    elif ctx.color_target == "fill" and ctx._c_comp_style_target is None and ctx.state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
        fg = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else (ctx._c_primary_obj.get("fill_gradient") if isinstance(ctx._c_primary_obj.get("fill_gradient"), dict) else None)
        if fg is not None:
            cur_stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
            pr = ctx.state.get("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
            # If a stop marker on the ramp is clicked, select that stop.
            stops_for_pick = get_gradient_stops(fg) if 'get_gradient_stops' in ctx.globals() else list(fg.get("stops") or [])
            if stops_for_pick:
                best_i = None
                ctx.best_d = 1e9
                for si_pick, st_pick in enumerate(stops_for_pick):
                    try:
                        ctx.sp = float((st_pick or {}).get("pos", 0.0)) if isinstance(st_pick, dict) else float(st_pick[0])
                    except Exception:
                        ctx.sp = 0.0
                    ctx.sp = ctx.clamp(ctx.sp, 0.0, 1.0)
                    sxp = pr.x + ctx.sp * max(1, pr.w - 1)
                    ctx.d = abs(event.pos[0] - sxp)
                    if ctx.d <= 7 and ctx.d < ctx.best_d:
                        ctx.best_d = ctx.d
                        best_i = si_pick
                if best_i is not None:
                    cur_stop_i = int(best_i)
                    ctx.state["fill_gradient_stop"] = cur_stop_i
            rel = (event.pos[0] - pr.x) / max(1, pr.w - 1)
            rel = ctx.clamp(rel, 0.0, 1.0)
            if 'set_gradient_stop_pos' in ctx.globals():
                for ctx.si in ctx._c_sel_list:
                    if 0 <= ctx.si < len(ctx.strokes):
                        sfg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                        if sfg is not None:
                            sidx = clamp_gradient_stop_index(sfg, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                            ng, _ni = set_gradient_stop_pos(sfg, sidx, rel)
                            ctx.strokes[ctx.si]["fill_gradient"] = ng
                            ctx.strokes[ctx.si]["fill_color"] = None
                pfg2 = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else None
                if pfg2 is not None:
                    sidx = clamp_gradient_stop_index(pfg2, cur_stop_i) if 'clamp_gradient_stop_index' in ctx.globals() else cur_stop_i
                    _ngp, ni = set_gradient_stop_pos(pfg2, sidx, rel)
                    ctx.state["fill_gradient_stop"] = ni
                    fc = get_gradient_stop_color(_ngp, ni) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                    ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                    ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
            ctx.fill_stop_pos_drag = True
            ctx.state["fill_stop_pos_drag"] = True
        return True
    return False


def handle_c_picker(ctx, event):
    if ctx.color_target == "fill" and ctx._c_comp_style_target is None and any(ctx.r.collidepoint(event.pos) for ctx.r in (ctx.state.get("fill_stop_rects") or {}).values()):
        ctx.items = list((ctx.state.get("fill_stop_rects") or {}).items())
        skey = ctx.next((ctx.k for ctx.k, ctx.r in reversed(ctx.items) if ctx.r.collidepoint(event.pos)), None)
        if skey is not None:
            try:
                ctx.state["fill_gradient_stop"] = int(skey)
            except Exception:
                ctx.state["fill_gradient_stop"] = 0
            fg = ctx.get_fill_gradient(ctx._c_primary_obj) if 'get_fill_gradient' in ctx.globals() else None
            if fg is not None:
                si_clamped = clamp_gradient_stop_index(fg, int(ctx.state.get("fill_gradient_stop", 0) or 0)) if 'clamp_gradient_stop_index' in ctx.globals() else int(ctx.state.get("fill_gradient_stop", 0) or 0)
                ctx.state["fill_gradient_stop"] = si_clamped
                fc = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in ctx.globals() else (1.0, 1.0, 1.0, 1.0)
                ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*fc)
                ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
    elif ctx.state["sv_rect"].collidepoint(event.pos):
        ctx.picker_drag_sv = True
        ctx.sv = ctx.state["sv_rect"]
        ctx.picker_s = ctx.clamp((event.pos[0] - ctx.sv.x) / max(1, ctx.sv.w - 1), 0.0, 1.0)
        ctx.picker_v = ctx.clamp(1.0 - (event.pos[1] - ctx.sv.y) / max(1, ctx.sv.h - 1), 0.0, 1.0)
        ctx.col = ctx.hsv_to_rgb(ctx.picker_h, ctx.picker_s, ctx.picker_v)
        if ctx._c_comp_style_target is not None:
            ctx.si, ctx.ci = ctx._c_comp_style_target
            if 0 <= ctx.si < len(ctx.strokes):
                cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                ctx.alpha = color_alpha(cur_sc, 1.0)
                ctx._c_set_comp_stroke_color(ctx.si, ctx.ci, ctx.col, ctx.alpha)
        else:
            for ctx.si in ctx._c_sel_list:
                if 0 <= ctx.si < len(ctx.strokes):
                    if ctx.color_target == "stroke":
                        ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("stroke_color"), 1.0)
                        ctx.strokes[ctx.si]["stroke_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                    else:
                        fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                        if fg is not None:
                            stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                            ctx.alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1), 1.0)
                            ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                        else:
                            ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("fill_color"), 1.0)
                            ctx.strokes[ctx.si]["fill_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                            ctx.strokes[ctx.si]["fill_gradient"] = None
        ctx.state["picker_drag_sv"] = True
        ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
    elif ctx.state["hue_rect"].collidepoint(event.pos):
        ctx.picker_drag_hue = True
        hr = ctx.state["hue_rect"]
        ctx.picker_h = ctx.clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
        ctx.col = ctx.hsv_to_rgb(ctx.picker_h, ctx.picker_s, ctx.picker_v)
        if ctx._c_comp_style_target is not None:
            ctx.si, ctx.ci = ctx._c_comp_style_target
            if 0 <= ctx.si < len(ctx.strokes):
                cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                ctx.alpha = color_alpha(cur_sc, 1.0)
                ctx._c_set_comp_stroke_color(ctx.si, ctx.ci, ctx.col, ctx.alpha)
        else:
            for ctx.si in ctx._c_sel_list:
                if 0 <= ctx.si < len(ctx.strokes):
                    if ctx.color_target == "stroke":
                        ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("stroke_color"), 1.0)
                        ctx.strokes[ctx.si]["stroke_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                    else:
                        fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                        if fg is not None:
                            stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                            ctx.alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1), 1.0)
                            ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                        else:
                            ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("fill_color"), 1.0)
                            ctx.strokes[ctx.si]["fill_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                            ctx.strokes[ctx.si]["fill_gradient"] = None
        ctx.state["picker_drag_hue"] = True
        ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
    elif ctx.state.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        ar = ctx.state["alpha_rect"]
        new_alpha = ctx.clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
        if ctx._c_comp_style_target is not None:
            ctx.si, ctx.ci = ctx._c_comp_style_target
            if 0 <= ctx.si < len(ctx.strokes):
                cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                ctx.base = color_rgb(cur_sc, (0.1,0.1,0.15))
                ctx._c_set_comp_stroke_color(ctx.si, ctx.ci, ctx.base, new_alpha)
        else:
            for ctx.si in ctx._c_sel_list:
                if 0 <= ctx.si < len(ctx.strokes):
                    if ctx.color_target == "stroke":
                        ctx.strokes[ctx.si]["stroke_color"] = set_color_alpha(ctx.strokes[ctx.si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                    else:
                        fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                        if fg is not None:
                            stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                            cstop = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1)
                            ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (cstop[0], cstop[1], cstop[2], new_alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                        elif ctx.strokes[ctx.si].get("fill_color") is not None:
                            ctx.strokes[ctx.si]["fill_color"] = set_color_alpha(ctx.strokes[ctx.si].get("fill_color"), new_alpha)
        ctx.picker_drag_alpha = True
        ctx.state["picker_drag_alpha"] = True
    else:
        # preset swatches (draw_panel populates rects matching active target)
        ctx.rects = ctx.state["stroke_swatch_rects"] if ctx.color_target == "stroke" else ctx.state["fill_swatch_rects"]
        for ctx.i, ctx.r in enumerate(ctx.rects):
            if ctx.r.w > 0 and ctx.r.collidepoint(event.pos) and ctx.i < len(ctx.STROKE_SWATCHES):
                ctx.col = ctx.STROKE_SWATCHES[ctx.i]
                if ctx._c_comp_style_target is not None:
                    ctx.si, ctx.ci = ctx._c_comp_style_target
                    if 0 <= ctx.si < len(ctx.strokes):
                        cur_sc, _ = _effective_component_style(ctx.strokes[ctx.si], ctx.ci)
                        ctx.alpha = color_alpha(cur_sc, 1.0)
                        ctx._c_set_comp_stroke_color(ctx.si, ctx.ci, ctx.col, ctx.alpha)
                else:
                    for ctx.si in ctx._c_sel_list:
                        if 0 <= ctx.si < len(ctx.strokes):
                            if ctx.color_target == "stroke":
                                ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("stroke_color"), 1.0)
                                ctx.strokes[ctx.si]["stroke_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                            else:
                                fg = ctx.get_fill_gradient(ctx.strokes[ctx.si]) if 'get_fill_gradient' in ctx.globals() else None
                                if fg is not None:
                                    stop_i = int(ctx.state.get("fill_gradient_stop", 0) or 0)
                                    ctx.alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in ctx.globals() else (0,0,0,1), 1.0)
                                    ctx.strokes[ctx.si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)) if 'set_gradient_stop_color' in ctx.globals() else fg
                                else:
                                    ctx.alpha = color_alpha(ctx.strokes[ctx.si].get("fill_color"), 1.0)
                                    ctx.strokes[ctx.si]["fill_color"] = (ctx.col[0], ctx.col[1], ctx.col[2], ctx.alpha)
                                    ctx.strokes[ctx.si]["fill_gradient"] = None
                ctx.picker_h, ctx.picker_s, ctx.picker_v = ctx.rgb_to_hsv(*ctx.col)
                ctx.state["picker_h"] = ctx.picker_h; ctx.state["picker_s"] = ctx.picker_s; ctx.state["picker_v"] = ctx.picker_v
                break
        return True
    return False


# Semantic aliases
handle_fill_tabs_and_type = handle_c_tabs_filltype
handle_gradient_stops = handle_c_stops
handle_fill_picker = handle_c_picker
