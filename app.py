"""Compatibility shim: load the real app module from src/."""
import importlib.util
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Load the real app from src/ without triggering its __main__ guard here.
_spec = importlib.util.spec_from_file_location("app", os.path.join(_SRC, "app.py"))
_mod = importlib.util.module_from_spec(_spec)
# Register as "app" (and as the running module name) so imports resolve consistently.
sys.modules["app"] = _mod
if __name__ != "app":
    sys.modules[__name__] = _mod
_spec.loader.exec_module(_mod)

if __name__ == "__main__":
    _mod.main()
