"""Controller: menu action dispatch wrapper (extracted from app_controller for SRP)."""

import types


_MENU_CALLBACK_FIELDS = {
    '_bezier_pen_cancel', '_bezier_pen_commit_or_cancel', '_capture_shape_state', '_copy_stroke',
    '_delete_shape_state', '_insert_shape_state', 'assign_group', 'cfg', 'clear_group', 'combined_bbox',
    'copy', 'do_redo', 'do_undo', 'import_svg', 'load_document_with_meta', 'new_group_id',
    'pick_import_svg_path', 'pick_open_document_path', 'pick_save_document_path', 'push_undo', 'relayout',
    'save_document', 'state', 'strokes', 'translate_stroke',
}


def run_menu_action(key, s):
    """Dispatch a menu action with automatic state sync.

    Syncs all non-callable state fields from s into ctx, runs the action, then
    syncs all non-callback fields back. This removes hardcoded sync field lists.
    """
    ctx = types.SimpleNamespace(**s.__dict__)
    # Ensure callbacks are present even if not in s.__dict__
    for name in _MENU_CALLBACK_FIELDS:
        if not hasattr(ctx, name) and hasattr(s, name):
            setattr(ctx, name, getattr(s, name))

    from controllers.menu_actions import run_menu_action as _rma
    result = _rma(ctx, key)

    for k, v in ctx.__dict__.items():
        if k in _MENU_CALLBACK_FIELDS:
            continue
        setattr(s, k, v)
    return result
