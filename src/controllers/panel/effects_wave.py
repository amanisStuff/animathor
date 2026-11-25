"""Compat re-export: wave effects live in effects_wave_* modules."""
from controllers.panel.effects_wave_add import *  # noqa: F401,F403
from controllers.panel.effects_wave_edit import *  # noqa: F401,F403
from controllers.panel.effects_wave_apply import *  # noqa: F401,F403
from controllers.panel.wave_hits import _b3_wave_hits, _b3_wave_sliders  # noqa: F401
from controllers.panel.effects_wave_add import handle_b_part1  # noqa: F401
from controllers.panel.effects_wave_edit import handle_b_part2  # noqa: F401
from controllers.panel.effects_wave_apply import handle_b_part3  # noqa: F401

def effects_wave_hit(tools, document, selection, ui, state, event, ctx, handlers):
    """Typed entry point for the wave/effects panel domain.

    Handlers consume the live typed dispatch context; domain boundaries are
    typed while individual handler bodies migrate incrementally.
    """
    for handler in handlers:
        if handler(ctx, event):
            return True
    return False

# Semantic aliases
handle_wave_effects_primary = handle_b_part1
handle_wave_effects_secondary = handle_b_part2
handle_wave_effect_hits = _b3_wave_hits
handle_wave_effects_sliders = _b3_wave_sliders
handle_wave_effects_tertiary = handle_b_part3
