"""App configuration: layout, theme tokens and UI constant tables.

Static values are safe to star-import. The five window-layout values that
the Controller updates on window resize (WIDTH, HEIGHT, CANVAS_W,
CANVAS_X, PANEL_X) are intentionally excluded from __all__: read them
live via `import config as cfg` attribute access so View and Controller
always see the current window size.

Theme
-----
Every colour, radius, spacing and border width used by the chrome lives here.
Views must use these semantic tokens instead of ad-hoc literals so the whole
application looks and behaves like one coherent, modern UI. Old colour names
are kept as aliases for backwards compatibility with external callers.
"""

__all__ = [
    # Legacy names (kept as aliases)
    "ACCENT",
    "ACTIVE_COLOR",
    "BG_COLOR",
    "BOTTOM_BAR_H",
    "BOTTOM_TOOLS",
    "BUCKET_SWATCHES",
    "BUTTON_BG",
    "BUTTON_BORDER",
    "BUTTON_HOVER",
    "DRAW_SHAPES",
    "FILL_SWATCHES",
    "LEFT_BAR_W",
    "MUTED_COLOR",
    "PANEL_BG",
    "PANEL_BORDER",
    "PANEL_W",
    "STROKE_SWATCHES",
    "TEXT_COLOR",
    "TOOLBAR_BG",
    "TOP_BAR_H",
    "TOOL_ACTIVE",
    "TRACE_ALGORITHMS",
    "TRIANGLE_VARIANTS",
    # Semantic colours
    "SURFACE",
    "SURFACE_SUBTLE",
    "SURFACE_ALT",
    "SURFACE_SUNKEN",
    "SURFACE_DISABLED",
    "SHADOW_COLOR",
    "BORDER_SUBTLE",
    "BORDER_STRONG",
    "BORDER_DISABLED",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "TEXT_DISABLED",
    "TEXT_ON_ACCENT",
    "TEXT_DANGER",
    "TEXT_WARNING",
    "HOVER_BG",
    "ACTIVE_BG",
    "PRIMARY",
    "PRIMARY_HOVER",
    "PRIMARY_SOFT",
    "DANGER",
    "DISABLED",
    "PLOT_BG",
    "PLOT_BG_DISABLED",
    "PLOT_GRID",
    "PLOT_LINE_DISABLED",
    "TOOLTIP_BG",
    "TOOLTIP_BORDER",
    "TOOLTIP_TEXT",
    "CANVAS_BACKDROP",
    "SELECTION_FILL",
    "SELECTION_BORDER",
    "CUT_COLOR",
    "CUT_HANDLE_RADIUS",
    "NO_SWATCH_COLOR",
    "CUSTOM_CURVE_COLOR",
    "HANDLE_OUTLINE",
    "SAMPLE_PLACEHOLDER",
    # Canvas editor overlay tokens
    "EDITOR_SELECTION_RGB",
    "EDITOR_ACCENT_RGB",
    "EDITOR_ROTATION_RGB",
    "EDITOR_HANDLE_FILL_RGB",
    "EDITOR_SELECTION",
    "EDITOR_ACCENT",
    "EDITOR_ROTATION",
    "EDITOR_HANDLE_FILL",
    "EDITOR_GUIDE",
    "EDITOR_TEMPLATE",
    "EDITOR_HANDLE_RADIUS",
    "EDITOR_HANDLE_HALF",
    "EDITOR_SKEW_RADIUS",
    "EDITOR_PIVOT_RADIUS",
    "EDITOR_PIVOT_INNER_RADIUS",
    "EDITOR_SNAP_RADIUS",
    "EDITOR_SNAP_INNER",
    "EDITOR_LINE_WIDTH",
    "EDITOR_LINE_WIDTH_BOLD",
    "EDITOR_LINE_WIDTH_SUBTLE",
    "DEFAULT_STROKE_RGBA",
    "DEFAULT_FILL_RGBA",
    "cairo_rgb",
    # Shape / scale tokens
    "RADIUS_XS",
    "RADIUS_SM",
    "RADIUS_MD",
    "RADIUS_LG",
    "RADIUS_XL",
    "SPACE_XS",
    "SPACE_SM",
    "SPACE_MD",
    "SPACE_LG",
    "SPACE_XL",
    "MIN_ELEMENT_SPACING",
    "BORDER_WIDTH",
    "BORDER_WIDTH_ACTIVE",
    "SHADOW_OFFSET",
    "CONTROL_H",
    "DRAG_FIELD_H",
    "ICON_SIZE",
    "MENU_WIDTH",
    "MENU_SEPARATOR_H",
    "PICKER_HANDLE_RADIUS",
    "SLIDER_KNOB_RADIUS",
    "FONT_SIZE_BODY",
    "FONT_SIZE_SMALL",
    "FONT_SIZE_TITLE",
    "FONT_SIZE_TOOLTIP",
]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

TOP_BAR_H = 28
LEFT_BAR_W = 56
BOTTOM_BAR_H = 56

CANVAS_W, HEIGHT = 980, 700

PANEL_W = 280

WIDTH = LEFT_BAR_W + CANVAS_W + PANEL_W

CANVAS_X = LEFT_BAR_W

PANEL_X = LEFT_BAR_W + CANVAS_W


def canvas_viewport_height():
    """Height of the drawable canvas area (window minus top and bottom bars)."""
    return max(1, HEIGHT - TOP_BAR_H - BOTTOM_BAR_H)


# View/camera transform (world <-> screen). Mutated by the Controller.
VIEW_ZOOM = 1.0
VIEW_PAN_X = 0.0
VIEW_PAN_Y = 0.0

# Grid / rulers / guides overlay (view-only). Off by default so deterministic
# previews and exports are unchanged until the user enables them.
SHOW_GRID = False
SHOW_RULERS = False
GRID_SIZE = 20.0          # world units between minor grid lines
GRID_MAJOR_EVERY = 5      # every Nth line is drawn as a major line
SNAP_TO_GRID = False

# ---------------------------------------------------------------------------
# Theme tokens
# ---------------------------------------------------------------------------

# Radii: one scale for every rounded surface in the app.
RADIUS_XS = 3     # slider track ends, tiny badges
RADIUS_SM = 4     # swatches, colour pickers
RADIUS_MD = 6     # buttons, rows, toggles
RADIUS_LG = 8     # tool buttons, cards
RADIUS_XL = 12    # popovers

# Spacing: 4px baseline grid. Do not use XS/SM for gaps between separate
# elements; the UI spacing contract is MIN_ELEMENT_SPACING (see STYLE_GUIDE.md).
SPACE_XS = 4
SPACE_SM = 6
SPACE_MD = 10
SPACE_LG = 14
SPACE_XL = 20
MIN_ELEMENT_SPACING = 8

BORDER_WIDTH = 1
BORDER_WIDTH_ACTIVE = 2
SHADOW_OFFSET = 3

# Standard control height and icon size keep rows aligned across panels/toolbars.
CONTROL_H = 28
DRAG_FIELD_H = 24        # draggable numeric field (scrub input)
ICON_SIZE = 20
MENU_WIDTH = 224          # dropdown width; item height reuses CONTROL_H
MENU_SEPARATOR_H = SPACE_SM
PICKER_HANDLE_RADIUS = 6
SLIDER_KNOB_RADIUS = 7

# Typography: 20/24/30 covers small labels, body text and panel headings.
FONT_SIZE_SMALL = 20
FONT_SIZE_BODY = 24
FONT_SIZE_TITLE = 30
FONT_SIZE_TOOLTIP = 19

# Surfaces -- light, neutral chrome.
SURFACE = (255, 255, 255)
SURFACE_SUBTLE = (250, 251, 253)
SURFACE_ALT = (248, 250, 252)
SURFACE_SUNKEN = (245, 247, 250)
SURFACE_DISABLED = (245, 246, 248)
SHADOW_COLOR = (222, 226, 234)

# Borders.
BORDER_SUBTLE = (225, 228, 235)
BORDER_STRONG = (160, 170, 185)
BORDER_DISABLED = (210, 214, 220)

# Text.
TEXT_PRIMARY = (30, 35, 45)
TEXT_SECONDARY = (90, 100, 115)
TEXT_DISABLED = (170, 176, 184)
TEXT_ON_ACCENT = (255, 255, 255)
TEXT_DANGER = (190, 70, 60)
TEXT_WARNING = (170, 95, 40)

# Interactive states.
HOVER_BG = (232, 238, 248)
ACTIVE_BG = (220, 232, 248)
PRIMARY = (60, 120, 220)
PRIMARY_HOVER = (48, 102, 196)
PRIMARY_SOFT = (220, 232, 248)
DANGER = (205, 115, 115)
DISABLED = (180, 186, 198)

# Small preview plots (wave/displacement editors).
PLOT_BG = (245, 247, 250)
PLOT_BG_DISABLED = (238, 240, 244)
PLOT_GRID = (205, 212, 224)
PLOT_LINE_DISABLED = (150, 156, 168)

# Tooltips intentionally use a dark surface for contrast over any canvas.
TOOLTIP_BG = (34, 38, 48)
TOOLTIP_BORDER = (96, 104, 120)
TOOLTIP_TEXT = (240, 244, 250)

# Canvas chrome.
CANVAS_BACKDROP = (230, 233, 238)
SELECTION_FILL = (80, 140, 240, 35)
SELECTION_BORDER = (60, 120, 220)
CUT_COLOR = (225, 70, 70)
CUT_HANDLE_RADIUS = 3
NO_SWATCH_COLOR = (200, 60, 60)
CUSTOM_CURVE_COLOR = (100, 150, 255)
HANDLE_OUTLINE = (0, 0, 0)
SAMPLE_PLACEHOLDER = (128, 128, 128)

# Grid / ruler / guide chrome.
GRID_MINOR_RGB = (214, 220, 230)
GRID_MAJOR_RGB = (188, 197, 212)
RULER_BG_RGB = (246, 248, 251)
RULER_TEXT_RGB = (110, 120, 136)
RULER_TICK_RGB = (170, 180, 196)
GUIDE_RGB = (60, 150, 235)
GUIDE_SELECTED_RGB = (242, 115, 26)
RULER_SIZE = 18


def cairo_rgb(token, alpha=1.0):
    """Convert a 0..255 RGB token to Cairo's 0..1 float RGB(A) colour space.

    Keeping editor overlays in the same palette as the chrome is what makes
    the canvas feel like part of the application instead of a separate tool.
    """
    rgba = tuple(round(c / 255.0, 6) for c in token[:3])
    return rgba if alpha >= 1.0 else rgba + (alpha,)


# Editor overlays share the chrome palette. Cairo needs 0..1 floats, so the
# same semantic colours are exposed in both spaces for the views to use.
EDITOR_SELECTION_RGB = PRIMARY       # outlines, scale/anchor and link handles
EDITOR_ACCENT_RGB = (242, 115, 26)   # pivot, control points, gradient center
EDITOR_ROTATION_RGB = (38, 179, 89)  # rotation handles
EDITOR_HANDLE_FILL_RGB = SURFACE     # opaque handle interior
EDITOR_GUIDE_RGB = (102, 128, 153)   # node control-handle guide lines
EDITOR_TEMPLATE_RGB = (255, 255, 0)  # low-opacity redraw template highlight

EDITOR_SELECTION = cairo_rgb(EDITOR_SELECTION_RGB)
EDITOR_ACCENT = cairo_rgb(EDITOR_ACCENT_RGB)
EDITOR_ROTATION = cairo_rgb(EDITOR_ROTATION_RGB)
EDITOR_HANDLE_FILL = cairo_rgb(EDITOR_HANDLE_FILL_RGB)
EDITOR_GUIDE = cairo_rgb(EDITOR_GUIDE_RGB)
EDITOR_TEMPLATE = cairo_rgb(EDITOR_TEMPLATE_RGB)

# One geometry scale for every on-canvas editor handle (screen-space pixels).
# hit_test_bbox_handle uses an 8px radius, so handles stay comfortably grabbable.
EDITOR_HANDLE_RADIUS = 5.0
EDITOR_HANDLE_HALF = 4.0
EDITOR_SKEW_RADIUS = 4.5
EDITOR_PIVOT_RADIUS = 7.0
EDITOR_PIVOT_INNER_RADIUS = 2.5
EDITOR_SNAP_RADIUS = 11.0
EDITOR_SNAP_INNER = 2.5

EDITOR_LINE_WIDTH = 1.5
EDITOR_LINE_WIDTH_BOLD = 2.0
EDITOR_LINE_WIDTH_SUBTLE = 1.2

# Shared drawing data defaults (Cairo 0..1 float RGBA). Centralising these
# keeps stroke/fill fallbacks identical everywhere a colour may be missing.
DEFAULT_STROKE_RGBA = (0.1, 0.1, 0.15, 1.0)
DEFAULT_FILL_RGBA = (0.0, 0.0, 0.0, 1.0)

# ---------------------------------------------------------------------------
# Legacy aliases (do not remove: external code/tests import these names).
# ---------------------------------------------------------------------------

BG_COLOR = (1.0, 1.0, 1.0)
ACTIVE_COLOR = (0.2, 0.4, 0.9)  # float RGB for Cairo

PANEL_BG = SURFACE_SUNKEN
PANEL_BORDER = BORDER_SUBTLE
TEXT_COLOR = TEXT_PRIMARY
MUTED_COLOR = TEXT_SECONDARY
BUTTON_BG = SURFACE
BUTTON_HOVER = HOVER_BG
BUTTON_BORDER = (180, 190, 205)
ACCENT = PRIMARY
TOOLBAR_BG = (236, 239, 244)
TOOL_ACTIVE = ACTIVE_BG

# ---------------------------------------------------------------------------
# Option tables
# ---------------------------------------------------------------------------

STROKE_SWATCHES = [
    (0.1, 0.1, 0.15),
    (0.9, 0.2, 0.2),
    (0.15, 0.55, 0.2),
    (0.15, 0.35, 0.9),
    (0.95, 0.6, 0.1),
]

FILL_SWATCHES = [
    None,
    (0.85, 0.92, 1.0),
    (1.0, 0.9, 0.85),
    (0.88, 1.0, 0.88),
    (0.97, 0.88, 1.0),
    (1.0, 1.0, 1.0),
]

# Preset colors for the Fill (bucket) tool. Unlike FILL_SWATCHES these are all
# opaque colors (a bucket fill with no color would be invisible).
BUCKET_SWATCHES = [
    (0.45, 0.72, 1.0),
    (0.85, 0.92, 1.0),
    (1.0, 0.9, 0.85),
    (0.88, 1.0, 0.88),
    (0.97, 0.88, 1.0),
    (0.95, 0.6, 0.1),
    (0.9, 0.2, 0.2),
    (0.15, 0.55, 0.2),
    (0.15, 0.35, 0.9),
    (1.0, 1.0, 1.0),
    (0.1, 0.1, 0.15),
]

TRACE_ALGORITHMS = [
    ("fit", "Fit"),
    ("catmull-rom", "C-R"),
    ("single", "Single"),
]

DRAW_SHAPES = [
    ("freehand", "Free"),
    ("pen", "Pen"),
    ("line", "Line"),
    ("rect", "Rect"),
    ("ellipse", "Ellipse"),
    ("triangle", "Tri"),
    ("polygon", "Poly"),
    ("star", "Star"),
]

# Non-shape drawing tools shown at the right end of the bottom bar.
BOTTOM_TOOLS = [
    ("eraser", "Eraser"),
    ("cutter", "Split"),
    ("bucket", "Fill"),
    ("text", "Text"),
]

# Triangle sub-types (right-click the Tri button on the bottom bar).
TRIANGLE_VARIANTS = [
    ("isosceles", "Isosceles"),
    ("right", "Right"),
    ("equilateral", "Equilateral"),
]
