"""Align / distribute / mirror panel actions (part 3)."""
import copy, math, pygame
import config as cfg

from models.appearance import get_appearance, set_appearance
from models.geometry import distribute_offsets, expand_stroke_outline
from models.strokes import (
    WIDTH_PROFILES,
    _component_ranges,
    _is_closed_segs,
    add_anchor_at,
    apply_width_profile,
    delete_anchor,
    join_components_in_stroke,
    mirror_stroke,
    reverse_stroke,
    segs_of,
    set_anchor_smooth,
    set_path_closed,
)
from models.text import update_text_stroke
from controllers.panel.text_actions import text_actions_click

def align_distribute_typed(tools, selection, document, drag, ui, state, event,
                            push_undo, clamp):
    _matched = False
    if text_actions_click(tools, selection, document, state, event, push_undo):
        _matched = True
    elif tools.tool_mode == "selection" and selection.selected_strokes and state.get(
        "obj_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        bar = state["obj_opacity_rect"]
        opacity = clamp((event.pos[0] - bar.x) / max(1, bar.w - 1), 0.0, 1.0)
        push_undo()
        for si in sorted(selection.selected_strokes):
            if 0 <= si < len(document.strokes) and isinstance(document.strokes[si], dict):
                document.strokes[si] = set_appearance(document.strokes[si], opacity=opacity)
        ui.obj_opacity_drag = True
        state["obj_opacity_drag"] = True
    elif tools.tool_mode == "selection" and selection.selected_strokes and any(
        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for k in ("shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")
    ):
        _matched = True
        appear_keys = ("shadow_toggle_rect", "shadow_blur_minus_rect", "shadow_blur_plus_rect")
        appear_key = next(k for k in appear_keys
                          if state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
        push_undo()
        for si in sorted(selection.selected_strokes):
            if not (0 <= si < len(document.strokes)) or not isinstance(document.strokes[si], dict):
                continue
            app = get_appearance(document.strokes[si])
            if appear_key == "shadow_toggle_rect":
                shadow = app["shadow"] if app["shadow"] is not None else {
                    "dx": 6.0, "dy": 6.0, "blur": 6.0,
                    "opacity": 0.35, "color": (0.0, 0.0, 0.0, 1.0)}
                document.strokes[si] = set_appearance(document.strokes[si], shadow=shadow if app["shadow"] is None else None)
            else:
                shadow = app["shadow"]
                if shadow is None:
                    shadow = {"dx": 6.0, "dy": 6.0, "blur": 6.0,
                              "opacity": 0.35, "color": (0.0, 0.0, 0.0, 1.0)}
                step = -2.0 if appear_key == "shadow_blur_minus_rect" else 2.0
                shadow = dict(shadow)
                shadow["blur"] = max(0.0, min(64.0, float(shadow.get("blur", 4.0)) + step))
                document.strokes[si] = set_appearance(document.strokes[si], shadow=shadow)
    elif tools.tool_mode == "selection" and selection.selection_submode == "nodes" and any(
        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for k in ("path_close_rect", "path_reverse_rect", "path_add_rect",
                  "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                  "path_expand_rect")
    ):
        _matched = True
        path_keys = ("path_close_rect", "path_reverse_rect", "path_add_rect",
                     "path_delete_rect", "path_smooth_rect", "path_corner_rect",
                     "path_expand_rect")
        path_key = next(k for k in path_keys
                        if state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
        sel_idx = sorted(i for i in selection.selected_strokes if 0 <= i < len(document.strokes))
        if sel_idx:
            si = sel_idx[0]
            st = document.strokes[si]
            seg_i, pname = selection.selected_point if selection.selected_point else (0, "p0")
            if pname not in ("p0", "p3"):
                pname = "p0" if pname == "c1" else "p3"
            seg_i = max(0, min(int(seg_i), len(segs_of(st)) - 1))
            push_undo()
            if path_key == "path_close_rect":
                document.strokes[si] = set_path_closed(st, not _is_closed_segs(segs_of(st)))
            elif path_key == "path_reverse_rect":
                document.strokes[si] = reverse_stroke(st)
            elif path_key == "path_add_rect":
                document.strokes[si] = add_anchor_at(st, seg_i, 0.5)
                selection.selected_point = (seg_i, "p0")
            elif path_key == "path_delete_rect":
                document.strokes[si] = delete_anchor(st, seg_i, pname)
                selection.selected_point = None
            elif path_key == "path_smooth_rect":
                document.strokes[si] = set_anchor_smooth(st, seg_i, pname, True)
            elif path_key == "path_expand_rect":
                expanded = expand_stroke_outline(st)
                if expanded is not None:
                    document.strokes[si] = expanded
                else:
                    # Nothing to expand (zero-width path): undo the push.
                    document.strokes[si] = st
                    if document.undo_stack:
                        document.undo_stack.pop()
                selection.selected_point = None
            else:
                document.strokes[si] = set_anchor_smooth(st, seg_i, pname, False)
            drag.transform_drag = None; drag.drag_last = None
    elif tools.tool_mode == "selection" and state.get("eyedropper_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        tools.eyedropper_pick = not tools.eyedropper_pick
        state["eyedropper_pick"] = tools.eyedropper_pick
        drag.cutting = False; drag.cut_points = []
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and state.get("curve_join_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        if len(selection.selected_curves) >= 2:
            by_stroke = {}
            for si, ci in list(selection.selected_curves):
                by_stroke.setdefault(si, set()).add(int(ci))
            results = {}
            for si, idxs in by_stroke.items():
                if 0 <= si < len(document.strokes):
                    new_st, index_map = join_components_in_stroke(document.strokes[si], idxs)
                    if index_map is not None:
                        results[si] = (new_st, index_map, idxs)
            if results:
                push_undo()
                new_selected_curves = set()
                for si, idxs in by_stroke.items():
                    if si in results:
                        new_st, index_map, _idxs2 = results[si]
                        document.strokes[si] = new_st
                        for ci in idxs:
                            new_selected_curves.add((si, int(index_map.get(ci, ci))))
                    elif 0 <= si < len(document.strokes):
                        for ci in idxs:
                            new_selected_curves.add((si, int(ci)))
                selection.selected_curves = new_selected_curves
                selection.selected_curve = next(iter(selection.selected_curves), None)
                selection.selected_strokes = {si for si, _ in selection.selected_curves}
        selection.selected_point = None; drag.transform_drag = None; drag.drag_last = None
        tools.eyedropper_pick = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and state.get("curve_cut_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        tools.curve_cut_mode = not tools.curve_cut_mode
        state["curve_cut_mode"] = tools.curve_cut_mode
        drag.cutting = False; drag.cut_points = []
        selection.selected_point = None; drag.transform_drag = None; drag.drag_last = None
        tools.eyedropper_pick = False
    elif tools.tool_mode == "selection" and selection.selection_submode == "curve" and state.get("curve_redraw_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        _matched = True
        if selection.selected_curve and selection.selected_curve[0] in selection.selected_strokes:
            si, comp_i = selection.selected_curve
            fixed_start = fixed_end = None
            if 0 <= si < len(document.strokes):
                segs = segs_of(document.strokes[si])
                ranges = _component_ranges(document.strokes[si])
                if 0 <= comp_i < len(ranges):
                    s0, s1 = ranges[comp_i]
                    if s1 > s0 and s1 <= len(segs):
                        fixed_start = tuple(segs[s0][0])
                        fixed_end = tuple(segs[s1 - 1][3])
            drag.redrawing_curve = {
                "stroke_idx": si, "comp_idx": comp_i, "points": [],
                "started": False, "fixed_start": fixed_start, "fixed_end": fixed_end,
            }
            selection.selected_point = None; drag.transform_drag = None; drag.drag_last = None
    return "handled" if _matched else None



# Semantic alias


def _handle_panel_click_a_p3(ctx, event):
    """Compat wrapper for the typed align/distribute handler."""
    s = getattr(ctx, '_app_state', None)
    if s is None:
        from controllers.app_state import AppState
        s = AppState()
        for obj, names in (
            (s.tools, ('tool_mode', 'selection_submode', 'curve_cut_mode',
                       'eyedropper_pick', 'text_size')),
            (s.selection, ('selected_strokes', 'selected_point', 'selected_curve',
                           'selected_curves')),
            (s.document, ('strokes', 'undo_stack')),
            (s.drag, ('cutting', 'cut_points', 'drag_last', 'transform_drag',
                      'pending_transform_toggle', 'redrawing_curve')),
            (s.ui, ('obj_opacity_drag',)),
        ):
            for name in names:
                if hasattr(ctx, name):
                    setattr(obj, name, getattr(ctx, name))
    return align_distribute_typed(
        s.tools, s.selection, s.document, s.drag, s.ui, ctx.state, event,
        getattr(ctx, 'push_undo', None), getattr(ctx, 'clamp', None),
    )
