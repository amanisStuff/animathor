"""Compatibility shim: load the real app module from src/."""
import importlib.util
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Avoid self-import: load src/app.py under this module name.
_spec = importlib.util.spec_from_file_location(__name__, os.path.join(_SRC, "app.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules[__name__] = _mod
_spec.loader.exec_module(_mod)

if __name__ == "__main__":
    _mod.main()
