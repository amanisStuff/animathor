"""Semantic panel action domains.

This package provides domain-oriented entry points over the existing panel
handler implementations. It is an incremental semantic layer: handlers can be
moved here domain-by-domain without changing behavior.
"""

from controllers.panel_actions.wave_effects import (  # noqa: F401
    handle_wave_effects_primary,
    handle_wave_effects_secondary,
    handle_wave_effects_sliders,
)

__all__ = [
    "handle_wave_effects_primary",
    "handle_wave_effects_secondary",
    "handle_wave_effects_sliders",
]
