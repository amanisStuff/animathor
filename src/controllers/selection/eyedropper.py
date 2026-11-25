"""Eyedropper style pick/apply in selection mode.

The core logic is a typed contract over AppState substates; ``handle_eyedropper``
is a compat wrapper for the extracted ctx-based callers.
"""

import copy
from models import hit_test_component, hit_test_stroke  # noqa: F401
from models.strokes import _effective_component_style  # noqa: F401
from models.waves import _get_distortion_styles, _is_distortion_style  # noqa: F401


def eyedropper_hit(tools, document, selection, state, event, to_canvas,
                   stroke_components, set_distortion_style, push_undo):
    """Pick style from the clicked stroke and apply it to the selection."""
    if not tools.eyedropper_pick:
        return None
    cpos = to_canvas(event.pos)
    hit = hit_test_stroke(cpos, document.strokes)
    strokes = document.strokes
    if hit is not None and 0 <= hit < len(strokes):
        src_stroke = strokes[hit]
        src_comp_i = hit_test_component(src_stroke, cpos)
        if src_comp_i is None:
            src_comp_i = 0
        src_sc, src_sw = _effective_component_style(src_stroke, src_comp_i)
        src_fc = src_stroke.get("fill_color")
        src_fg = copy.deepcopy(src_stroke.get("fill_gradient")) if isinstance(src_stroke, dict) else None
        src_comps = stroke_components(src_stroke)
        if 0 <= src_comp_i < len(src_comps):
            src_dists = copy.deepcopy(_get_distortion_styles(src_comps[src_comp_i]))
        else:
            src_dists = []
        had_sel = bool(selection.selected_strokes)
        if not had_sel:
            selection.selected_strokes = {hit}
            if selection.selection_submode == "curve":
                selection.selected_curve = (hit, src_comp_i)
            else:
                selection.selected_curve = None
        else:
            push_undo()
            for si in list(selection.selected_strokes):
                if not (0 <= si < len(strokes)):
                    continue
                st = strokes[si]
                st["stroke_width"] = float(src_sw)
                st["fill_color"] = copy.deepcopy(src_fc) if src_fc is not None else None
                st["fill_gradient"] = copy.deepcopy(src_fg) if src_fg is not None else None
                if (selection.selection_submode == "curve" and selection.selected_curve
                        and selection.selected_curve[0] == si and len(selection.selected_strokes) == 1):
                    ci = selection.selected_curve[1]
                    comps = stroke_components(st)
                    if 0 <= ci < len(comps):
                        comps[ci] = copy.deepcopy(comps[ci])
                        comps[ci]["stroke_color"] = copy.deepcopy(src_sc)
                        comps[ci]["stroke_width"] = float(src_sw)
                        comps[ci].pop("wave", None)
                        comps[ci]["styles"] = [s for s in comps[ci].get("styles", []) if not _is_distortion_style(s)]
                        for wi, wv in enumerate(src_dists):
                            set_distortion_style(comps[ci], wv, wi)
                        st["components"] = comps
                else:
                    st["stroke_color"] = copy.deepcopy(src_sc)
                    comps = stroke_components(st)
                    if comps:
                        new_comps = []
                        for comp in comps:
                            comp = copy.deepcopy(comp)
                            comp.pop("stroke_color", None)
                            comp.pop("stroke_width", None)
                            comp.pop("wave", None)
                            comp["styles"] = [s for s in comp.get("styles", []) if not _is_distortion_style(s)]
                            for wi, wv in enumerate(src_dists):
                                set_distortion_style(comp, wv, wi)
                            new_comps.append(comp)
                        st["components"] = new_comps
        tools.eyedropper_pick = False
        state["eyedropper_pick"] = False
    return 'handled'


def handle_eyedropper(ctx, event):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        return None
    result = eyedropper_hit(
        app_state.tools, app_state.document, app_state.selection, ctx.state, event,
        ctx.to_canvas, ctx._stroke_components, ctx._set_distortion_style, ctx.push_undo,
    )
    if result == 'handled':
        ctx.eyedropper_pick = app_state.tools.eyedropper_pick
    return result
