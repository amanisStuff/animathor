"""Compat wrapper: semantic domain lives in controllers.panel.gradient_panel."""
import controllers.panel.gradient_panel as _new_mod  # noqa: F401
for _n in dir(_new_mod):
    if not _n.startswith("__"):
        globals()[_n] = getattr(_new_mod, _n)
