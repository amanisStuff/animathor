"""Compat re-export: transform motion lives in controllers/mouse_motion/transform_motion."""
from controllers.mouse_motion.transform_motion import mm_part3  # noqa: F401,F403
import controllers.mouse_motion.transform_motion as _mod  # noqa: F401
for _n in dir(_mod):
    if not _n.startswith("__"):
        globals()[_n] = getattr(_mod, _n)
