"""Compat wrapper: semantic domain lives in controllers.panel.color_panel."""
import controllers.panel.color_panel as _new_mod  # noqa: F401
for _n in dir(_new_mod):
    if not _n.startswith("__"):
        globals()[_n] = getattr(_new_mod, _n)
