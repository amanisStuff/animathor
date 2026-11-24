"""Compat wrapper: semantic domain lives in views.panel_domain_color_detail."""
from views.panel_domain_color_detail import *  # noqa: F401,F403
import views.panel_domain_color_detail as _mod
for _k, _v in vars(_mod).items():
    if _k not in globals():
        globals()[_k] = _v
del _k, _v, _mod
