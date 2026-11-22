#!/usr/bin/env python3
"""Score every Python file in the repository for complexity on a 0-10 scale.

Usage (from the repo root):
    python tools/complexity_score.py
    python tools/complexity_score.py --root src
    python tools/complexity_score.py --threshold 8

The score is a dependency-free heuristic built from five signals:

    size          non-blank, non-comment source lines
    branches      decision points (if/for/while/except/and/or/...)
    nesting       deepest control-flow nesting
    function size longest function body
    function cost most decision points in a single function

Each signal is normalised to 0-10 and combined with fixed weights (see the
constants below). The result is rounded to the nearest integer. A file with no
code scores 0; a very large, branch-heavy file scores 10.

Files that cannot be parsed (for example, intentionally broken snapshots) are
still scored from a line-based fallback and marked with "!" in the report.
"""

import argparse
import ast
import math
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Scoring configuration. Adjust these if the repo grows or the scale feels off.
# ---------------------------------------------------------------------------

SIZE_REFERENCE = 4_000          # SLOC that maps to the top of the size scale
BRANCH_REFERENCE = 600          # decision points that map to the top
NESTING_REFERENCE = 6           # nesting depth that maps to the top
FUNCTION_REFERENCE = 250        # longest-function SLOC that maps to the top
FUNCTION_BRANCH_REFERENCE = 50  # decisions in one function that map to the top

WEIGHTS = {
    "size": 0.30,
    "branches": 0.30,
    "nesting": 0.15,
    "function_size": 0.15,
    "function_branches": 0.10,
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv",
}

TRY_NODES = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass
class FileComplexity:
    path: Path
    score: int
    sloc: int
    branches: int
    max_depth: int
    functions: int
    longest_function: int
    max_function_branches: int
    error: str | None = None


# ---------------------------------------------------------------------------
# Reading and parsing
# ---------------------------------------------------------------------------


def read_source(path: Path) -> str:
    """Read a Python source file, tolerating BOMs and non-UTF-8 encodings."""
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def code_line_numbers(source: str) -> set[int]:
    """Return 1-based line numbers that contain code (not blank/comment-only)."""
    result = set()
    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            result.add(number)
    return result


def count_sloc(source: str) -> int:
    return len(code_line_numbers(source))


def _decision_weight(node: ast.AST) -> int:
    if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp, ast.Assert)):
        return 1
    if isinstance(node, ast.BoolOp):
        return max(0, len(node.values) - 1)
    if isinstance(node, ast.Match):
        return len(node.cases)
    if isinstance(node, ast.comprehension):
        return 1 + len(node.ifs)
    if isinstance(node, ast.match_case) and node.guard is not None:
        return 1
    return 0


def count_branches(tree: ast.AST) -> int:
    return sum(_decision_weight(node) for node in ast.walk(tree))


def count_function_branches(function: ast.AST) -> int:
    """Count decisions inside a function without descending into nested defs."""
    total = 0
    stack = list(ast.iter_child_nodes(function))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        total += _decision_weight(node)
        stack.extend(ast.iter_child_nodes(node))
    return total


def max_nesting(node: ast.AST, depth: int = 0) -> int:
    """Deepest control-flow nesting, treating an elif chain as one level.

    Function and class bodies do not count as nesting; only the control-flow
    statements inside them do.
    """
    best = depth

    def visit_block(statements, block_depth):
        nonlocal best
        for statement in statements:
            best = max(best, max_nesting(statement, block_depth))

    if isinstance(node, ast.If):
        visit_block(node.body, depth + 1)
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            # "elif" is an If node nested in orelse but aligns with the parent.
            best = max(best, max_nesting(node.orelse[0], depth))
        else:
            visit_block(node.orelse, depth + 1)
    elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        visit_block(node.body, depth + 1)
        visit_block(node.orelse, depth + 1)
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        visit_block(node.body, depth + 1)
    elif isinstance(node, TRY_NODES):
        visit_block(node.body, depth + 1)
        for handler in node.handlers:
            visit_block(handler.body, depth + 1)
        visit_block(node.orelse, depth + 1)
        visit_block(node.finalbody, depth + 1)
    elif isinstance(node, ast.Match):
        for case in node.cases:
            visit_block(case.body, depth + 1)
    else:
        for child in ast.iter_child_nodes(node):
            best = max(best, max_nesting(child, depth))
    return best


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _log_scale(value: int, reference: int) -> float:
    if value <= 0:
        return 0.0
    return min(10.0, 10.0 * math.log2(1 + value) / math.log2(1 + reference))


def score_metrics(
    sloc: int,
    branches: int,
    depth: int,
    longest_function: int,
    max_function_branches: int,
) -> int:
    components = {
        "size": _log_scale(sloc, SIZE_REFERENCE),
        "branches": _log_scale(branches, BRANCH_REFERENCE),
        "nesting": min(10.0, depth / NESTING_REFERENCE * 10.0),
        "function_size": min(10.0, longest_function / FUNCTION_REFERENCE * 10.0),
        "function_branches": min(10.0, max_function_branches / FUNCTION_BRANCH_REFERENCE * 10.0),
    }
    total = sum(components[name] * weight for name, weight in WEIGHTS.items())
    return max(0, min(10, round(total)))


def _fallback_metrics(source: str) -> tuple[int, int, int, int, int]:
    """Estimate branches/depth/functions for files that do not parse."""
    lines = source.splitlines()
    branches = 0
    depth = 0
    functions = 0

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())
        if re.match(r"^(?:async\s+)?def\s+", stripped):
            functions += 1
        keyword_hits = len(re.findall(r"\b(?:if|elif|for|while|except|assert)\b", stripped))
        boolean_hits = len(re.findall(r"\b(?:and|or)\b", stripped))
        branches += keyword_hits + boolean_hits
        if keyword_hits:
            depth = max(depth, indent // 4)

    # Longest-function metrics are not recoverable from broken syntax.
    return branches, depth, functions, 0, 0


def analyze_file(path: Path) -> FileComplexity:
    source = read_source(path)
    sloc = count_sloc(source)

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        branches, depth, functions, longest, max_branches = _fallback_metrics(source)
        return FileComplexity(
            path=path,
            score=score_metrics(sloc, branches, depth, longest, max_branches),
            sloc=sloc,
            branches=branches,
            max_depth=depth,
            functions=functions,
            longest_function=longest,
            max_function_branches=max_branches,
            error=f"SyntaxError: {exc.msg} (line {exc.lineno})",
        )

    code_lines = code_line_numbers(source)
    functions = [node for node in ast.walk(tree) if isinstance(node, FUNCTION_NODES)]

    longest_function = 0
    max_function_branches = 0
    for function in functions:
        start = function.lineno
        end = getattr(function, "end_lineno", start)
        length = sum(1 for line in range(start, end + 1) if line in code_lines)
        longest_function = max(longest_function, length)
        max_function_branches = max(max_function_branches, count_function_branches(function))

    branches = count_branches(tree)
    depth = max_nesting(tree)
    return FileComplexity(
        path=path,
        score=score_metrics(sloc, branches, depth, longest_function, max_function_branches),
        sloc=sloc,
        branches=branches,
        max_depth=depth,
        functions=len(functions),
        longest_function=longest_function,
        max_function_branches=max_function_branches,
    )


# ---------------------------------------------------------------------------
# Discovery and reporting
# ---------------------------------------------------------------------------


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def print_report(shown: list[FileComplexity], root: Path, all_results: list[FileComplexity]) -> None:
    if not all_results:
        print(f"No Python files found under {root}")
        return

    name_width = max(len(display_path(item.path, root)) for item in shown)
    header = (
        f"{'Score':>5}  {'SLOC':>5}  {'Branch':>6}  {'Depth':>5}  "
        f"{'Fns':>4}  {'MaxFn':>5}  {'File':<{name_width}}"
    )
    print(header)
    print("-" * len(header))

    for item in shown:
        marker = "!" if item.error else " "
        name = display_path(item.path, root)
        print(
            f"{item.score:>5}  {item.sloc:>5}  {item.branches:>6}  {item.max_depth:>5}  "
            f"{item.functions:>4}  {item.longest_function:>5}  {name:<{name_width}}{marker}"
        )

    scores = [item.score for item in all_results]
    print()
    if len(shown) != len(all_results):
        print(f"Showing {len(shown)} of {len(all_results)} Python files (highest scores first).")
    print(
        f"Scanned {len(all_results)} Python files: "
        f"mean {statistics.mean(scores):.1f}, median {statistics.median(scores):.1f}, "
        f"max {max(scores)}."
    )
    print("Scale: 0 = trivial, 10 = very complex. '!' marks files that did not parse.")
    for item in all_results:
        if item.error:
            print(f"  ! {display_path(item.path, root)}: {item.error}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Score every Python file in the repo for complexity (0-10).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=repo_root,
        help=f"directory to scan (default: repo root, {repo_root})",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        metavar="N",
        help="exit with status 1 if any file scores above N (useful in CI)",
    )
    parser.add_argument(
        "--top",
        type=int,
        metavar="N",
        help="only show the N highest-scoring files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.resolve()

    results = [analyze_file(path) for path in iter_python_files(root)]
    results.sort(key=lambda item: (item.score, item.sloc), reverse=True)

    shown = results
    if args.top is not None:
        if args.top < 1:
            print("--top must be at least 1", file=sys.stderr)
            return 2
        shown = results[: args.top]

    print_report(shown, root, results)

    if args.threshold is not None:
        over = [item for item in results if item.score > args.threshold]
        if over:
            print(
                f"\nFAIL: {len(over)} file(s) score above {args.threshold}.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
