"""Transform field editing panel actions (part 2)."""
import copy, math, pygame
import config as cfg

from models.appearance import get_appearance, set_appearance
from models.geometry import distribute_offsets, expand_stroke_outline
from models.interaction import xform_step
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
from controllers.panel.transform_text import transform_text_click
from controllers.panel.transform_align import transform_align_click

def transform_fields_typed(tools, selection, document, drag, ui, state, event,
                           push_undo, combined_bbox, combined_obb, stroke_bbox,
                           translate_stroke, apply_xform_field, xform_current_value,
                           font_families, globals_map):
    if transform_align_click(tools, selection, document, drag, state, event,
                               push_undo, combined_obb, combined_bbox,
                               stroke_bbox, translate_stroke):
        _matched = True
    elif tools.tool_mode == "selection" and selection.selection_submode == "transform" and len(selection.selected_strokes) >= 3 and (
        state.get("distribute_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) or
        state.get("distribute_v_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
    ):
        _matched = True
        sel = sorted(i for i in selection.selected_strokes if 0 <= i < len(document.strokes))
        boxes = [stroke_bbox(document.strokes[si]) for si in sel]
        if all(boxes) and len(boxes) >= 3:
            horizontal = state.get("distribute_h_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos)
            offsets = distribute_offsets(boxes, "h" if horizontal else "v")
            push_undo()
            for si, (dx, dy) in zip(sel, offsets):
                if dx or dy:
                    document.strokes[si] = translate_stroke(document.strokes[si], dx, dy)
        selection.selected_point = None; selection.selected_curve = None; selection.selected_curves.clear(); drag.transform_drag = None; drag.drag_last = None
    elif tools.tool_mode == "selection" and selection.selection_submode == "transform" and selection.selected_strokes and (
        any(state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
            for k in ("xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
                      "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
                      "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
                      "xform_rm_rect", "xform_rp_rect"))
    ):
        _matched = True
        # Numeric transform: focus/seed value field, or nudge via the arrows.
        # Ctrl/Cmd = fine 0.1, Shift = coarse 10.0, otherwise 1.0.
        fields = ("x", "y", "w", "h", "r")
        _mods = getattr(event, "mod", None)
        if _mods is None:
            _mods = pygame.key.get_mods()
        _step = xform_step(
            fine=bool(_mods & (pygame.KMOD_CTRL | pygame.KMOD_META)),
            coarse=bool(_mods & pygame.KMOD_SHIFT),
        )
        handled_xform = False
        for fk in fields:
            if state.get(f"xform_{fk}_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                cur = xform_current_value(fk)
                if cur is not None:
                    if fk == "r":
                        seed = "0"
                    else:
                        seed = f"{cur:.3f}".rstrip("0").rstrip(".") or "0"
                    ui.xform_field_focus = fk
                    ui.xform_field_buffer = seed
                    state["xform_field_focus"] = fk
                    state["xform_field_buffer"] = seed
                handled_xform = True
                break
            if state.get(f"xform_{fk}m_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                apply_xform_field(fk, -_step, relative=True)
                ui.xform_field_focus = None
                ui.xform_field_buffer = ""
                state["xform_field_focus"] = None
                state["xform_field_buffer"] = ""
                handled_xform = True
                break
            if state.get(f"xform_{fk}p_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
                apply_xform_field(fk, _step, relative=True)
                ui.xform_field_focus = None
                ui.xform_field_buffer = ""
                state["xform_field_focus"] = None
                state["xform_field_buffer"] = ""
                handled_xform = True
                break
        if handled_xform:
            selection.selected_point = None; selection.selected_curve = None; selection.selected_curves.clear(); drag.transform_drag = None; drag.drag_last = None; drag.pending_transform_toggle = None
    elif tools.tool_mode == "selection" and selection.selection_submode == "transform" and selection.selected_strokes and any(
        state.get(k, pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos)
        for k in ("width_profile_prev_rect", "width_profile_next_rect")
    ):
        _matched = True
        wk = "width_profile_prev_rect" if state.get("width_profile_prev_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos) else "width_profile_next_rect"
        step_dir = -1 if wk == "width_profile_prev_rect" else 1
        profiles = list(WIDTH_PROFILES) if 'WIDTH_PROFILES' in globals_map else ["uniform", "taper_in", "taper_out", "taper_both", "pressure"]
        if 'apply_width_profile' in globals_map:
            push_undo()
            for si in sorted(selection.selected_strokes):
                if 0 <= si < len(document.strokes) and isinstance(document.strokes[si], dict):
                    cur = document.strokes[si].get("width_profile")
                    if cur not in profiles:
                        cur = "uniform"
                    ni = (profiles.index(cur) + step_dir) % len(profiles)
                    document.strokes[si] = apply_width_profile(document.strokes[si], profiles[ni])
    elif tools.tool_mode == "selection" and selection.selection_submode == "transform" and selection.selected_strokes and any(
        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for k in ("marker_start_rect", "marker_end_rect")
    ):
        _matched = True
        mk_key = "marker_start_rect" if state.get("marker_start_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos) else "marker_end_rect"
        end = "start" if mk_key == "marker_start_rect" else "end"
        ui.marker_dropdown = None if ui.marker_dropdown == end else end
        state["marker_dropdown"] = ui.marker_dropdown
    elif tools.tool_mode == "selection" and selection.selection_submode == "transform" and selection.selected_strokes and any(
        state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos)
        for k in ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
                  "dash_prev_rect", "dash_next_rect")
    ):
        _matched = True
        skey = next(k for k in ("cap_prev_rect", "cap_next_rect", "join_prev_rect", "join_next_rect",
                                "dash_prev_rect", "dash_next_rect")
                    if state.get(k, pygame.Rect(0,0,0,0)).collidepoint(event.pos))
        if skey.startswith("cap_"):
            field, opts = "line_cap", ["butt", "round", "square"]
        elif skey.startswith("join_"):
            field, opts = "line_join", ["miter", "round", "bevel"]
        else:
            field, opts = "dash", [None, "dashed", "dotted"]
        step_dir = -1 if skey.endswith("_prev_rect") else 1
        push_undo()
        for si in sorted(selection.selected_strokes):
            if 0 <= si < len(document.strokes) and isinstance(document.strokes[si], dict):
                updated = dict(document.strokes[si])
                cur = updated.get(field)
                if field == "dash" and cur not in opts:
                    cur = None
                if cur not in opts:
                    cur = opts[0]
                idx = (opts.index(cur) + step_dir) % len(opts)
                updated[field] = opts[idx]
                document.strokes[si] = updated
    elif transform_text_click(tools, selection, document, drag, ui, state, event,
                               push_undo, font_families):
        _matched = True
    return None


def _handle_panel_click_a_p2(ctx, event):
    """Compat wrapper for the typed transform-field handler."""
    s = getattr(ctx, '_app_state', None)
    if s is None:
        from controllers.app_state import AppState
        s = AppState()
        for obj, names in (
            (s.tools, ('tool_mode', 'draw_tool', 'text_family', 'text_size')),
            (s.selection, ('selected_strokes', 'selected_point', 'selected_curve',
                           'selected_curves', 'selection_submode')),
            (s.document, ('strokes',)),
            (s.drag, ('drag_last', 'pending_transform_toggle', 'pivot_pos',
                      'transform_drag', 'current_points', 'drawing')),
            (s.ui, ('xform_field_focus', 'xform_field_buffer', 'marker_dropdown',
                    'text_entry')),
        ):
            for name in names:
                if hasattr(ctx, name):
                    setattr(obj, name, getattr(ctx, name))
    return transform_fields_typed(
        s.tools, s.selection, s.document, s.drag, s.ui, ctx.state, event,
        getattr(ctx, 'push_undo', None), getattr(ctx, 'combined_bbox', None),
        getattr(ctx, 'combined_obb', None), getattr(ctx, 'stroke_bbox', None),
        getattr(ctx, 'translate_stroke', None),
        getattr(ctx, '_apply_xform_field', None),
        getattr(ctx, '_xform_current_value', None),
        getattr(ctx, 'FONT_FAMILIES', []),
        globals(),
    )
