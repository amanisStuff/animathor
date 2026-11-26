"""Click handling for collapsible properties-panel sections."""

from __future__ import annotations

import pygame


def handle_section_click(ctx, event):
    """Toggle the section whose header was clicked; consume the click."""
    if getattr(event, "type", None) != pygame.MOUSEBUTTONDOWN:
        return None
    if getattr(event, "button", 1) != 1:
        return None
    state = getattr(ctx, "state", None) or {}
    rects = state.get("panel_section_rects") or {}
    pos = getattr(event, "pos", None)
    if pos is None:
        return None
    for key, rect in rects.items():
        if rect is not None and rect.collidepoint(pos):
            from views.panel_sections import toggle
            toggle(state, key)
            app_state = getattr(ctx, "_app_state", None)
            if app_state is not None and hasattr(app_state, "ui"):
                app_state.ui.panel_sections = state["panel_sections"]
            # Keep the read mirror in sync for legacy ctx handlers.
            if hasattr(ctx, "panel_sections"):
                ctx.panel_sections = state["panel_sections"]
            return 'continue'
    return None
