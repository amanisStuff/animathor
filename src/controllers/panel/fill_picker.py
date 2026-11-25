"""Compat re-export: fill picker domains live in fill_picker_* modules."""
from controllers.panel.fill_picker_options import *  # noqa: F401,F403
from controllers.panel.fill_picker_stops import *  # noqa: F401,F403
from controllers.panel.fill_picker_color import *  # noqa: F401,F403
from controllers.panel.fill_picker_options import handle_bc_part1  # noqa: F401
from controllers.panel.fill_picker_stops import handle_bc_part2  # noqa: F401
from controllers.panel.fill_picker_color import handle_bc_part3  # noqa: F401

def fill_picker_hit(tools, document, selection, ui, state, event, ctx, handlers):
    """Typed entry point for the fill/color picker domain.

    Handlers consume the live typed dispatch context supplied by the caller;
    this boundary keeps the domain contract typed while the handler bodies are
    migrated incrementally.
    """
    for handler in handlers:
        if handler(ctx, event):
            return True
    return False

# Semantic aliases
handle_color_targets = handle_bc_part1
handle_fill_stops = handle_bc_part2
handle_color_picker = handle_bc_part3
