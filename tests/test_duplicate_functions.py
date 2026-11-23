"""Tests for the duplicate-function detection tool."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tools"))

import duplicate_functions as df  # noqa: E402


IDENTICAL_BODIES = '''\
def helper_one(x, y):
    """Add the two values together."""

    return x + y


def helper_two(x, y):
    # adds the two values together
    return x + y
'''


DIFFERENT_BODIES = '''\
def subtract(a, b):
    return a - b


def divide(a, b):
    if b == 0:
        return 0
    return a / b
'''


TRIVIAL_BODIES = '''\
def documented_only(value):
    """Just a docstring."""


def passthrough(value):
    pass
'''


class TestDuplicateFunctions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _write(self, name: str, source: str) -> Path:
        path = self.root / name
        path.write_text(source, encoding="utf-8")
        return path

    def _collect(self, sources: list[str]) -> list:
        for index, source in enumerate(sources):
            self._write(f"module_{index}.py", source)
        return df.collect_functions(self.root)

    # -- body comparison -------------------------------------------------

    def test_identical_bodies_after_normalization_match(self):
        functions = self._collect([IDENTICAL_BODIES])
        groups = df.find_duplicate_groups(functions)
        self.assertEqual(len(groups), 2)
        for group in groups:
            self.assertEqual(len(group.matches), 1)
            other, score = group.matches[0]
            self.assertEqual(score, 1.0)
            self.assertIsNot(group.function, other)

    def test_similar_bodies_match(self):
        source = (
            "def clamp(value, low, high):\n"
            "    if value < low:\n"
            "        return low\n"
            "    if value > high:\n"
            "        return high\n"
            "    return value\n"
        )
        functions = self._collect(
            [
                source,
                source.replace("def clamp", "def clamp_value"),
            ],
        )
        groups = df.find_duplicate_groups(functions)
        self.assertEqual(len(groups), 2)

    def test_different_bodies_do_not_match(self):
        functions = self._collect([DIFFERENT_BODIES])
        for function in functions:
            self.assertEqual(df.find_matches(function, functions, df.THRESHOLD), [])

    def test_trivial_bodies_are_not_comparable(self):
        functions = self._collect([TRIVIAL_BODIES])
        self.assertEqual(functions, [])

    # -- reporting ---------------------------------------------------------

    def test_report_lists_functions_with_duplicates(self):
        functions = self._collect([IDENTICAL_BODIES])
        groups = df.find_duplicate_groups(functions)
        self.assertTrue(len(groups) > 0)
        group = groups[0]
        self.assertIn("helper", group.function.qualname)
        self.assertGreater(group.matches[0][1], 0.5)

    # -- CLI ----------------------------------------------------------------

    def test_main_missing_file_returns_usage_error(self):
        self.assertEqual(df.main([str(self.root / "missing.py")]), 2)

    def test_main_clean_file_returns_zero(self):
        path = self._write("clean.py", "def add(a, b):\n    return a + b\n")
        self.assertEqual(df.main([str(path), "--root", str(self.root)]), 0)

    def test_main_duplicate_file_returns_one(self):
        path = self._write("duplicated.py", IDENTICAL_BODIES)
        self.assertEqual(df.main([str(path), "--root", str(self.root)]), 1)


if __name__ == "__main__":
    unittest.main()
