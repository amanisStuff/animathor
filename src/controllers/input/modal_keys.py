"""Modal dismissal key handling (menu/help/export dialogs)."""

import pygame


def handle_modal_keys(ctx, event):
    if ctx.menu_open is not None and event.key == pygame.K_ESCAPE:
        ctx.menu_open = None
        return 'continue'
    if ctx.help_open:
        if event.key == pygame.K_ESCAPE:
            ctx.help_open = False
            ctx.menu_open = None
        return 'continue'
    if ctx.export_dialog_open:
        if event.key == pygame.K_ESCAPE:
            ctx.export_dialog_open = False
        return 'continue'
    return None
