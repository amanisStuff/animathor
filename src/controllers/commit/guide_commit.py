"""Guide drag commit."""

import pygame
from models import *  # noqa: F401,F403
from views import *  # noqa: F401,F403
from controllers.coordinates import *  # noqa: F401,F403
import config as cfg


def commit_guide_drag(ctx, event):
    if ctx.guide_drag is None:
        return None
    ctx._rs = int(ctx.RULER_SIZE)
    _on_ruler = (event.pos[1] <= ctx.TOP_BAR_H + ctx._rs) or (event.pos[0] <= cfg.CANVAS_X + ctx._rs)
    if _on_ruler:
        ctx.guides = remove_guide(ctx.guides, ctx.guide_drag.get("index", 0))
    ctx.guide_drag = None
    return 'continue'
