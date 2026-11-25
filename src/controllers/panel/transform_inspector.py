"""Compat re-export: transform domains live in transform_fields / align_distribute."""
from controllers.panel.transform_fields import *  # noqa: F401,F403
from controllers.panel.align_distribute import *  # noqa: F401,F403
from controllers.panel.transform_fields import _handle_panel_click_a_p2  # noqa: F401
from controllers.panel.align_distribute import _handle_panel_click_a_p3  # noqa: F401
import controllers.panel.transform_fields as _fields  # noqa: F401
import controllers.panel.align_distribute as _align  # noqa: F401

handle_transform_align = _fields._handle_panel_click_a_p2
handle_transform_nudge = _align._handle_panel_click_a_p3

def transform_inspector_hit(tools, document, selection, ui, state, event, ctx, handlers):
    """Typed entry point for this panel domain.

    Handlers consume the live typed dispatch context supplied by the caller;
    domain boundaries are typed while handler bodies migrate incrementally.
    """
    for handler in handlers:
        if handler(ctx, event):
            return True
    return False
