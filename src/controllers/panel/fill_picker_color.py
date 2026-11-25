"""fill picker color."""
from controllers.panel.rects import hit_rect, rects_from_state  # noqa: E402
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
from models.pattern import cycle_pattern_type, get_fill_pattern, new_pattern
from models.strokes import _effective_component_style


def fill_picker_part3_typed(ui, state, document, event, comp_target,
                              primary_obj, sel_list, set_comp_stroke_color,
                              get_fill_gradient, hsv_to_rgb, rgb_to_hsv,
                              clamp, stroke_swatches, globals_map):
    rects = rects_from_state(state)
    if primary_obj is not None and ui.color_target == "fill" and comp_target is None and any(r.collidepoint(event.pos) for r in (state.get("fill_stop_rects") or {}).values()):
        # reverse so if any overlap occurs, topmost/latest wins
        items = list((state.get("fill_stop_rects") or {}).items())
        skey = next((k for k, r in reversed(items) if r.collidepoint(event.pos)), None)
        if skey is not None:
            try:
                state["fill_gradient_stop"] = int(skey)
            except Exception:
                state["fill_gradient_stop"] = 0
            fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else None
            if fg is not None:
                si_clamped = clamp_gradient_stop_index(fg, int(state.get("fill_gradient_stop", 0) or 0)) if 'clamp_gradient_stop_index' in globals_map else int(state.get("fill_gradient_stop", 0) or 0)
                state["fill_gradient_stop"] = si_clamped
                fc = get_gradient_stop_color(fg, si_clamped) if 'get_gradient_stop_color' in globals_map else (1.0, 1.0, 1.0, 1.0)
                ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*fc)
                state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
    elif primary_obj is not None and state["sv_rect"].collidepoint(event.pos):
        ui.picker_drag_sv = True
        sv = state["sv_rect"]
        ui.picker_s = clamp((event.pos[0] - sv.x) / max(1, sv.w - 1), 0.0, 1.0)
        ui.picker_v = clamp(1.0 - (event.pos[1] - sv.y) / max(1, sv.h - 1), 0.0, 1.0)
        col = hsv_to_rgb(ui.picker_h, ui.picker_s, ui.picker_v)
        if comp_target is not None:
            si, ci = comp_target
            if 0 <= si < len(document.strokes):
                cur_sc, _ = _effective_component_style(document.strokes[si], ci)
                alpha = color_alpha(cur_sc, 1.0)
                set_comp_stroke_color(si, ci, col, alpha)
        else:
            for si in sel_list:
                if 0 <= si < len(document.strokes):
                    if ui.color_target == "stroke":
                        alpha = color_alpha(document.strokes[si].get("stroke_color"), 1.0)
                        document.strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                    else:
                        fg = get_fill_gradient(document.strokes[si]) if 'get_fill_gradient' in globals_map else None
                        if fg is not None:
                            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                            alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals_map else (0,0,0,1), 1.0)
                            document.strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals_map else fg
                        else:
                            alpha = color_alpha(document.strokes[si].get("fill_color"), 1.0)
                            document.strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                            document.strokes[si]["fill_gradient"] = None
        state["picker_drag_sv"] = True
        state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
    elif primary_obj is not None and state["hue_rect"].collidepoint(event.pos):
        ui.picker_drag_hue = True
        hr = state["hue_rect"]
        ui.picker_h = clamp((event.pos[0] - hr.x) / max(1, hr.w - 1), 0.0, 1.0) * 360.0
        col = hsv_to_rgb(ui.picker_h, ui.picker_s, ui.picker_v)
        if comp_target is not None:
            si, ci = comp_target
            if 0 <= si < len(document.strokes):
                cur_sc, _ = _effective_component_style(document.strokes[si], ci)
                alpha = color_alpha(cur_sc, 1.0)
                set_comp_stroke_color(si, ci, col, alpha)
        else:
            for si in sel_list:
                if 0 <= si < len(document.strokes):
                    if ui.color_target == "stroke":
                        alpha = color_alpha(document.strokes[si].get("stroke_color"), 1.0)
                        document.strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                    else:
                        fg = get_fill_gradient(document.strokes[si]) if 'get_fill_gradient' in globals_map else None
                        if fg is not None:
                            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                            alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals_map else (0,0,0,1), 1.0)
                            document.strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals_map else fg
                        else:
                            alpha = color_alpha(document.strokes[si].get("fill_color"), 1.0)
                            document.strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                            document.strokes[si]["fill_gradient"] = None
        state["picker_drag_hue"] = True
        state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
    elif primary_obj is not None and rects.get("alpha_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        ar = state["alpha_rect"]
        new_alpha = clamp((event.pos[0] - ar.x) / max(1, ar.w - 1), 0.0, 1.0)
        if comp_target is not None:
            si, ci = comp_target
            if 0 <= si < len(document.strokes):
                cur_sc, _ = _effective_component_style(document.strokes[si], ci)
                base = color_rgb(cur_sc, (0.1,0.1,0.15))
                set_comp_stroke_color(si, ci, base, new_alpha)
        else:
            for si in sel_list:
                if 0 <= si < len(document.strokes):
                    if ui.color_target == "stroke":
                        document.strokes[si]["stroke_color"] = set_color_alpha(document.strokes[si].get("stroke_color", (0.1,0.1,0.15,1.0)), new_alpha)
                    else:
                        fg = get_fill_gradient(document.strokes[si]) if 'get_fill_gradient' in globals_map else None
                        if fg is not None:
                            stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                            cstop = get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals_map else (0,0,0,1)
                            document.strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (cstop[0], cstop[1], cstop[2], new_alpha)) if 'set_gradient_stop_color' in globals_map else fg
                        elif document.strokes[si].get("fill_color") is not None:
                            document.strokes[si]["fill_color"] = set_color_alpha(document.strokes[si].get("fill_color"), new_alpha)
        ui.picker_drag_alpha = True
        state["picker_drag_alpha"] = True
    elif primary_obj is not None:
        # preset swatches
        rects = state["stroke_swatch_rects"] if ui.color_target == "stroke" else state["fill_swatch_rects"]
        for i, r in enumerate(rects):
            if r.w > 0 and r.collidepoint(event.pos) and i < len(stroke_swatches):
                col = stroke_swatches[i]
                if comp_target is not None:
                    si, ci = comp_target
                    if 0 <= si < len(document.strokes):
                        cur_sc, _ = _effective_component_style(document.strokes[si], ci)
                        alpha = color_alpha(cur_sc, 1.0)
                        set_comp_stroke_color(si, ci, col, alpha)
                else:
                    for si in sel_list:
                        if 0 <= si < len(document.strokes):
                            if ui.color_target == "stroke":
                                alpha = color_alpha(document.strokes[si].get("stroke_color"), 1.0)
                                document.strokes[si]["stroke_color"] = (col[0], col[1], col[2], alpha)
                            else:
                                fg = get_fill_gradient(document.strokes[si]) if 'get_fill_gradient' in globals_map else None
                                if fg is not None:
                                    stop_i = int(state.get("fill_gradient_stop", 0) or 0)
                                    alpha = color_alpha(get_gradient_stop_color(fg, stop_i) if 'get_gradient_stop_color' in globals_map else (0,0,0,1), 1.0)
                                    document.strokes[si]["fill_gradient"] = set_gradient_stop_color(fg, stop_i, (col[0], col[1], col[2], alpha)) if 'set_gradient_stop_color' in globals_map else fg
                                else:
                                    alpha = color_alpha(document.strokes[si].get("fill_color"), 1.0)
                                    document.strokes[si]["fill_color"] = (col[0], col[1], col[2], alpha)
                                    document.strokes[si]["fill_gradient"] = None
                ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*col)
                state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
                break
        return True
    return False


def handle_bc_part3(ctx, event):
    """Compat wrapper for the typed part-3 fill-picker handler."""
    s = getattr(ctx, '_app_state', None)
    if s is None:
        return None
    return fill_picker_part3_typed(
        s.ui, ctx.state, s.document, event,
        getattr(ctx, '_c_comp_style_target', None),
        getattr(ctx, '_c_primary_obj', None),
        getattr(ctx, '_c_sel_list', []),
        getattr(ctx, '_c_set_comp_stroke_color', None),
        getattr(ctx, 'get_fill_gradient', None),
        getattr(ctx, 'hsv_to_rgb', None),
        getattr(ctx, 'rgb_to_hsv', None),
        getattr(ctx, 'clamp', None),
        getattr(ctx, 'STROKE_SWATCHES', []),
        globals(),
    )
