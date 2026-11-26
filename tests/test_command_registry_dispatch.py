import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.commands.context import CommandContext  # noqa: E402
from controllers.commands.registry import dispatch_command  # noqa: E402
from controllers.commands import ids as CMD  # noqa: E402


class TestCommandRegistryDispatch(unittest.TestCase):
    def _ctx(self, **overrides):
        ctx = CommandContext(
            selected_strokes=set(),
            selected_curves=set(),
            current_points=[],
            state={},
            _bezier_pen_commit_or_cancel=lambda: None,
        )
        for k, v in overrides.items():
            setattr(ctx, k, v)
        return ctx

    def test_tool_workspace_help_and_cycle_commands_dispatch_and_mutate_state(self):
        cases = [
            (CMD.WORKSPACE, {"workspace": "draw", "state": {"workspace": "draw"}}, "workspace", "library"),
            (CMD.TOOL_SELECT, {"tool_mode": "draw"}, "tool_mode", "selection"),
            (CMD.TOOL_PEN, {"tool_mode": "selection", "draw_tool": "eraser"}, "tool_mode", "draw"),
            (CMD.SHORTCUTS, {"help_open": False}, "help_open", True),
            (CMD.CYCLE_SUBMODE, {"selection_submode": "transform"}, "selection_submode", "nodes"),
        ]
        for key, overrides, attr, expected in cases:
            with self.subTest(key=key):
                ctx = self._ctx(**overrides)
                handled = dispatch_command(ctx, key)
                self.assertTrue(handled, f"{key} should be handled")
                self.assertEqual(getattr(ctx, attr), expected)

        # TOOL_PEN also sets draw tool
        ctx = self._ctx(tool_mode="selection", draw_tool="eraser")
        self.assertTrue(dispatch_command(ctx, CMD.TOOL_PEN))
        self.assertEqual(ctx.draw_tool, "pen")

    def test_unknown_command_returns_false_and_does_not_mutate(self):
        ctx = self._ctx(workspace="draw", tool_mode="draw", help_open=False)
        handled = dispatch_command(ctx, "totally_unknown_command")
        self.assertFalse(handled)
        self.assertEqual(ctx.workspace, "draw")
        self.assertEqual(ctx.tool_mode, "draw")
        self.assertFalse(ctx.help_open)


if __name__ == "__main__":
    unittest.main()
