import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from controllers.app_state import ToolState  # noqa: E402
from controllers.bucket_controller import pick, set_color  # noqa: E402


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _hsv(h, s, v):
    return (h / 360.0, s, v, 1.0)


def _rgb(*c):
    return (c[0] * 360.0, c[1], c[2])


class _Rect:
    x, y, w, h = 10, 20, 100, 50


class TestTypedBucketController(unittest.TestCase):
    """Phase 1: bucket helpers operate on typed state, no ctx bag."""

    def test_pick_updates_typed_tools_and_state(self):
        tools = ToolState()
        state = {}
        pick(tools, _Rect(), (59.5, 20), "sv", state, _clamp, _hsv)
        self.assertAlmostEqual(tools.bucket_picker_s, 0.5)
        self.assertEqual(tools.bucket_picker_v, 1.0)
        self.assertEqual(state["bucket_picker_drag"], "sv")
        self.assertEqual(state["bucket_fill_color"], tools.bucket_fill_color)

    def test_set_color_updates_typed_tools(self):
        tools = ToolState()
        state = {}
        set_color(tools, (0.5, 0.25, 0.75), state, _rgb)
        self.assertEqual(tools.bucket_fill_color, (0.5, 0.25, 0.75))
        self.assertEqual(state["bucket_fill_color"], (0.5, 0.25, 0.75))


if __name__ == "__main__":
    unittest.main()
