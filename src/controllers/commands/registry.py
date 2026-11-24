"""Simple command registry.

Commands are semantic actions invoked by menus, shortcuts, or UI.
Handlers take (ctx, key) and return True if handled.
"""

from __future__ import annotations


class CommandRegistry:
    def __init__(self):
        self._handlers = []

    def register(self, handler):
        self._handlers.append(handler)
        return handler

    def dispatch(self, ctx, key):
        for handler in self._handlers:
            if handler(ctx, key):
                return True
        return False


def build_default_registry():
    from controllers.commands.file_commands import handle_file_command
    from controllers.commands.edit_commands import handle_edit_command
    from controllers.menu_actions_view import _menu_view, _menu_tools

    reg = CommandRegistry()
    reg.register(handle_file_command)
    reg.register(handle_edit_command)
    reg.register(_menu_view)
    reg.register(_menu_tools)
    return reg


DEFAULT_REGISTRY = None


def get_default_registry():
    global DEFAULT_REGISTRY
    if DEFAULT_REGISTRY is None:
        DEFAULT_REGISTRY = build_default_registry()
    return DEFAULT_REGISTRY


def dispatch_command(ctx, key):
    return get_default_registry().dispatch(ctx, key)
