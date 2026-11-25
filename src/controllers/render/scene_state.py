"""Render semantic domain: scene preparation and Cairo composition."""
"""Render frame (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from config import RULER_BG_RGB, RULER_SIZE, RULER_TEXT_RGB, RULER_TICK_RGB  # noqa: F401
from models import combined_obb, grid_positions, normalize_rect, ruler_ticks  # noqa: F401
from views import BORDER_WIDTH, CANVAS_BACKDROP, CUT_COLOR, CUT_HANDLE_RADIUS, EDITOR_LINE_WIDTH_BOLD, PANEL_BORDER, SELECTION_BORDER, SELECTION_FILL, SURFACE, draw_bottom_shape_toolbar, draw_export_dialog, draw_left_toolbar, draw_marker_dropdown, draw_menu_bar, draw_panel, draw_panel_toggle, draw_scene, draw_shape_context_menu, draw_shortcuts_overlay, surface_to_pygame  # noqa: F401


def render_scene(ctx):
    # Draw scene (Cairo) and blit at canvas offset
    ctx.active = ctx.current_points if (ctx.drawing and ctx.tool_mode == "draw") else (ctx.redrawing_curve.get("points") if ctx.redrawing_curve else None)
    # While placing text, render the typed buffer as a live editable outline.
    render_strokes = ctx.strokes
    text_preview_index = None
    if ctx.workspace == "library" and ctx.shape_states:
        # Library workspace: browse the saved shape states as canvas content.
        _lib = []
        for _sid, _sdef in ctx.shape_states.items():
            if not isinstance(_sdef, dict) or not isinstance(_sdef.get("strokes"), list):
                continue
            _org = _sdef.get("origin") or [0.0, 0.0]
            try:
                _ox = float(_org[0]); _oy = float(_org[1])
            except Exception:
                _ox = _oy = 0.0
            for _st in _sdef["strokes"]:
                if not isinstance(_st, dict):
                    continue
                ctx._n = copy.deepcopy(_st)
                ctx._n.pop("shape_state_id", None); ctx._n.pop("shape_state_is_master", None); ctx._n.pop("shape_state_instance_id", None)
                try:
                    ctx._n = ctx.translate_stroke(ctx._n, _ox, _oy)
                except Exception:
                    pass
                _lib.append(ctx._n)
        render_strokes = _lib
    if ctx.text_entry is not None and str(ctx.text_entry.get("text", "")):
        try:
            _tc = ctx.hsv_to_rgb(ctx.picker_h, ctx.picker_s, ctx.picker_v)
            _preview = ctx.new_text_stroke(ctx.text_entry["text"], ctx.text_entry["x"],
                                       ctx.text_entry["y"], ctx.text_entry["family"],
                                       ctx.text_entry["size"],
                                       color=(_tc[0], _tc[1], _tc[2], 1.0))
            render_strokes = list(ctx.strokes) + [_preview]
            text_preview_index = len(render_strokes) - 1
        except Exception:
            render_strokes = ctx.strokes
    _eff_pivot = None
    _grad_edit_info = None
    if ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes:
        _pobb = combined_obb(ctx.strokes, ctx.selected_strokes)
        if _pobb:
            _eff_pivot = ctx.pivot_pos if ctx.pivot_pos is not None else (_pobb["cx"], _pobb["cy"])
        if ctx.state.get("color_target", ctx.color_target) == "fill":
            for _gsi in sorted(ctx.selected_strokes):
                if 0 <= _gsi < len(ctx.strokes):
                    _gst = ctx.strokes[_gsi]
                    _gfg = _gst.get("fill_gradient") if isinstance(_gst, dict) else None
                    try:
                        _gfg = ctx.get_fill_gradient(_gst) or _gfg
                    except Exception:
                        pass
                    if isinstance(_gfg, dict) and str(_gfg.get("type")) in ("linear", "radial", "conic", "spiral", "diamond", "square"):
                        try:
                            _grad_edit_info = ctx.gradient_edit_handles(_gst, _gfg)
                            if isinstance(_grad_edit_info, dict):
                                _grad_edit_info["stroke_i"] = _gsi
                        except Exception:
                            _grad_edit_info = None
                        break
    # Set OBB on selection (not at creation).
    for _si in list(ctx.selected_strokes):
        if 0 <= _si < len(ctx.strokes):
            try:
                ctx.get_stroke_obb(ctx.strokes[_si])
            except Exception:
                pass
    draw_scene(
        ctx.cairo_surface, render_strokes, ctx.active, snap_point=ctx.hover_snap,
        selected_indices=ctx.selected_strokes, edit_mode=(ctx.tool_mode == "selection"),
        selection_submode=ctx.selection_submode, selected_curve=ctx.selected_curve,
        selected_curves=set(ctx.selected_curves),
        snap_kind=ctx.hover_snap_kind, redrawing_curve=ctx.redrawing_curve,
        ref_img=ctx.reference_image,
        pivot_pos=_eff_pivot,
        transform_handle_mode=ctx.transform_handle_mode,
        gradient_edit_info=_grad_edit_info,
        guides=ctx.guides,
        smart_guides=ctx.smart_snap_guides,
        bezier_pen=ctx.bezier_pen,
        artboards=ctx.artboards,
        active_artboard=ctx.active_artboard,
    )
    ctx.frame = surface_to_pygame(ctx.cairo_surface)
    ctx.screen.fill(CANVAS_BACKDROP)
    ctx.screen.blit(ctx.frame, (cfg.CANVAS_X, ctx.TOP_BAR_H))

