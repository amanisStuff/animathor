"""Semantic mapping for quantitatively split panel view modules.

The panel view code is still split by legacy part files; this module provides
semantic domain names to migrate against without changing behavior.
"""

# Selection/property panel domains -> existing implementations
from views.panel_select_parts import *  # noqa: F401,F403
from views.panel_select_parts_b import *  # noqa: F401,F403
from views.panel_select_parts_b2 import *  # noqa: F401,F403
from views.panel_select_parts_c import *  # noqa: F401,F403
from views.panel_select_parts_c2 import *  # noqa: F401,F403

# Domain aliases (semantic intent)
PANEL_DOMAIN_TRANSFORM = "transform_align"
PANEL_DOMAIN_STROKE_STYLE = "stroke_style"
PANEL_DOMAIN_COLOR_FILL = "color_fill"
PANEL_DOMAIN_EFFECTS = "effects_wave"
PANEL_DOMAIN_TEXT = "text"
PANEL_DOMAIN_REFERENCE = "reference"
