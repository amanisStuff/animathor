"""Extracted handler: handle_keydown."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

def handle_keydown(ctx, event=None):
    if ctx.menu_open is not None and event.key == pygame.K_ESCAPE:
        ctx.menu_open = None
        return 'continue'
    if ctx.help_open:
        if event.key == pygame.K_ESCAPE:
            ctx.help_open = False
            ctx.menu_open = None
        return 'continue'
    if ctx.export_dialog_open:
        if event.key == pygame.K_ESCAPE:
            ctx.export_dialog_open = False
        return 'continue'
    if ctx.text_entry is not None:
        # Text insertion mode: capture keystrokes into the buffer so
        # single-letter tool shortcuts never fire while typing.
        if event.key == pygame.K_ESCAPE:
            ctx.text_entry = None
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            ctx.commit_text_entry()
        elif event.key == pygame.K_BACKSPACE:
            ctx.text_entry["text"] = ctx.text_entry["text"][:-1]
        elif event.key in (pygame.K_UP, pygame.K_DOWN) and \
                bool(pygame.key.get_mods() & pygame.KMOD_CTRL):
            ctx.text_entry["size"] = max(4.0, min(400.0,
                ctx.text_entry["size"] + (2.0 if event.key == pygame.K_UP else -2.0)))
        elif event.unicode and event.unicode.isprintable():
            if len(ctx.text_entry["text"]) < 500:
                ctx.text_entry["text"] += event.unicode
        return 'continue'
    if ctx.xform_field_focus is not None and ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and ctx.selected_strokes:
        if event.key == pygame.K_ESCAPE:
            ctx._cancel_xform_field()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            ctx._commit_xform_field()
        elif event.key == pygame.K_BACKSPACE:
            ctx.xform_field_buffer = str(ctx.xform_field_buffer)[:-1]
            ctx.state["xform_field_buffer"] = ctx.xform_field_buffer
        elif event.key == pygame.K_UP:
            ctx.step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
            ctx._apply_xform_field(ctx.xform_field_focus, ctx.step, relative=True)
            ctx.xform_field_buffer = ""
            ctx.state["xform_field_buffer"] = ""
        elif event.key == pygame.K_DOWN:
            ctx.step = 10.0 if bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1.0
            ctx._apply_xform_field(ctx.xform_field_focus, -ctx.step, relative=True)
            ctx.xform_field_buffer = ""
            ctx.state["xform_field_buffer"] = ""
        elif event.unicode and (event.unicode.isdigit() or event.unicode in ".-"):
            if len(str(ctx.xform_field_buffer)) < 24:
                ctx.xform_field_buffer = str(ctx.xform_field_buffer) + event.unicode
                ctx.state["xform_field_buffer"] = ctx.xform_field_buffer
        return 'continue'
    elif ctx.xform_field_focus is not None:
        # Focus is stale (wrong mode/selection) — clear so keys aren't trapped.
        ctx._cancel_xform_field()
    # Bezier pen: Enter finishes open path, Escape cancels.
    if ctx.bezier_pen is not None and ctx.tool_mode == "draw" and ctx.draw_tool == "pen" and ctx.draw_shape == "pen":
        if event.key == pygame.K_ESCAPE:
            ctx._bezier_pen_cancel()
            return 'continue'
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if len(ctx.bezier_pen.get("anchors", [])) >= 2:
                ctx._bezier_pen_finish(close_path=False)
            else:
                ctx._bezier_pen_cancel()
            return 'continue'
        if event.key == pygame.K_BACKSPACE:
            # Remove last placed anchor (useful correction while drawing).
            ctx.anchors = ctx.bezier_pen.get("anchors", [])
            if len(ctx.anchors) > 1:
                ctx.anchors.pop()
                ctx.bezier_pen["mouse_down"] = False
                ctx.bezier_pen["dragging"] = False
            else:
                ctx._bezier_pen_cancel()
            return 'continue'
    if ctx.wave_formula_focus and ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                ctx.wi = int(ctx.state.get("wave_active_index", 0) or 0)
                ctx.w = _get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                if ctx.w.get("type") == "wave":
                    formula = str(ctx.w.get("formula", "sin(x)") or "")
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        ctx.wave_formula_focus = False
                        ctx.state["wave_formula_focus"] = False
                    elif event.key == pygame.K_BACKSPACE:
                        formula = formula[:-1]
                        ctx.w["formula"] = formula
                        _set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
                    elif event.unicode and event.unicode.isprintable():
                        formula += event.unicode
                        ctx.w["formula"] = formula
                        _set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
                else:
                    ctx.wave_formula_focus = False
                    ctx.state["wave_formula_focus"] = False
        # consume key while editing formula (except we already handled)
        if ctx.wave_formula_focus or event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE) or (event.unicode and event.unicode.isprintable()):
            pass
    elif ctx.state.get("wave_custom_draw") and ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and ctx.selected_curve[0] in ctx.selected_strokes:
        # custom wave draw mode key handling: Esc/Enter finishes
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    ctx.state["wave_custom_draw"] = False
                    ctx.state["wave_custom_finished"] = True
    else:
        ctx.mods = pygame.key.get_mods()
        ctrl = bool(ctx.mods & pygame.KMOD_CTRL)
        ctx.shift = bool(ctx.mods & pygame.KMOD_SHIFT)
        # --- Esc: cancel/deselect first, quit only as fallback ---
        if event.key == pygame.K_ESCAPE:
            if ctx.eyedropper_pick:
                ctx.eyedropper_pick = False
            elif ctx.redrawing_curve is not None:
                ctx.redrawing_curve = None
            elif ctx.marquee_select is not None:
                ctx.marquee_select = None
            elif ctx.drawing:
                ctx.drawing = False; ctx.current_points = []
            elif ctx.transform_drag is not None or ctx.drag_last is not None or ctx.selected_strokes or ctx.selected_point or ctx.selected_curve:
                ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
                ctx.transform_drag = None; ctx.drag_last = None
            elif ctx.space_panning:
                ctx.space_panning = False; ctx.pan_drag = None
            else:
                ctx.running = False
        # --- File: Save / Open / Export ---
        elif ctrl and event.key == pygame.K_s and not ctx.shift:
            ctx.run_menu_action("save")
        elif ctrl and event.key == pygame.K_s and ctx.shift:
            ctx.run_menu_action("save_as")
        elif ctrl and event.key == pygame.K_n:
            ctx.run_menu_action("new")
        elif ctrl and event.key == pygame.K_o:
            ctx.run_menu_action("open")
        elif ctrl and ctx.shift and event.key == pygame.K_e:
            ctx.run_menu_action("export")
        # --- Select / clipboard / duplicate ---
        elif ctrl and event.key == pygame.K_a:
            ctx.run_menu_action("select_all")
        elif ctrl and event.key == pygame.K_d:
            ctx.run_menu_action("duplicate")
        elif ctrl and event.key == pygame.K_g:
            ctx.run_menu_action("ungroup" if ctx.shift else "group")
        elif ctrl and event.key == pygame.K_c and not ctx.shift:
            ctx.run_menu_action("copy")
        elif ctrl and event.key == pygame.K_x:
            ctx.run_menu_action("cut")
        elif ctrl and event.key == pygame.K_v:
            ctx.run_menu_action("paste")
        # --- View ---
        elif ctrl and event.key == pygame.K_0:
            ctx.run_menu_action("fit")
        elif ctrl and event.key == pygame.K_1:
            ctx.run_menu_action("actual_size")
        # --- Undo / Redo ---
        elif ctrl and event.key == pygame.K_z:
            ctx.run_menu_action("redo" if ctx.shift else "undo")
        elif ctrl and event.key == pygame.K_y:
            ctx.run_menu_action("redo")
        # --- Tool switching (single-key, no modifiers) ---
        elif not ctrl and event.key == pygame.K_v:
            ctx.run_menu_action("tool_select")
        elif not ctrl and event.key == pygame.K_i:
            ctx.run_menu_action("tool_eyedropper")
        elif not ctrl and event.key == pygame.K_b:
            ctx.run_menu_action("tool_pen")
        elif not ctrl and event.key == pygame.K_e:
            ctx.run_menu_action("tool_eraser")
        elif not ctrl and event.key == pygame.K_f:
            ctx.run_menu_action("tool_bucket")
        elif not ctrl and event.key == pygame.K_c:
            ctx.run_menu_action("tool_cutter")
        elif not ctrl and event.key == pygame.K_t:
            ctx.run_menu_action("tool_text")
        elif not ctrl and event.key == pygame.K_s:
            ctx.run_menu_action("toggle_snap")
        elif not ctrl and event.key == pygame.K_HASH:
            ctx.run_menu_action("toggle_grid")
        elif ctrl and event.key == pygame.K_r:
            ctx.run_menu_action("toggle_rulers")
        elif event.key == pygame.K_SPACE:
            ctx.space_panning = True
        # --- Editing ---
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and ctx.tool_mode == "selection":
            ctx.run_menu_action("delete")
        elif event.key == pygame.K_n and ctx.tool_mode == "selection":
            ctx.run_menu_action("cycle_submode")
        elif event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS):
            ctx.max_points_per_curve = max(2, ctx.max_points_per_curve - 1); ctx.slider.value = ctx.max_points_per_curve
        elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            ctx.limit = ctx.BOOST_MAX_POINTS if ctx.boost_points else ctx.NORMAL_MAX_POINTS
            ctx.max_points_per_curve = min(ctx.limit, ctx.max_points_per_curve + 1); ctx.slider.value = ctx.max_points_per_curve
        elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            if ctx.drawing and ctx.tool_mode == "draw" and ctx.current_points:
                ctx.snap = ctx.nearest_snap_point(ctx.current_points[0], ctx.strokes, ctx.snap_radius())
                if ctx.snap is not None:
                    ctx.current_points[0] = ctx.snap
            elif ctx.redrawing_curve is not None and ctx.redrawing_curve.get("started") and ctx.redrawing_curve.get("points"):
                if ctx.redrawing_curve.get("fixed_start") is None:
                    ctx.snap = ctx.nearest_snap_point(ctx.redrawing_curve["points"][0], ctx.strokes, ctx.snap_radius())
                    if ctx.snap is not None:
                        ctx.redrawing_curve["points"][0] = ctx.snap
    return None
