"""Keyboard dispatch split semantically by input mode.

The handler priority is intentional: modal/input-capture modes consume keys before
global shortcuts so tool shortcuts never fire while typing.
"""

from controllers.input.drag_field_keys import handle_drag_field_keys
from controllers.input.modal_keys import handle_modal_keys
from controllers.input.text_entry_keys import handle_text_entry_keys
from controllers.input.xform_field_keys import handle_xform_field_keys
from controllers.input.bezier_pen_keys import handle_bezier_pen_keys
from controllers.input.wave_keys import handle_wave_keys
from controllers.input.shortcut_keys import handle_global_shortcuts


# Semantic dispatch order. Each handler returns 'continue' when it consumed
# the event, or None to pass to the next mode.
_KEY_HANDLERS = (
    handle_drag_field_keys,
    handle_modal_keys,
    handle_text_entry_keys,
    handle_xform_field_keys,
    handle_bezier_pen_keys,
    handle_wave_keys,
    handle_global_shortcuts,
)


def handle_keydown(ctx, event=None):
    """Dispatch a KEYDOWN event to the first semantic handler that consumes it."""
    for handler in _KEY_HANDLERS:
        result = handler(ctx, event)
        if result == 'continue':
            return 'continue'
    return None
