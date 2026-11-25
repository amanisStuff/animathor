"""gradient tabs."""
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



def gradient_tabs_filltype_typed(ui, state, document, event, comp_target, primary_obj,
                      sel_list, get_fill_gradient, rgb_to_hsv,
                      set_comp_stroke_color, stroke_swatches,
                      clamp, hsv_to_rgb, globals_map):
    if state["tab_stroke_rect"].collidepoint(event.pos):
        ui.color_target = "stroke"
        state["color_target"] = ui.color_target
        if comp_target is not None:
            sc, _sw = _effective_component_style(primary_obj, comp_target[1])
            sc = sc or (0.1, 0.1, 0.15)
        else:
            sc = primary_obj.get("stroke_color", (0.1, 0.1, 0.15)) or (0.1, 0.1, 0.15)
        ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*sc)
        state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
    elif state["tab_fill_rect"].collidepoint(event.pos) and comp_target is None:
        ui.color_target = "fill"
        state["color_target"] = ui.color_target
        fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) and primary_obj.get("fill_gradient", {}).get("type") in ("linear","radial") else None)
        if fg is not None:
            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
            fc = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals_map else (1.0, 1.0, 1.0, 1.0)
        else:
            fc = primary_obj.get("fill_color", None) or (1.0, 1.0, 1.0)
        ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*fc)
        state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
    elif state.get("nofill_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) and ui.color_target == "fill" and comp_target is None:
        for si in sel_list:
            if 0 <= si < len(document.strokes):
                document.strokes[si]["fill_color"] = None
                document.strokes[si]["fill_gradient"] = None
    elif ui.color_target == "fill" and comp_target is None and any(
        state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for k in ("fill_type_prev_rect", "fill_type_next_rect")
    ):
        _fdir = -1 if state.get("fill_type_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else 1
        _fmodes = ["solid", "linear", "radial", "conic", "spiral", "diamond", "square", "mesh", "pattern"]
        _pfg_cur = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
        _ppat_cur = get_fill_pattern(primary_obj) if 'get_fill_pattern' in globals_map else primary_obj.get("fill_pattern")
        if _ppat_cur is not None:
            _cur_fill_mode = "pattern"
        elif _pfg_cur is not None:
            _cur_fill_mode = str(_pfg_cur.get("type", "linear"))
        elif primary_obj.get("fill_color") is not None:
            _cur_fill_mode = "solid"
        else:
            _cur_fill_mode = "solid"
        if _cur_fill_mode not in _fmodes:
            _cur_fill_mode = "solid"
        ftype = _fmodes[(_fmodes.index(_cur_fill_mode) + _fdir) % len(_fmodes)]
        if ftype is not None:
            cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
            grad_types = ("linear", "radial", "conic", "spiral", "diamond", "square", "mesh")
            for si in sel_list:
                if 0 <= si < len(document.strokes):
                    st = document.strokes[si]
                    fg = get_fill_gradient(st) if 'get_fill_gradient' in globals_map else (st.get("fill_gradient") if isinstance(st.get("fill_gradient"), dict) else None)
                    if ftype == "solid":
                        if fg is not None:
                            si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else max(0, min(cur_stop_i, max(0, len(fg.get("stops") or []) - 1)))
                            col0 = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in globals_map else (0.0, 0.0, 0.0, 1.0)
                        else:
                            col0 = st.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                        st["fill_color"] = tuple(color_rgba(col0, (0.45, 0.72, 1.0, 1.0)))
                        st["fill_gradient"] = None
                    elif ftype in grad_types:
                        if fg is not None and str(fg.get("type")) in grad_types:
                            if ftype == "mesh" or str(fg.get("type")) == "mesh":
                                base = st.get("fill_color")
                                if base is None and isinstance(fg.get("stops"), list) and fg.get("stops"):
                                    try:
                                        base = get_gradient_stop_color(fg, 0) if 'get_gradient_stop_color' in globals_map else (fg.get("stops")[0] or {}).get("color")
                                    except Exception:
                                        base = None
                                base = color_rgba(base or (0.2, 0.4, 0.9, 1.0), (0.2, 0.4, 0.9, 1.0))
                                c1m = (1.0, 1.0, 1.0, float(base[3]))
                                if ftype == "mesh" and 'default_mesh_gradient' in globals_map:
                                    st["fill_gradient"] = default_mesh_gradient(base, c1m)
                                elif ftype == "linear" and 'default_linear_gradient' in globals_map:
                                    st["fill_gradient"] = default_linear_gradient(base, c1m, 0.0)
                                elif ftype == "radial" and 'default_radial_gradient' in globals_map:
                                    st["fill_gradient"] = default_radial_gradient((1.0, 1.0, 1.0, float(base[3])), base)
                                elif 'default_shaped_gradient' in globals_map:
                                    st["fill_gradient"] = default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(base[3])), base)
                                else:
                                    st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(base)}, {"pos": 1.0, "color": list(c1m)}]}
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
                                if 'normalize_gradient' in globals_map:
                                    try:
                                        ng = normalize_gradient(ng)
                                    except Exception:
                                        pass
                                st["fill_gradient"] = ng
                        else:
                            base = st.get("fill_color") or (0.2, 0.4, 0.9, 1.0)
                            c0 = color_rgba(base, (0.2, 0.4, 0.9, 1.0))
                            c1 = (1.0, 1.0, 1.0, float(c0[3]))
                            if ftype == "mesh" and 'default_mesh_gradient' in globals_map:
                                st["fill_gradient"] = default_mesh_gradient(c0, c1)
                            elif ftype == "linear" and 'default_linear_gradient' in globals_map:
                                st["fill_gradient"] = default_linear_gradient(c0, c1, 0.0)
                            elif ftype == "radial" and 'default_radial_gradient' in globals_map:
                                st["fill_gradient"] = default_radial_gradient((1.0, 1.0, 1.0, float(c0[3])), c0)
                            elif 'default_shaped_gradient' in globals_map:
                                st["fill_gradient"] = default_shaped_gradient(ftype, (1.0, 1.0, 1.0, float(c0[3])), c0)
                            else:
                                st["fill_gradient"] = {"type": ftype, "center": [0.5, 0.5], "radii": [0.5, 0.5], "angle": 0.0, "stops": [{"pos": 0.0, "color": list(c0)}, {"pos": 1.0, "color": list(c1)}]}
                        st["fill_color"] = None
                    elif ftype == "pattern":
                        pat = get_fill_pattern(st) if 'get_fill_pattern' in globals_map else None
                        if pat is None and 'new_pattern' in globals_map:
                            pat = new_pattern("stripes")
                        st["fill_pattern"] = pat
                        st["fill_color"] = None
                        st["fill_gradient"] = None
            pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
            if pfg is not None:
                state["fill_gradient_stop"] = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
                fc = get_gradient_stop_color(pfg, int(state.get("fill_gradient_stop", 0) or 0)) if 'get_gradient_stop_color' in globals_map else (1.0, 1.0, 1.0, 1.0)
                ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*fc)
                state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
            elif ftype == "solid":
                fc = primary_obj.get("fill_color") or (0.45, 0.72, 1.0, 1.0)
                ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*fc)
                state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
                state["fill_gradient_stop"] = 0
        return True
    return False


def handle_c_tabs_filltype(ctx, event):
    s = getattr(ctx, '_app_state', None)
    if s is None:
        from controllers.app_state import AppState
        s = AppState()
        s.tools.tool_mode = getattr(ctx, 'tool_mode', 'draw')
        s.selection.selection_submode = getattr(ctx, 'selection_submode', 'transform')
        s.selection.selected_strokes = getattr(ctx, 'selected_strokes', set())
        s.selection.selected_curve = getattr(ctx, 'selected_curve', None)
        s.document.strokes = getattr(ctx, 'strokes', [])
        s.ui.color_target = getattr(ctx, 'color_target', 'stroke')
        s.ui.picker_h = getattr(ctx, 'picker_h', None)
        s.ui.picker_s = getattr(ctx, 'picker_s', None)
        s.ui.picker_v = getattr(ctx, 'picker_v', None)
    return gradient_tabs_filltype_typed(
        s.ui, ctx.state, s.document, event,
        getattr(ctx, '_c_comp_style_target', None),
        getattr(ctx, '_c_primary_obj', None),
        getattr(ctx, '_c_sel_list', []),
        getattr(ctx, 'get_fill_gradient', None),
        getattr(ctx, 'rgb_to_hsv', None),
        getattr(ctx, '_c_set_comp_stroke_color', None),
        getattr(ctx, 'STROKE_SWATCHES', []),
        getattr(ctx, 'clamp', None),
        getattr(ctx, 'hsv_to_rgb', None),
        globals(),
    )
