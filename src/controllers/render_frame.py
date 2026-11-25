"""Render frame orchestrator (semantic split: controllers/render/*)."""
"""Render frame (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from config import RULER_BG_RGB, RULER_SIZE, RULER_TEXT_RGB, RULER_TICK_RGB  # noqa: F401
from models import combined_obb, grid_positions, normalize_rect, ruler_ticks  # noqa: F401
from views import BORDER_WIDTH, CANVAS_BACKDROP, CUT_COLOR, CUT_HANDLE_RADIUS, EDITOR_LINE_WIDTH_BOLD, PANEL_BORDER, SELECTION_BORDER, SELECTION_FILL, SURFACE, draw_bottom_shape_toolbar, draw_export_dialog, draw_left_toolbar, draw_marker_dropdown, draw_menu_bar, draw_panel, draw_panel_toggle, draw_scene, draw_shape_context_menu, draw_shortcuts_overlay, surface_to_pygame  # noqa: F401


def render_frame(ctx):
    from controllers.render.scene_state import render_scene
    from controllers.render.canvas_overlay import render_canvas_overlay
    from controllers.render.ui_frame import render_ui_frame
    render_scene(ctx)
    render_canvas_overlay(ctx)
    render_ui_frame(ctx)
    return 0
