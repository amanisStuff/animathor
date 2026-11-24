"""Color/fill panel click dispatch."""
import copy, math, pygame
import config as cfg

# _handle_panel_click_b

def _handle_panel_click_b(ctx, event):
    # Semantic domain dispatch: wave/effect panel actions.
    from controllers.panel.effects_wave import (
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
