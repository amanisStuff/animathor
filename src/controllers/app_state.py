"""Typed state contracts for incremental migration away from ctx locals.

This module defines semantic state groups. The app still uses legacy locals in
`app_controller.main`, but these contracts provide a stable target for
incremental migration and eliminate implicit field ownership.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ViewportState:
    width: int = 1400
    height: int = 900
    canvas_x: int = 0
    canvas_w: int = 0
    panel_x: int = 0
    panel_collapsed: bool = False
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0


@dataclass
class DocumentState:
    strokes: list = field(default_factory=list)
    shape_states: dict = field(default_factory=dict)
    artboards: list = field(default_factory=list)
    active_artboard: int = -1
    symbols: dict = field(default_factory=dict)
    document_path: str | None = None
    clipboard_strokes: list = field(default_factory=list)
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)
    max_undo: int = 100
    _shape_state_counter: int = 0
    _symbol_counter: int = 0


@dataclass
class SelectionState:
    selected_strokes: set = field(default_factory=set)
    selected_point: Any = None
    selected_curve: Any = None
    selected_curves: set = field(default_factory=set)
    selection_submode: str = "transform"
    transform_handle_mode: str = "scale"


@dataclass
class ToolState:
    tool_mode: str = "draw"
    draw_tool: str = "pen"
    draw_shape: str = "freehand"
    snap_enabled: bool = True
    eyedropper_pick: bool = False
    curve_cut_mode: bool = False
    bucket_fill_color: tuple = (0.45, 0.72, 1.0)
    bucket_picker_h: float = 0.0
    bucket_picker_s: float = 0.0
    bucket_picker_v: float = 0.1
    bezier_pen: Any = None
    text_family: str = "Sans"
    text_size: float = 36.0


@dataclass
class DragState:
    drag_last: Any = None
    transform_drag: Any = None
    gradient_drag: Any = None
    pivot_drag: Any = None
    marquee_select: Any = None
    pan_drag: Any = None
    ref_drag: Any = None
    guide_drag: Any = None
    cutting: bool = False
    cut_points: list = field(default_factory=list)
    drawing: bool = False
    current_points: list = field(default_factory=list)
    redrawing_curve: Any = None
    drag_manager: Any = None


@dataclass
class UiCacheState:
    """UI rect caches and transient UI state synced from render frame."""

    panel_scroll: int = 0
    export_scale: float = 1.0
    export_dpi: int = 300
    export_dialog_rects: dict = field(default_factory=dict)
    marker_dropdown: Any = None
    marker_dropdown_rect: Any = None
    marker_dropdown_item_rects: dict = field(default_factory=dict)
    shape_menu_key: Any = None
    shape_menu_anchor: Any = None
    shape_menu_rect: Any = None
    shape_menu_item_rects: dict = field(default_factory=dict)
    menu_bar_rects: dict = field(default_factory=dict)
    menu_item_rects: dict = field(default_factory=dict)
    wave_formula_focus: bool = False
    wave_custom_draw: bool = False
    wave_custom_drag: Any = None
    wave_custom_finished: bool = False
    wave_active_index: int = 0
    repeat_pick_mode: bool = False
    repeat_pick_target: Any = None
    # Text/xform input-mode state used by the controller ctx builders.
    text_entry: Any = None
    xform_field_focus: Any = None
    xform_field_buffer: str = ""
    picker_h: Any = None
    picker_s: Any = None
    picker_v: Any = None
    # Session/lifecycle state used by menu command dispatch.
    export_dialog_open: bool = False
    export_dialog_format: str = "png"
    help_open: bool = False
    workspace: str = "draw"
    running: bool = True


@dataclass
class AppState:
    viewport: ViewportState = field(default_factory=ViewportState)
    document: DocumentState = field(default_factory=DocumentState)
    selection: SelectionState = field(default_factory=SelectionState)
    tools: ToolState = field(default_factory=ToolState)
    drag: DragState = field(default_factory=DragState)
    ui: UiCacheState = field(default_factory=UiCacheState)

    @staticmethod
    def _substates(obj):
        # Typed substate groups owned by AppState. viewport is included so
        # layout/panel geometry state flows through the typed contract instead
        # of living only as module-level cfg locals / frame locals.
        return (obj.viewport, obj.document, obj.selection, obj.tools, obj.drag, obj.ui)

    @property
    def _SYNC_FIELDS(self):
        # Auto-derived from typed substate dataclass fields (eliminates manual list).
        fields = []
        for st in self._substates(self):
            for k in st.__dataclass_fields__:
                fields.append(k)
        return tuple(fields)

    def sync_from_locals(self, ns: dict):
        """Incremental bridge: mirror legacy locals into typed contracts."""
        for st in self._substates(self):
            for k in st.__dataclass_fields__:
                if k in ns:
                    setattr(st, k, ns[k])
        return self

    def to_locals_dict(self):
        """Export typed state to legacy local names (migration bridge)."""
        out = {}
        for st in self._substates(self):
            for k in st.__dataclass_fields__:
                out[k] = getattr(st, k)
        return out
