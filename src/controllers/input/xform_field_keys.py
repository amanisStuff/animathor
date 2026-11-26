"""Transform numeric field input mode key handling."""

import pygame

from models.interaction import xform_step


def handle_xform_field_keys(ctx, event):
    if not (ctx.xform_field_focus is not None and ctx.tool_mode == "selection"
            and ctx.selection_submode == "transform" and ctx.selected_strokes):
        if ctx.xform_field_focus is not None:
            # Focus is stale (wrong mode/selection) — clear so keys aren't trapped.
            ctx._cancel_xform_field()
        return None

    if event.key == pygame.K_ESCAPE:
        ctx._cancel_xform_field()
    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        ctx._commit_xform_field()
    elif event.key == pygame.K_BACKSPACE:
        ctx.xform_field_buffer = str(ctx.xform_field_buffer)[:-1]
        ctx.state["xform_field_buffer"] = ctx.xform_field_buffer
    elif event.key in (pygame.K_UP, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT):
        # Up/Right increment, Down/Left decrement. Ctrl/Cmd gives a fine 0.1
        # step, Shift a coarse 10.0 step; fine wins if both are held.
        mods = getattr(event, "mod", None)
        if mods is None:
            mods = pygame.key.get_mods()
        ctx.step = xform_step(
            fine=bool(mods & (pygame.KMOD_CTRL | pygame.KMOD_META)),
            coarse=bool(mods & pygame.KMOD_SHIFT),
        )
        direction = 1 if event.key in (pygame.K_UP, pygame.K_RIGHT) else -1
        ctx._apply_xform_field(ctx.xform_field_focus, direction * ctx.step,
                               relative=True)
        ctx.xform_field_buffer = ""
        ctx.state["xform_field_buffer"] = ""
    elif event.unicode and (event.unicode.isdigit() or event.unicode in ".-"):
        if len(str(ctx.xform_field_buffer)) < 24:
            ctx.xform_field_buffer = str(ctx.xform_field_buffer) + event.unicode
            ctx.state["xform_field_buffer"] = ctx.xform_field_buffer
    return 'continue'
