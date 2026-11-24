"""Compat wrapper: semantic domain lives in views.panel_domain_selection."""
from views.panel_domain_selection import *  # noqa: F401,F403
import views.panel_domain_selection as _mod
for _k, _v in vars(_mod).items():
    if _k not in globals():
        globals()[_k] = _v
del _k, _v, _mod
