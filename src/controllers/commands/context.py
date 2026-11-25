"""Typed command context for menu/shortcut command dispatch.

Replaces the ad-hoc ``SimpleNamespace`` ctx bag used by ``run_menu_action``
with a typed contract. State fields are populated from ``AppState`` substates;
service/callback fields are explicit dependencies, not app state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CommandContext:
    # Document state
    strokes: list | None = None
    _shape_state_counter: int = 0
    _symbol_counter: int = 0
    active_artboard: int = -1
    artboards: list | None = None
    clipboard_strokes: list | None = None
    document_path: str | None = None
    shape_states: dict | None = None
    symbols: dict | None = None

    # Interaction / selection state
    current_points: list | None = None
    curve_cut_mode: bool = False
    cut_points: list | None = None
    cutting: bool = False
    drag_last: Any = None
    drawing: bool = False
    eyedropper_pick: bool = False
    redrawing_curve: Any = None
    selected_curve: Any = None
    selected_curves: set | None = None
    selected_point: Any = None
    selected_strokes: set | None = None
    selection_submode: str = "transform"
    transform_drag: Any = None

    # Tool / UI state
    draw_tool: str = "pen"
    export_dialog_format: str = "png"
    export_dialog_open: bool = False
    help_open: bool = False
    panel_collapsed: bool = False
    running: bool = True
    snap_enabled: bool = True
    text_entry: Any = None
    text_family: str = "Sans"
    text_size: float = 36.0
    tool_mode: str = "draw"
    workspace: str = "draw"

    # View state and explicit services (not app state)
    state: dict | None = None
    _bezier_pen_cancel: Any = None
    _bezier_pen_commit_or_cancel: Any = None
    _capture_shape_state: Any = None
    _copy_stroke: Any = None
    _delete_shape_state: Any = None
    _insert_shape_state: Any = None
    assign_group: Any = None
    cfg: Any = None
    clear_group: Any = None
    combined_bbox: Any = None
    copy: Any = None
    do_redo: Any = None
    do_undo: Any = None
    import_svg: Any = None
    load_document_with_meta: Any = None
    new_group_id: Any = None
    pick_import_svg_path: Any = None
    pick_open_document_path: Any = None
    pick_save_document_path: Any = None
    push_undo: Any = None
    relayout: Any = None
    save_document: Any = None
    translate_stroke: Any = None
