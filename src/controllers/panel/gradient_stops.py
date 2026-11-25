"""Compat re-export: gradient domains live in gradient_* modules."""
from controllers.panel.gradient_tabs import *  # noqa: F401,F403
from controllers.panel.gradient_stops_edit import *  # noqa: F401,F403
from controllers.panel.gradient_color_picker import *  # noqa: F401,F403
from controllers.panel.gradient_tabs import handle_c_tabs_filltype  # noqa: F401
from controllers.panel.gradient_stops_edit import handle_c_stops  # noqa: F401
from controllers.panel.gradient_color_picker import handle_c_picker  # noqa: F401

# Semantic aliases
handle_fill_tabs_and_type = handle_c_tabs_filltype
handle_gradient_stops = handle_c_stops
handle_fill_picker = handle_c_picker

def gradient_stops_hit(tools, document, selection, ui, state, event, ctx, handlers):
    """Typed entry point for this panel domain.

    Handlers consume the live typed dispatch context supplied by the caller;
    domain boundaries are typed while handler bodies migrate incrementally.
    """
    for handler in handlers:
        if handler(ctx, event):
            return True
    return False
