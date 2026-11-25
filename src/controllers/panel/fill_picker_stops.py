"""fill picker stops."""
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


def fill_picker_part2_typed(ui, state, document, event, comp_target,
                              primary_obj, sel_list, get_fill_gradient,
                              rgb_to_hsv, clamp, globals_map):
    rects = rects_from_state(state)
    if primary_obj is not None and ui.color_target == "fill" and comp_target is None and rects.get("pattern_type_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        for si in sel_list:
            if 0 <= si < len(document.strokes):
                pat = get_fill_pattern(document.strokes[si]) if 'get_fill_pattern' in globals_map else None
                if pat is not None and 'cycle_pattern_type' in globals_map:
                    document.strokes[si]["fill_pattern"] = cycle_pattern_type(pat)
                elif pat is None and 'new_pattern' in globals_map:
                    document.strokes[si]["fill_pattern"] = new_pattern("stripes")
    elif primary_obj is not None and ui.color_target == "fill" and comp_target is None and rects.get("pattern_size_minus_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        for si in sel_list:
            if 0 <= si < len(document.strokes):
                pat = get_fill_pattern(document.strokes[si]) if 'get_fill_pattern' in globals_map else None
                if pat is not None:
                    pat = dict(pat)
                    pat["size"] = max(2.0, float(pat.get("size", 14.0)) - 2.0)
                    document.strokes[si]["fill_pattern"] = pat
    elif primary_obj is not None and ui.color_target == "fill" and comp_target is None and rects.get("pattern_size_plus_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        for si in sel_list:
            if 0 <= si < len(document.strokes):
                pat = get_fill_pattern(document.strokes[si]) if 'get_fill_pattern' in globals_map else None
                if pat is not None:
                    pat = dict(pat)
                    pat["size"] = min(120.0, float(pat.get("size", 14.0)) + 2.0)
                    document.strokes[si]["fill_pattern"] = pat
    elif primary_obj is not None and ui.color_target == "fill" and comp_target is None and rects.get("fill_stop_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
        for si in sel_list:
            if 0 <= si < len(document.strokes):
                fg = get_fill_gradient(document.strokes[si]) if 'get_fill_gradient' in globals_map else None
                if fg is not None and 'add_gradient_stop' in globals_map:
                    si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else cur_stop_i
                    ng, ni = add_gradient_stop(fg, si_clamped)
                    document.strokes[si]["fill_gradient"] = ng
                    document.strokes[si]["fill_color"] = None
        pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
        if pfg is not None:
            si_clamped = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else cur_stop_i
            ni = min(si_clamped + 1, max(0, len(pfg.get("stops") or []) - 1))
            state["fill_gradient_stop"] = ni
            fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in globals_map else (1.0, 1.0, 1.0, 1.0)
            ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*fc)
            state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
    elif primary_obj is not None and ui.color_target == "fill" and comp_target is None and rects.get("fill_stop_remove_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
        for si in sel_list:
            if 0 <= si < len(document.strokes):
                fg = get_fill_gradient(document.strokes[si]) if 'get_fill_gradient' in globals_map else None
                if fg is not None and 'remove_gradient_stop' in globals_map:
                    si_clamped = clamp_gradient_stop_index(fg, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else cur_stop_i
                    ng, ni = remove_gradient_stop(fg, si_clamped)
                    document.strokes[si]["fill_gradient"] = ng
                    document.strokes[si]["fill_color"] = None
        pfg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
        if pfg is not None:
            ni = clamp_gradient_stop_index(pfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else max(0, min(cur_stop_i, max(0, len(pfg.get("stops") or []) - 1)))
            state["fill_gradient_stop"] = ni
            fc = get_gradient_stop_color(pfg, ni) if 'get_gradient_stop_color' in globals_map else (1.0, 1.0, 1.0, 1.0)
            ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*fc)
            state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
    elif primary_obj is not None and ui.color_target == "fill" and comp_target is None and rects.get("fill_stop_pos_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        fg = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else (primary_obj.get("fill_gradient") if isinstance(primary_obj.get("fill_gradient"), dict) else None)
        if fg is not None:
            cur_stop_i = int(state.get("fill_gradient_stop", 0) or 0)
            pr = rects.get("fill_stop_pos_rect", pygame.Rect(0,0,0,0))
            # If a stop marker on the ramp is clicked, select that stop.
            stops_for_pick = get_gradient_stops(fg) if 'get_gradient_stops' in globals_map else list(fg.get("stops") or [])
            if stops_for_pick:
                best_i = None
                best_d = 1e9
                for si_pick, st_pick in enumerate(stops_for_pick):
                    try:
                        sp = float((st_pick or {}).get("pos", 0.0)) if isinstance(st_pick, dict) else float(st_pick[0])
                    except Exception:
                        sp = 0.0
                    sp = clamp(sp, 0.0, 1.0)
                    sxp = pr.x + sp * max(1, pr.w - 1)
                    d = abs(event.pos[0] - sxp)
                    if d <= 7 and d < best_d:
                        best_d = d
                        best_i = si_pick
                if best_i is not None:
                    cur_stop_i = int(best_i)
                    state["fill_gradient_stop"] = cur_stop_i
            rel = (event.pos[0] - pr.x) / max(1, pr.w - 1)
            rel = clamp(rel, 0.0, 1.0)
            if 'set_gradient_stop_pos' in globals_map:
                for si in sel_list:
                    if 0 <= si < len(document.strokes):
                        sfg = get_fill_gradient(document.strokes[si]) if 'get_fill_gradient' in globals_map else None
                        if sfg is not None:
                            sidx = clamp_gradient_stop_index(sfg, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else cur_stop_i
                            ng, _ni = set_gradient_stop_pos(sfg, sidx, rel)
                            document.strokes[si]["fill_gradient"] = ng
                            document.strokes[si]["fill_color"] = None
                pfg2 = get_fill_gradient(primary_obj) if 'get_fill_gradient' in globals_map else None
                if pfg2 is not None:
                    sidx = clamp_gradient_stop_index(pfg2, cur_stop_i) if 'clamp_gradient_stop_index' in globals_map else cur_stop_i
                    _ngp, ni = set_gradient_stop_pos(pfg2, sidx, rel)
                    state["fill_gradient_stop"] = ni
                    fc = get_gradient_stop_color(_ngp, ni) if 'get_gradient_stop_color' in globals_map else (1.0, 1.0, 1.0, 1.0)
                    ui.picker_h, ui.picker_s, ui.picker_v = rgb_to_hsv(*fc)
                    state["picker_h"] = ui.picker_h; state["picker_s"] = ui.picker_s; state["picker_v"] = ui.picker_v
            ui.fill_stop_pos_drag = True
            state["fill_stop_pos_drag"] = True
        return True
    return False


def handle_bc_part2(ctx, event):
    """Compat wrapper for the typed part-2 fill-picker handler."""
    s = getattr(ctx, '_app_state', None)
    if s is None:
        return None
    return fill_picker_part2_typed(
        s.ui, ctx.state, s.document, event,
        getattr(ctx, '_c_comp_style_target', None),
        getattr(ctx, '_c_primary_obj', None),
        getattr(ctx, '_c_sel_list', []),
        getattr(ctx, 'get_fill_gradient', None),
        getattr(ctx, 'rgb_to_hsv', None),
        getattr(ctx, 'clamp', None),
        globals(),
    )
