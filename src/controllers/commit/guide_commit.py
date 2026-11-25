"""Guide drag commit.

The core is a typed contract over ``DragState``; ``commit_guide_drag`` is a
compat wrapper for the extracted ctx-based callers.
"""

import config as cfg
from models import remove_guide  # noqa: F401


def commit_guide_drag_typed(drag, pos, ruler_size, top_bar_h):
    """Remove a guide when released over a ruler; clear the drag state."""
    if drag.guide_drag is None:
        return None
    rs = int(ruler_size)
    on_ruler = (pos[1] <= top_bar_h + rs) or (pos[0] <= cfg.CANVAS_X + rs)
    if on_ruler:
        drag.guides = remove_guide(drag.guides, drag.guide_drag.get("index", 0))
    drag.guide_drag = None
    return 'continue'


def commit_guide_drag(ctx, event):
    """Compat wrapper: extract typed drag substate from dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None or app_state.drag.guide_drag is None:
        return None
    result = commit_guide_drag_typed(
        app_state.drag, event.pos,
        getattr(ctx, "RULER_SIZE", 18), getattr(ctx, "TOP_BAR_H", 34),
    )
    if result == 'continue':
        ctx.guide_drag = app_state.drag.guide_drag
        ctx.guides = app_state.drag.guides
    return result
