"""Command IDs shared by menus, shortcuts, and UI actions."""

# File
NEW = "new"
SAVE = "save"
SAVE_AS = "save_as"
OPEN = "open"
IMPORT_SVG = "import_svg"
EXPORT = "export"
QUIT = "quit"

# Edit
UNDO = "undo"
REDO = "redo"
SELECT_ALL = "select_all"
DUPLICATE = "duplicate"
GROUP = "group"
UNGROUP = "ungroup"
COPY = "copy"
CUT = "cut"
PASTE = "paste"
DELETE = "delete"

# View / tools
TOOL_SELECT = "tool_select"
TOOL_EYEDROPPER = "tool_eyedropper"
TOOL_PEN = "tool_pen"
TOOL_ERASER = "tool_eraser"
TOOL_BUCKET = "tool_bucket"
TOOL_CUTTER = "tool_cutter"
TOOL_TEXT = "tool_text"
TOGGLE_SNAP = "toggle_snap"
TOGGLE_GRID = "toggle_grid"
TOGGLE_RULERS = "toggle_rulers"
FIT = "fit"
ACTUAL_SIZE = "actual_size"
CYCLE_SUBMODE = "cycle_submode"

ALL_COMMAND_IDS = {
    NEW, SAVE, SAVE_AS, OPEN, IMPORT_SVG, EXPORT, QUIT,
    UNDO, REDO, SELECT_ALL, DUPLICATE, GROUP, UNGROUP, COPY, CUT, PASTE, DELETE,
    TOOL_SELECT, TOOL_EYEDROPPER, TOOL_PEN, TOOL_ERASER, TOOL_BUCKET, TOOL_CUTTER, TOOL_TEXT,
    TOGGLE_SNAP, TOGGLE_GRID, TOGGLE_RULERS, FIT, ACTUAL_SIZE, CYCLE_SUBMODE,
}
