import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.app_state import ToolState, SelectionState, DocumentState, UiCacheState, DragState  # noqa: E402
from controllers.panel.tool_options import tool_options_typed  # noqa: E402


class _Btn:
    def hit(self, pos):
        return False


class TestToolCycling(unittest.TestCase):
    def _call(self, tools, state):
        return tool_options_typed(
            tools, SelectionState(), DocumentState(), DragState(), UiCacheState(), state,
            types.SimpleNamespace(pos=(0, 0)),
            None, None, None, None, None, None, None,
            _Btn(), None, 100, 5, [], globals(),
        )

    def test_prev_tool_button_cycles_draw_tool(self):
        tools = ToolState()
        tools.draw_tool = "pen"
        state = {"draw_tool_prev_rect": types.SimpleNamespace(collidepoint=lambda p: True)}
        result = self._call(tools, state)
        self.assertEqual(result, "continue")
        self.assertEqual(tools.draw_tool, "cutter")

    def test_next_tool_button_cycles_draw_tool(self):
        tools = ToolState()
        tools.draw_tool = "pen"
        state = {"draw_tool_next_rect": types.SimpleNamespace(collidepoint=lambda p: True)}
        result = self._call(tools, state)
        self.assertEqual(result, "continue")
        self.assertEqual(tools.draw_tool, "eraser")


if __name__ == "__main__":
    unittest.main()
