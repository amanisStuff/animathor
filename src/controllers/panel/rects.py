"""Compat re-export: the shared rect contract lives in neutral ``panel_rects``.

Controllers import from here; views import the neutral module directly, so no
view→controller dependency is introduced.
"""

from panel_rects import (  # noqa: F401,F403
    PanelRects,
    RECT_DOMAINS,
    domain_of,
    hit_rect,
    publish_rect,
    rects_from_state,
)
