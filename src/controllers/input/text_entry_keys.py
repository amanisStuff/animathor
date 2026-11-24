"""Text-entry input mode key handling."""

import pygame


def handle_text_entry_keys(ctx, event):
    if ctx.text_entry is None:
        return None
    # Text insertion mode: capture keystrokes into the buffer so
    # single-letter tool shortcuts never fire while typing.
    if event.key == pygame.K_ESCAPE:
        ctx.text_entry = None
    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        ctx.commit_text_entry()
    elif event.key == pygame.K_BACKSPACE:
        ctx.text_entry["text"] = ctx.text_entry["text"][:-1]
    elif event.key in (pygame.K_UP, pygame.K_DOWN) and \
            bool(pygame.key.get_mods() & pygame.KMOD_CTRL):
        ctx.text_entry["size"] = max(4.0, min(400.0,
            ctx.text_entry["size"] + (2.0 if event.key == pygame.K_UP else -2.0)))
    elif event.unicode and event.unicode.isprintable():
        if len(ctx.text_entry["text"]) < 500:
            ctx.text_entry["text"] += event.unicode
    return 'continue'
