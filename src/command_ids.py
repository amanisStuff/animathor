"""Command IDs shared by menus, shortcuts, and UI actions.

Neutral module at the ``src`` root so both ``views`` (menu definitions) and
``controllers`` (command handlers) can single-source the same IDs without
introducing a view->controller dependency cycle.
"""

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
TOGGLE_GRID_SNAP = "toggle_grid_snap"
TOGGLE_PANEL = "toggle_panel"
CLEAR_GUIDES = "clear_guides"
FIT = "fit"
ACTUAL_SIZE = "actual_size"
CYCLE_SUBMODE = "cycle_submode"
WORKSPACE = "workspace"
SHORTCUTS = "shortcuts"

# Artboards
ARTBOARD_ADD = "artboard_add"
ARTBOARD_REMOVE = "artboard_remove"
ARTBOARD_NEXT = "artboard_next"
ARTBOARD_FIT_SELECTION = "artboard_fit_selection"

# Shape states
SHAPE_STATE_SAVE = "shape_state_save"
SHAPE_STATE_INSERT = "shape_state_insert"
SHAPE_STATE_DELETE = "shape_state_delete"

# Symbols
SYMBOL_CREATE = "symbol_create"
SYMBOL_INSERT = "symbol_insert"
SYMBOL_UPDATE = "symbol_update"
SYMBOL_DETACH = "symbol_detach"

ALL_COMMAND_IDS = {
    NEW, SAVE, SAVE_AS, OPEN, IMPORT_SVG, EXPORT, QUIT,
    UNDO, REDO, SELECT_ALL, DUPLICATE, GROUP, UNGROUP, COPY, CUT, PASTE, DELETE,
    TOOL_SELECT, TOOL_EYEDROPPER, TOOL_PEN, TOOL_ERASER, TOOL_BUCKET, TOOL_CUTTER, TOOL_TEXT,
    TOGGLE_SNAP, TOGGLE_GRID, TOGGLE_RULERS, TOGGLE_GRID_SNAP, TOGGLE_PANEL, CLEAR_GUIDES,
    FIT, ACTUAL_SIZE, CYCLE_SUBMODE, WORKSPACE, SHORTCUTS,
    ARTBOARD_ADD, ARTBOARD_REMOVE, ARTBOARD_NEXT, ARTBOARD_FIT_SELECTION,
    SHAPE_STATE_SAVE, SHAPE_STATE_INSERT, SHAPE_STATE_DELETE,
    SYMBOL_CREATE, SYMBOL_INSERT, SYMBOL_UPDATE, SYMBOL_DETACH,
}

__all__ = [name for name in dir() if name.isupper()]
