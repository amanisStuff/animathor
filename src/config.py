"""App configuration: layout, theme colors and UI constant tables.

Static values are safe to star-import. The five window-layout values that
the Controller updates on window resize (WIDTH, HEIGHT, CANVAS_W,
CANVAS_X, PANEL_X) are intentionally excluded from __all__: read them
live via `import config as cfg` attribute access so View and Controller
always see the current window size."""

__all__ = [
    "ACCENT",
    "ACTIVE_COLOR",
    "BG_COLOR",
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
]

TOP_BAR_H = 28
LEFT_BAR_W = 56

CANVAS_W, HEIGHT = 980, 700

PANEL_W = 280

WIDTH = LEFT_BAR_W + CANVAS_W + PANEL_W

CANVAS_X = LEFT_BAR_W

PANEL_X = LEFT_BAR_W + CANVAS_W

# View/camera transform (world <-> screen). Mutated by the Controller.
VIEW_ZOOM = 1.0
VIEW_PAN_X = 0.0
VIEW_PAN_Y = 0.0

BG_COLOR = (1.0, 1.0, 1.0)

ACTIVE_COLOR = (0.2, 0.4, 0.9)

PANEL_BG = (245, 247, 250)

PANEL_BORDER = (210, 215, 225)

TEXT_COLOR = (30, 35, 45)

MUTED_COLOR = (90, 100, 115)

BUTTON_BG = (255, 255, 255)

BUTTON_HOVER = (232, 238, 248)

BUTTON_BORDER = (180, 190, 205)

ACCENT = (60, 120, 220)

TOOLBAR_BG = (236, 239, 244)

TOOL_ACTIVE = (220, 232, 248)

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

TRACE_ALGORITHMS = [
    ("fit", "Fit"),
    ("catmull-rom", "C-R"),
    ("single", "Single"),
]

DRAW_SHAPES = [
    ("freehand", "Free"),
    ("line", "Line"),
    ("rect", "Rect"),
    ("square", "Square"),
    ("ellipse", "Ellipse"),
    ("circle", "Circle"),
    ("triangle", "Tri"),
]
