"""Render semantic domain: rulers, guides, cutter and marquee overlays."""
"""Render frame (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from config import RULER_BG_RGB, RULER_SIZE, RULER_TEXT_RGB, RULER_TICK_RGB  # noqa: F401
from models import combined_obb, grid_positions, normalize_rect, ruler_ticks  # noqa: F401
from views import BORDER_WIDTH, CANVAS_BACKDROP, CUT_COLOR, CUT_HANDLE_RADIUS, EDITOR_LINE_WIDTH_BOLD, PANEL_BORDER, SELECTION_BORDER, SELECTION_FILL, SURFACE, draw_bottom_shape_toolbar, draw_export_dialog, draw_left_toolbar, draw_marker_dropdown, draw_menu_bar, draw_panel, draw_panel_toggle, draw_scene, draw_shape_context_menu, draw_shortcuts_overlay, surface_to_pygame  # noqa: F401


def render_canvas_overlay(ctx):
    # Rulers + guides overlay (view-only).
    if getattr(cfg, "SHOW_RULERS", False):
        _rs = int(RULER_SIZE)
        _vh = cfg.canvas_viewport_height()
        _top = pygame.Rect(cfg.CANVAS_X, ctx.TOP_BAR_H, cfg.CANVAS_W, _rs)
        _left = pygame.Rect(cfg.CANVAS_X, ctx.TOP_BAR_H, _rs, _vh)
        pygame.draw.rect(ctx.screen, RULER_BG_RGB, _top)
        pygame.draw.rect(ctx.screen, RULER_BG_RGB, _left)
        pygame.draw.line(ctx.screen, PANEL_BORDER, (_top.x, _top.bottom - 1),
                         (_top.right, _top.bottom - 1), BORDER_WIDTH)
        pygame.draw.line(ctx.screen, PANEL_BORDER, (_left.right - 1, _left.y),
                         (_left.right - 1, _left.bottom), BORDER_WIDTH)
        _z = float(getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0)
        _px = float(getattr(cfg, "VIEW_PAN_X", 0.0))
        _py = float(getattr(cfg, "VIEW_PAN_Y", 0.0))
        _wx0 = (0.0 - _px) / _z
        _wx1 = (float(cfg.CANVAS_W) - _px) / _z
        _wy0 = (0.0 - _py) / _z
        _wy1 = (float(_vh) - _py) / _z
        _step_x = ruler_ticks(_wx0, _wx1, 10.0, min_pixels=64.0, zoom=_z)
        _step_y = ruler_ticks(_wy0, _wy1, 10.0, min_pixels=48.0, zoom=_z)
        for _x in grid_positions(_wx0, _wx1, _step_x):
            _sx = int(_x * _z + _px + cfg.CANVAS_X)
            if _sx <= _top.x or _sx >= _top.right:
                continue
            pygame.draw.line(ctx.screen, RULER_TICK_RGB, (_sx, _top.bottom - 5),
                             (_sx, _top.bottom - 1), BORDER_WIDTH)
            _lbl = ctx.ruler_font.render(str(int(round(_x))), True, RULER_TEXT_RGB)
            ctx.screen.blit(_lbl, (_sx + 2, _top.y + 1))
        for _y in grid_positions(_wy0, _wy1, _step_y):
            _sy = int(_y * _z + _py + ctx.TOP_BAR_H)
            if _sy <= _left.y or _sy >= _left.bottom:
                continue
            pygame.draw.line(ctx.screen, RULER_TICK_RGB, (_left.right - 5, _sy),
                             (_left.right - 1, _sy), BORDER_WIDTH)
            _lbl = ctx.ruler_font.render(str(int(round(_y))), True, RULER_TEXT_RGB)
            _lbl = pygame.transform.rotate(_lbl, 90)
            ctx.screen.blit(_lbl, (_left.x + 1, _sy + 2))

    # Cutter swipe preview (razor line across the canvas).
    if ctx.cutting and len(ctx.cut_points) >= 2:
        ctx.pts = [(int(ctx.to_screen(ctx.p)[0]), int(ctx.to_screen(ctx.p)[1])) for ctx.p in ctx.cut_points]
        pygame.draw.lines(ctx.screen, CUT_COLOR, False, ctx.pts, int(EDITOR_LINE_WIDTH_BOLD))
        pygame.draw.circle(ctx.screen, SURFACE, ctx.pts[0], CUT_HANDLE_RADIUS)
        pygame.draw.circle(ctx.screen, CUT_COLOR, ctx.pts[0], CUT_HANDLE_RADIUS, BORDER_WIDTH)

    # marquee selection overlay
    if ctx.marquee_select is not None and ctx.tool_mode == "selection":
        ctx.r = normalize_rect(ctx.marquee_select["start"], ctx.marquee_select.get("current", ctx.marquee_select["start"]))
        rx1, ry1, rx2, ry2 = ctx.r
        ctx.s1 = ctx.to_screen((rx1, ry1)); s2 = ctx.to_screen((rx2, ry2))
        ctx.rect = pygame.Rect(int(min(ctx.s1[0],s2[0])), int(min(ctx.s1[1],s2[1])), int(abs(s2[0]-ctx.s1[0])), int(abs(s2[1]-ctx.s1[1])))
        if ctx.rect.w > 0 and ctx.rect.h > 0:
            overlay = pygame.Surface((ctx.rect.w, ctx.rect.h), pygame.SRCALPHA)
            overlay.fill(SELECTION_FILL)
            ctx.screen.blit(overlay, ctx.rect.topleft)
            pygame.draw.rect(ctx.screen, SELECTION_BORDER, ctx.rect, BORDER_WIDTH)

