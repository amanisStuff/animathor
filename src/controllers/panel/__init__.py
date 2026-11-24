"""Semantic panel/UI command domains (Phase 3 migration).

Domains own a panel concern (tool options, fill/color picker, gradient stops,
etc.) and are dispatched by priority rather than by quantitative part number.
"""

from controllers.panel import dispatch, rects  # noqa: F401
