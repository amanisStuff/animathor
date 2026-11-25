"""Compat re-export: mouse-down handler domains live in mouse_button_down_* modules."""
from controllers.mouse_button_down_menus import *  # noqa: F401,F403
from controllers.mouse_button_down_toolbar import *  # noqa: F401,F403
from controllers.mouse_button_down_menus import _handle_pre_menu, _handle_menus  # noqa: F401
from controllers.mouse_button_down_toolbar import _handle_toolbar  # noqa: F401
from controllers.mouse_button_down_panel import _handle_panel_click  # noqa: F401
from controllers.mouse_button_down_canvas import _handle_canvas_click  # noqa: F401

def handle_mousebuttondown1(ctx, event):
    r = _handle_pre_menu(ctx, event)
    if r == 'continue': return 'continue'
    r = _handle_menus(ctx, event)
    if r == 'continue': return 'continue'
    r = _handle_toolbar(ctx, event)
    if r == 'continue': return 'continue'
    if event.pos[0] >= cfg.PANEL_X:
        _r = _handle_panel_click(ctx, event)
        if _r == 'continue': return 'continue'
    elif ctx.in_canvas(event.pos):
        _r = _handle_canvas_click(ctx, event)
        if _r == 'continue': return 'continue'
    return None
