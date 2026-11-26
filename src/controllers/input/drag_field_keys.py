"""Keyboard mode for double-click numeric field editing."""

from controllers import numeric_field_edit as _edit


def handle_drag_field_keys(ctx, event):
    """Return 'continue' when a draggable field is being edited."""
    return _edit.handle_keys(ctx, event)
