"""Panel click helpers (split for SRP)."""
import copy, math, pygame
import config as cfg

# _handle_panel_click_b

def _handle_panel_click_b(ctx, event):
    # Semantic domain dispatch: wave/effect panel actions.
    from controllers.panel_actions.wave_effects import (
        handle_wave_effects_primary,
        handle_wave_effects_secondary,
        handle_wave_effects_tertiary,
    )
    for handler in (
        handle_wave_effects_primary,
        handle_wave_effects_secondary,
        handle_wave_effects_tertiary,
    ):
        if handler(ctx, event):
            return "handled"
    return None
