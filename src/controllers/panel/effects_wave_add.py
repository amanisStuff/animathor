"""effects wave add."""
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


def effects_wave_part1_typed(tools, selection, document, ui, state, event,
                      stroke_components, get_distortion_style,
                      set_distortion_style, push_undo):
    _matched = False
    if tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and state.get("wave_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                # append a new wave style to the stack and edit it
                n = len(_get_distortion_styles(comps[comp_i]))
                w = default_wave_params()
                w["enabled"] = True
                set_distortion_style(comps[comp_i], w, n)
                document.strokes[si]["components"] = comps
                state["wave_active_index"] = n
                state["wave_custom_finished"] = False
        ui.wave_formula_focus = False
        state["wave_formula_focus"] = False
        state["wave_custom_draw"] = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and state.get("displacement_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                n = len(_get_distortion_styles(comps[comp_i]))
                d = default_displacement_params()
                d["enabled"] = True
                set_distortion_style(comps[comp_i], d, n)
                document.strokes[si]["components"] = comps
                state["wave_active_index"] = n
                state["wave_custom_finished"] = False
        ui.wave_formula_focus = False
        state["wave_formula_focus"] = False
        state["wave_custom_draw"] = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and state.get("repeat_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                n = len(_get_distortion_styles(comps[comp_i]))
                r = default_repeat_params()
                r["enabled"] = True
                set_distortion_style(comps[comp_i], r, n)
                document.strokes[si]["components"] = comps
                state["wave_active_index"] = n
                state["wave_custom_finished"] = False
        ui.wave_formula_focus = False
        state["wave_formula_focus"] = False
        state["wave_custom_draw"] = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes and state.get("thickness_add_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        si, comp_i = selection.selected_curve
        if 0 <= si < len(document.strokes):
            comps = stroke_components(document.strokes[si])
            if 0 <= comp_i < len(comps):
                comps[comp_i] = dict(comps[comp_i])
                n = len(_get_distortion_styles(comps[comp_i]))
                th = default_thickness_params()
                th["enabled"] = True
                set_distortion_style(comps[comp_i], th, n)
                document.strokes[si]["components"] = comps
                state["wave_active_index"] = n
                state["wave_custom_finished"] = False
        ui.wave_formula_focus = False
        state["wave_formula_focus"] = False
        state["wave_custom_draw"] = False
    return _matched


def handle_b_part1(ctx, event):
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
    return effects_wave_part1_typed(
        s.tools, s.selection, s.document, s.ui, ctx.state, event,
        ctx._stroke_components, ctx._get_distortion_style,
        ctx._set_distortion_style, ctx.push_undo,
    )
