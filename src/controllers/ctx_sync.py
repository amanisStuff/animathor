"""Legacy ctx/frame sync helpers.

The hardcoded per-handler sync field lists were removed as part of the semantic
split migration. Handlers now auto-sync ctx/frame locals, and AppState owns the
primary synced slice. This module keeps only the frame-locals bridge helpers.
"""


def sync_attrs(target, source, fields):
    """Copy existing attributes from source to target for the given field names."""
    for k in fields:
        if hasattr(source, k):
            setattr(target, k, getattr(source, k))


def sync_to_frame_locals(frame, source, fields):
    """Sync fields from source into a caller frame's locals (CPython).

    This is a pragmatic bridge while migrating from ctx/locals state to typed
    AppState contracts.
    """
    updates = {}
    for k in fields:
        if hasattr(source, k):
            updates[k] = getattr(source, k)
    if not updates:
        return
    frame.f_locals.update(updates)
    try:
        import ctypes
        ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(0))
    except Exception:
        # Fallback: at least update f_locals (works in some contexts/debuggers).
        pass
