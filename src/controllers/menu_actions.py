"""Menu action dispatch (compat layer).

Semantic command implementations live in controllers.commands.* modules.
This module preserves the legacy entry points used by existing callers/tests.
"""

from controllers.commands.file_commands import handle_file_command as _menu_file  # noqa: F401
from controllers.commands.edit_commands import handle_edit_command as _menu_edit  # noqa: F401
from controllers.commands.registry import dispatch_command


def run_menu_action(ctx, key):
    """Execute a menu command via the semantic command registry."""
    return dispatch_command(ctx, key)
