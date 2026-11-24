"""Compat wrapper: semantic domain lives in panel_actions.color_fill_b."""
from controllers.panel_actions.color_fill_b import *  # noqa: F401,F403
import controllers.panel_actions.color_fill_b as _mod
for _k, _v in vars(_mod).items():
    if _k not in globals():
        globals()[_k] = _v
del _k, _v, _mod
