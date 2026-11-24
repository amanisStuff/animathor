"""Controller: MOUSEBUTTONDOWN button 1 handler (extracted for SRP)."""
import copy, math, pygame
import config as cfg

# Panel click helpers

def _handle_panel_click(ctx, event):
    """Delegate to the ordered semantic panel domains (Phase 3)."""
    from controllers.panel.dispatch import handle_panel_click as _dispatch
    return _dispatch(ctx, event)




