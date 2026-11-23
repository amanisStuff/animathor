#!/usr/bin/env python3
"""Find functions whose body duplicates (or nearly duplicates) another function.

Usage (from the repo root):
    python tools/duplicate_functions.py path/to/file.py
    python tools/duplicate_functions.py path/to/file.py --root src
    python tools/duplicate_functions.py --all --threshold 0.9

The tool takes a file and looks for other functions in the scanned codebase
that share the same (or a very similar) body. It is meant to catch copy-pasted
helpers and re-implementations of the same logic.

How it compares: the function body is reduced to a canonical list of unparsed
statements with docstrings and pass-only filler removed, so comments, docstrings
and formatting differences do not hide real duplicates. The statement lists are
compared with difflib's SequenceMatcher; pairs scoring at or above the threshold
(default 0.9, i.e. 90% similar) are reported.

When a file is given, only the functions that file defines are reported. With
`--all` the tool scans every Python file under --root and reports every
function that has a duplicate body.

Exit codes: 0 = no duplicates found, 1 = duplicates found, 2 = bad usage.
"""

import argparse
import ast
import difflib
import sys
from dataclasses import dataclass, field
from pathlib import Path

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

THRESHOLD = 0.9

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


@dataclass
class FunctionInfo:
    path: Path
    name: str
    qualname: str
    lineno: int
    end_lineno: int
    statements: list[str] = field(default_factory=list)


@dataclass
class DuplicateGroup:
    function: FunctionInfo
    matches: list[tuple[FunctionInfo, float]]


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


def _is_docstring(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(getattr(node, "value", None), ast.Constant)
        and isinstance(node.value.value, str)
    )


def normalized_statements(function: ast.AST) -> list[str] | None:
    """Return the function's body as comparable statements.

    Docstrings and pass-only filler are dropped. Returns None for trivial
    bodies (docstring-only or pass-only) that cannot be meaningfully compared.
    """
    body = [stmt for stmt in function.body if not isinstance(stmt, ast.Pass)]
    if body and _is_docstring(body[0]):
        body = body[1:]
    if not body:
        return None
    statements: list[str] = []
    for stmt in body:
        text = ast.unparse(stmt).strip()
        if text and text != "...":
            statements.append(text)
    return statements or None


def _walk_functions(node: ast.AST, scope: str = ""):
    """Yield (function_node, qualname) pairs, descending into nested defs."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNCTION_NODES):
            qualname = f"{scope}.{child.name}" if scope else child.name
            yield child, qualname
            yield from _walk_functions(child, qualname)
        elif isinstance(child, ast.ClassDef):
            class_scope = f"{scope}.{child.name}" if scope else child.name
            yield from _walk_functions(child, class_scope)
        else:
            yield from _walk_functions(child, scope)


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def collect_functions(root: Path) -> list[FunctionInfo]:
    """Collect every comparable function found under root."""
    functions: list[FunctionInfo] = []
    for path in iter_python_files(root):
        source = read_source(path)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node, qualname in _walk_functions(tree):
            statements = normalized_statements(node)
            if statements is None:
                continue
            functions.append(
                FunctionInfo(
                    path=path,
                    name=node.name,
                    qualname=qualname,
                    lineno=node.lineno,
                    end_lineno=getattr(node, "end_lineno", node.lineno),
                    statements=statements,
                ),
            )
    return functions


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def similarity(left: list[str], right: list[str]) -> float:
    """Similarity score between two normalized bodies, 0.0 - 1.0."""
    return difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()


def find_matches(
    function: FunctionInfo,
    functions: list[FunctionInfo],
    threshold: float,
) -> list[tuple[FunctionInfo, float]]:
    """Return (other_function, score) pairs whose body matches this one."""
    matches: list[tuple[FunctionInfo, float]] = []
    for other in functions:
        if other.path == function.path and other.qualname == function.qualname:
            continue
        score = similarity(function.statements, other.statements)
        if score >= threshold:
            matches.append((other, score))
    matches.sort(key=lambda item: (str(item[0].path), item[0].qualname))
    return matches


def find_duplicate_groups(
    functions: list[FunctionInfo],
    threshold: float = THRESHOLD,
) -> list[DuplicateGroup]:
    """Group every function that has at least one duplicate body."""
    groups: list[DuplicateGroup] = []
    for function in sorted(functions, key=lambda item: (str(item.path), item.qualname)):
        matches = find_matches(function, functions, threshold)
        if matches:
            groups.append(DuplicateGroup(function=function, matches=matches))
    return groups


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def print_report(
    groups: list[DuplicateGroup],
    checked: int,
    target: Path | None,
    root: Path,
) -> None:
    if not groups:
        if target is not None:
            print(f"No duplicate function bodies found in {display_path(target, root)}.")
        else:
            print("No duplicate function bodies found.")
        print(f"Checked {checked} comparable function(s).")
        return

    scope = f"in {display_path(target, root)}" if target is not None else f"under {display_path(root, root)}"
    print(f"Duplicate function bodies {scope}:")
    for group in groups:
        function = group.function
        header = f"{display_path(function.path, root)}::{function.qualname}  (line {function.lineno})"
        print(f"  {header}")
        for other, score in group.matches:
            print(
                f"    -> {display_path(other.path, root)}::{other.qualname}  "
                f"(line {other.lineno})  similar body ({score:.0%})"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Find functions with duplicate or similar bodies.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="file to check for duplicate function bodies (default: scan the whole repo)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="scan every Python file under --root and report all duplicate bodies",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=repo_root,
        help=f"directory to scan (default: repo root, {repo_root})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=THRESHOLD,
        metavar="0.9",
        help="similarity ratio at or above which bodies count as duplicates (default: 0.9)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.resolve()

    target: Path | None = None
    if not args.all:
        if args.path is None:
            print("Nothing to check. Pass a file path or use --all.", file=sys.stderr)
            return 2
        target = args.path.expanduser().resolve()
        if not target.exists():
            print(f"File not found: {target}", file=sys.stderr)
            return 2
        if not target.is_file():
            print(f"Expected a file, got a directory: {target}", file=sys.stderr)
            return 2

    functions = collect_functions(root)

    groups: list[DuplicateGroup] = []
    if args.all:
        groups = find_duplicate_groups(functions, args.threshold)
        checked = len(functions)
        if not functions:
            print(f"No Python functions found under {root}")
            return 0
    else:
        target_functions = [item for item in functions if item.path == target]
        for function in sorted(target_functions, key=lambda item: (str(item.path), item.qualname)):
            matches = find_matches(function, functions, args.threshold)
            if matches:
                groups.append(DuplicateGroup(function=function, matches=matches))
        checked = len(target_functions)

    print_report(groups, checked, target, root)

    if groups:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
