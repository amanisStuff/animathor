"""Typed dispatch context for extracted frame handlers.

Unlike a plain ``SimpleNamespace`` snapshot, writing a typed-state field on this
context immediately updates the owning ``AppState`` substate, so handlers mutate
typed state at the point of change rather than through a post-hoc sync. Runtime
fields (services, view state) remain ordinary attributes for compatibility with
the extracted ctx-based handler bodies.
"""

from __future__ import annotations


class DispatchContext:
    def __init__(self, app_state, fields: dict):
        object.__setattr__(self, "_app_state", app_state)
        self.__dict__.update(fields)

    @staticmethod
    def _owner(app_state, name):
        if app_state is None:
            return None
        for substate in app_state._substates(app_state):
            if name in substate.__dataclass_fields__:
                return substate
        return None

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        owner = self._owner(object.__getattribute__(self, "_app_state"), name)
        if owner is not None:
            setattr(owner, name, value)
