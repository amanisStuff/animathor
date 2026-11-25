"""effects wave apply."""
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


from controllers.panel.wave_hits import _b3_wave_hits, _b3_wave_sliders
from controllers.panel.color_target import _b3_color
def effects_wave_part3_typed(tools, selection, document, ui, state, event, ctx,
                      stroke_components, get_distortion_style,
                      set_distortion_style, push_undo):
    _matched = False
    if tools.tool_mode == "selection" and selection.selection_submode == "curve" and selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes:
        _matched = True
        _w_hit = False
        wi = int(state.get("wave_active_index", 0) or 0)
        # displacement profile selector (flat/custom)
        for key, r in (state.get("displacement_profile_rects") or {}).items():
            if r.collidepoint(event.pos):
                si, comp_i = selection.selected_curve
                if 0 <= si < len(document.strokes):
                    comps = stroke_components(document.strokes[si])
                    if 0 <= comp_i < len(comps):
                        comps[comp_i] = dict(comps[comp_i])
                        w = get_distortion_style(comps[comp_i], wi)
                        if w.get("type") == "displacement":
                            w["profile"] = key
                            set_distortion_style(comps[comp_i], w, wi)
                            document.strokes[si]["components"] = comps
                            if key == "custom":
                                state["wave_custom_draw"] = True
                                state["wave_custom_finished"] = False
                                state["wave_formula_focus"] = False
                                ui.wave_formula_focus = False
                            else:
                                state["wave_custom_draw"] = False
                                state["wave_custom_finished"] = False
                _w_hit = True
                break
        # displacement "apply to" toggles (X/Y/Rotate/Length), combinable
        _w_hit = _b3_wave_hits(ctx, event, _w_hit)
        _w_hit = _b3_wave_sliders(ctx, event, _w_hit)
        _w_hit = _b3_color(ctx, event, _w_hit)
    return _matched



def handle_b_part3(ctx, event):
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
    return effects_wave_part3_typed(
        s.tools, s.selection, s.document, s.ui, ctx.state, event, ctx,
        ctx._stroke_components, ctx._get_distortion_style,
        ctx._set_distortion_style, ctx.push_undo,
    )
