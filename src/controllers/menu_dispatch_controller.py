"""Controller: menu action dispatch wrapper (extracted from app_controller for SRP)."""

import types


def run_menu_action(key, s, state_fields=None):
    """Dispatch a menu action with automatic state sync.

    ``state_fields`` is the authoritative set of typed state field names to sync
    back into ``s`` (the caller supplies ``AppState._SYNC_FIELDS``). Callbacks and
    service objects are never copied back, eliminating the old callback blacklist.
    """
    ctx = types.SimpleNamespace(**s.__dict__)

    from controllers.menu_actions import run_menu_action as _rma
    result = _rma(ctx, key)

    for k, v in ctx.__dict__.items():
        if state_fields is not None:
            if k not in state_fields:
                continue
        elif callable(v) or isinstance(v, types.ModuleType):
            continue
        setattr(s, k, v)
    return result
