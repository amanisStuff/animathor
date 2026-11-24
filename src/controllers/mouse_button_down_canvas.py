"""Canvas click dispatch split semantically by tool/selection mode."""

from controllers.tools.draw_mode import handle_draw_mode
from controllers.tools.redraw_mode import handle_redraw_mode
from controllers.selection.eyedropper import handle_eyedropper
from controllers.selection.curve_mode import handle_curve_mode
from controllers.selection.transform_mode import handle_transform_mode
from controllers.selection.nodes_mode import handle_nodes_mode


def _handle_canvas_click(ctx, event):
    ctx.cpos = ctx.to_canvas(event.pos)
    # Semantic dispatch: draw mode -> redraw -> selection submodes.
    if ctx.tool_mode == "draw":
        return handle_draw_mode(ctx, event)

    if ctx.redrawing_curve is not None:
        return handle_redraw_mode(ctx, event)

    # Selection mode common setup
    ctx.selected_point = None
    ctx.transform_drag = None
    # mods/shift set by handlers as needed; preserve original behavior
    import pygame
    ctx.mods = pygame.key.get_mods()
    ctx.shift = bool(ctx.mods & pygame.KMOD_SHIFT)

    if handle_eyedropper(ctx, event) == 'handled' and ctx.eyedropper_pick is False:
        # Eyedropper consumed and finished (picked or applied).
        return None
    # Eyedropper handler always returns 'handled' when active, even on miss.
    # Original: if eyedropper_pick: ... (handled) elif curve...
    if ctx.eyedropper_pick:
        # It was active but missed - handler already ran and returned handled.
        return None

    if ctx.selection_submode == "curve":
        return handle_curve_mode(ctx, event)
    if ctx.selection_submode == "transform":
        return handle_transform_mode(ctx, event)
    return handle_nodes_mode(ctx, event)
