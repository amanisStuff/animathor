"""effects wave edit."""
import copy, math, pygame
import config as cfg

from models.waves import (
    WAVE_SHAPE_LABELS,
    _get_distortion_styles,
    _remove_distortion_style,
    default_displacement_params,
    default_repeat_params,
    default_thickness_params,
    default_wave_params,
)
from models.waves_extra import (
    _custom_smooth_samples,
    _custom_wave_paint,
    _smooth_repeat_points,
    bake_component_distortion,
)


def effects_wave_part2_typed(tools, selection, document, ui, state, event,
                      stroke_components, get_distortion_style,
                      set_distortion_style, push_undo):
    _matched = False
    if tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and state.get("wave_bake_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            baked = bake_component_distortion(document.strokes[si], comp_i)
            if baked is not document.strokes[si]:
                push_undo()
                document.strokes[si] = baked
                comps_b = stroke_components(document.strokes[si])
                if 0 <= comp_i < len(comps_b):
                    n = len(_get_distortion_styles(comps_b[comp_i]))
                    state["wave_active_index"] = (max(0, n - 1) if n else 0)
                else:
                    state["wave_active_index"] = 0
        ui.wave_formula_focus = False
        state["wave_formula_focus"] = False
        state["wave_custom_draw"] = False
        state["wave_custom_finished"] = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and state.get("wave_remove_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                wi = int(state.get("wave_active_index", 0) or 0)
                _remove_distortion_style(comps[comp_i], wi)
                document.strokes[si]["components"] = comps
                n = len(_get_distortion_styles(comps[comp_i]))
                state["wave_active_index"] = (max(0, min(wi, n - 1)) if n else 0)
        ui.wave_formula_focus = False
        state["wave_formula_focus"] = False
        state["wave_custom_draw"] = False
        state["wave_custom_finished"] = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and state.get("wave_toggle_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                wi = int(state.get("wave_active_index", 0) or 0)
                w = get_distortion_style(comps[comp_i], wi)
                w["enabled"] = not bool(w.get("enabled"))
                set_distortion_style(comps[comp_i], w, wi)
                document.strokes[si]["components"] = comps
        ui.wave_formula_focus = False
        state["wave_formula_focus"] = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and any(_rr.collidepoint(event.pos) for _ri, _rr in (state.get("wave_row_rects") or [])):
        _matched = True
        # click a stack row to make that wave the active/edited one
        for _ri, _rr in (state.get("wave_row_rects") or []):
            if _rr.collidepoint(event.pos):
                if _ri != int(state.get("wave_active_index", 0) or 0):
                    state["wave_active_index"] = _ri
                    state["wave_formula_focus"] = False
                    state["wave_custom_draw"] = False
                    state["wave_custom_finished"] = False
                    ui.wave_formula_focus = False
                break
    return _matched


def handle_b_part2(ctx, event):
    s = getattr(ctx, '_app_state', None)
    if s is None:
        from controllers.app_state import AppState
        s = AppState()
        s.tools.tool_mode = getattr(ctx, 'tool_mode', 'draw')
        s.selection.selection_submode = getattr(ctx, 'selection_submode', 'transform')
        s.selection.selected_strokes = getattr(ctx, 'selected_strokes', set())
        s.selection.selected_curve = getattr(ctx, 'selected_curve', None)
        s.document.strokes = getattr(ctx, 'strokes', [])
        s.ui.wave_formula_focus = getattr(ctx, 'wave_formula_focus', False)
    return effects_wave_part2_typed(
        s.tools, s.selection, s.document, s.ui, ctx.state, event,
        ctx._stroke_components, ctx._get_distortion_style,
        ctx._set_distortion_style, ctx.push_undo,
    )
