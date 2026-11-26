import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.app_state import ToolState, SelectionState, DocumentState, UiCacheState, DragState  # noqa: E402
from controllers.panel.tool_options import tool_options_typed  # noqa: E402


class TestSubmodeCycling(unittest.TestCase):
    def _btn(self):
        return types.SimpleNamespace(hit=lambda p: False)

    def test_nodes_mode_prev_button_cycles_submode(self):
        tools = ToolState()
        tools.tool_mode = "selection"
        sel = SelectionState()
        sel.selection_submode = "transform"
        ui = UiCacheState()
        state = {"nodes_mode_prev_rect": types.SimpleNamespace(collidepoint=lambda p: True)}
        result = tool_options_typed(
            tools, sel, DocumentState(), DragState(), ui, state,
            types.SimpleNamespace(pos=(0, 0)), None, None, None,
            None, None, None, None, self._btn(), None, 100, 5, [], globals(),
        )
        self.assertTrue(result)
        self.assertEqual(sel.selection_submode, "curve")

    def test_nodes_mode_next_button_cycles_submode(self):
        tools = ToolState()
        tools.tool_mode = "selection"
        sel = SelectionState()
        sel.selection_submode = "transform"
        ui = UiCacheState()
        state = {"nodes_mode_next_rect": types.SimpleNamespace(collidepoint=lambda p: True)}
        result = tool_options_typed(
            tools, sel, DocumentState(), DragState(), ui, state,
            types.SimpleNamespace(pos=(0, 0)), None, None, None,
            None, None, None, None, self._btn(), None, 100, 5, [], globals(),
        )
        self.assertTrue(result)
        self.assertEqual(sel.selection_submode, "nodes")


if __name__ == "__main__":
    unittest.main()
