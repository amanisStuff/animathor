"""Global shortcut and fallback key handling."""

import pygame
from models import *  # noqa: F401,F403
from views import *  # noqa: F401,F403
from controllers.coordinates import *  # noqa: F401,F403
from controllers.commands import ids as CMD


def handle_global_shortcuts(ctx, event):
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
        ctx.run_menu_action(CMD.SAVE)
    elif ctrl and event.key == pygame.K_s and ctx.shift:
        ctx.run_menu_action(CMD.SAVE_AS)
    elif ctrl and event.key == pygame.K_n:
        ctx.run_menu_action(CMD.NEW)
    elif ctrl and event.key == pygame.K_o:
        ctx.run_menu_action(CMD.OPEN)
    elif ctrl and ctx.shift and event.key == pygame.K_e:
        ctx.run_menu_action(CMD.EXPORT)
    # --- Select / clipboard / duplicate ---
    elif ctrl and event.key == pygame.K_a:
        ctx.run_menu_action(CMD.SELECT_ALL)
    elif ctrl and event.key == pygame.K_d:
        ctx.run_menu_action(CMD.DUPLICATE)
    elif ctrl and event.key == pygame.K_g:
        ctx.run_menu_action("ungroup" if ctx.shift else "group")
    elif ctrl and event.key == pygame.K_c and not ctx.shift:
        ctx.run_menu_action(CMD.COPY)
    elif ctrl and event.key == pygame.K_x:
        ctx.run_menu_action(CMD.CUT)
    elif ctrl and event.key == pygame.K_v:
        ctx.run_menu_action(CMD.PASTE)
    # --- View ---
    elif ctrl and event.key == pygame.K_0:
        ctx.run_menu_action(CMD.FIT)
    elif ctrl and event.key == pygame.K_1:
        ctx.run_menu_action(CMD.ACTUAL_SIZE)
    # --- Undo / Redo ---
    elif ctrl and event.key == pygame.K_z:
        ctx.run_menu_action("redo" if ctx.shift else "undo")
    elif ctrl and event.key == pygame.K_y:
        ctx.run_menu_action(CMD.REDO)
    # --- Tool switching (single-key, no modifiers) ---
    elif not ctrl and event.key == pygame.K_v:
        ctx.run_menu_action(CMD.TOOL_SELECT)
    elif not ctrl and event.key == pygame.K_i:
        ctx.run_menu_action(CMD.TOOL_EYEDROPPER)
    elif not ctrl and event.key == pygame.K_b:
        ctx.run_menu_action(CMD.TOOL_PEN)
    elif not ctrl and event.key == pygame.K_e:
        ctx.run_menu_action(CMD.TOOL_ERASER)
    elif not ctrl and event.key == pygame.K_f:
        ctx.run_menu_action(CMD.TOOL_BUCKET)
    elif not ctrl and event.key == pygame.K_c:
        ctx.run_menu_action(CMD.TOOL_CUTTER)
    elif not ctrl and event.key == pygame.K_t:
        ctx.run_menu_action(CMD.TOOL_TEXT)
    elif not ctrl and event.key == pygame.K_s:
        ctx.run_menu_action(CMD.TOGGLE_SNAP)
    elif not ctrl and event.key == pygame.K_HASH:
        ctx.run_menu_action(CMD.TOGGLE_GRID)
    elif ctrl and event.key == pygame.K_r:
        ctx.run_menu_action(CMD.TOGGLE_RULERS)
    elif event.key == pygame.K_SPACE:
        ctx.space_panning = True
    # --- Editing ---
    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and ctx.tool_mode == "selection":
        ctx.run_menu_action(CMD.DELETE)
    elif event.key == pygame.K_n and ctx.tool_mode == "selection":
        ctx.run_menu_action(CMD.CYCLE_SUBMODE)
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
