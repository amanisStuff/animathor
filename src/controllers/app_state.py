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
    reference_image: Any = None
    reference_error: Any = None
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
    prev_selection_set: set = field(default_factory=set)


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
    max_points_per_curve: int = 4
    boost_points: bool = False
    trace_algorithm: str = "fit"
    triangle_variant: str = "isosceles"
    rect_variant: str = "rect"
    ellipse_variant: str = "ellipse"
    line_constrain: bool = False
    line_arrow: bool = False
    corner_radius: int = 0
    ellipse_segments: int = 4
    polygon_sides: int = 6
    star_points: int = 5
    star_inner_ratio: float = 0.5


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
    cut_gap: int = 0
    drawing: bool = False
    current_points: list = field(default_factory=list)
    redrawing_curve: Any = None
    drag_manager: Any = None
    pivot_pos: Any = None
    pending_transform_toggle: Any = None
    guides: list = field(default_factory=list)
    guide_drag: Any = None
    smart_snap_guides: list = field(default_factory=list)


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
    # Double-click numeric entry for draggable panel fields (DragField).
    drag_field_edit: Any = None
    drag_field_last_click: Any = None
    # Collapsible properties-panel sections (key -> expanded bool).
    panel_sections: dict = field(default_factory=dict)
    panel_section_rects: dict = field(default_factory=dict)
    picker_h: Any = None
    picker_s: Any = None
    picker_v: Any = None
    picker_drag_sv: bool = False
    picker_drag_hue: bool = False
    picker_drag_alpha: bool = False
    color_target: str = "stroke"
    fill_gradient_stop: int = 0
    fill_stop_pos_drag: bool = False
    obj_opacity_drag: bool = False
    bucket_picker_drag: Any = None
    align_bottom_rect_cache: Any = None
    align_hcenter_rect_cache: Any = None
    align_left_rect_cache: Any = None
    align_right_rect_cache: Any = None
    align_top_rect_cache: Any = None
    align_vmiddle_rect_cache: Any = None
    bool_exclude_rect_cache: Any = None
    bool_intersect_rect_cache: Any = None
    bool_subtract_rect_cache: Any = None
    bool_union_rect_cache: Any = None
    bucket_hue_rect_cache: Any = None
    bucket_sv_rect_cache: Any = None
    bucket_swatch_rects_cache: dict = field(default_factory=dict)
    cap_next_rect_cache: Any = None
    cap_prev_rect_cache: Any = None
    curve_cut_rect_cache: Any = None
    curve_hide_rect_cache: Any = None
    curve_join_rect_cache: Any = None
    curve_redraw_rect_cache: Any = None
    dash_next_rect_cache: Any = None
    dash_prev_rect_cache: Any = None
    displacement_add_rect_cache: Any = None
    displacement_affect_rects_cache: dict = field(default_factory=dict)
    displacement_profile_rects_cache: dict = field(default_factory=dict)
    distribute_h_rect_cache: Any = None
    distribute_v_rect_cache: Any = None
    draw_shape_rects_cache: dict = field(default_factory=dict)
    draw_tool_bucket_rect_cache: Any = None
    draw_tool_cutter_rect_cache: Any = None
    draw_tool_eraser_rect_cache: Any = None
    draw_tool_next_rect_cache: Any = None
    draw_tool_pen_rect_cache: Any = None
    draw_tool_prev_rect_cache: Any = None
    elev_back_rect_cache: Any = None
    elev_backward_rect_cache: Any = None
    elev_forward_rect_cache: Any = None
    elev_front_rect_cache: Any = None
    eyedropper_rect_cache: Any = None
    fill_stop_add_rect_cache: Any = None
    fill_stop_pos_rect_cache: Any = None
    fill_stop_rects_cache: dict = field(default_factory=dict)
    fill_stop_remove_rect_cache: Any = None
    fill_type_next_rect_cache: Any = None
    fill_type_prev_rect_cache: Any = None
    join_next_rect_cache: Any = None
    join_prev_rect_cache: Any = None
    marker_end_rect_cache: Any = None
    marker_start_rect_cache: Any = None
    mirror_h_rect_cache: Any = None
    mirror_v_rect_cache: Any = None
    nodes_mode_next_rect_cache: Any = None
    nodes_mode_prev_rect_cache: Any = None
    obj_opacity_rect_cache: Any = None
    panel_toggle_rect_cache: Any = None
    path_add_rect_cache: Any = None
    path_close_rect_cache: Any = None
    path_corner_rect_cache: Any = None
    path_delete_rect_cache: Any = None
    path_expand_rect_cache: Any = None
    path_reverse_rect_cache: Any = None
    path_smooth_rect_cache: Any = None
    pattern_size_minus_rect_cache: Any = None
    pattern_size_plus_rect_cache: Any = None
    pattern_type_rect_cache: Any = None
    picker_rects: dict = field(default_factory=dict)
    ref_clear_rect_cache: Any = None
    ref_load_rect_cache: Any = None
    ref_opacity_rect_cache: Any = None
    ref_vis_rect_cache: Any = None
    repeat_add_rect_cache: Any = None
    repeat_pick_curve_rect_cache: Any = None
    shadow_blur_minus_rect_cache: Any = None
    shadow_blur_plus_rect_cache: Any = None
    shadow_toggle_rect_cache: Any = None
    snap_toggle_rect_cache: Any = None
    swatch_rects_cache: dict = field(default_factory=dict)
    text_edit_rect_cache: Any = None
    text_font_rect_cache: Any = None
    text_off_path_rect_cache: Any = None
    text_on_path_rect_cache: Any = None
    text_size_minus_rect_cache: Any = None
    text_size_plus_rect_cache: Any = None
    thickness_add_rect_cache: Any = None
    trace_algo_next_rect_cache: Any = None
    trace_algo_prev_rect_cache: Any = None
    wave_add_rect_cache: Any = None
    wave_bake_rect_cache: Any = None
    wave_clamp_rect_cache: Any = None
    wave_clear_rect_cache: Any = None
    wave_custom_box_rect_cache: Any = None
    wave_done_rect_cache: Any = None
    wave_formula_rect_cache: Any = None
    wave_remove_rect_cache: Any = None
    wave_reverse_rect_cache: Any = None
    wave_row_rects_cache: dict = field(default_factory=dict)
    wave_shape_next_rect_cache: Any = None
    wave_shape_prev_rect_cache: Any = None
    wave_slider_rects_cache: dict = field(default_factory=dict)
    wave_smooth_rect_cache: Any = None
    wave_toggle_rect_cache: Any = None
    width_profile_next_rect_cache: Any = None
    width_profile_prev_rect_cache: Any = None
    xform_h_rect_cache: Any = None
    xform_hm_rect_cache: Any = None
    xform_hp_rect_cache: Any = None
    xform_r_rect_cache: Any = None
    xform_rm_rect_cache: Any = None
    xform_rp_rect_cache: Any = None
    xform_w_rect_cache: Any = None
    xform_wm_rect_cache: Any = None
    xform_wp_rect_cache: Any = None
    xform_x_rect_cache: Any = None
    xform_xm_rect_cache: Any = None
    xform_xp_rect_cache: Any = None
    xform_y_rect_cache: Any = None
    xform_ym_rect_cache: Any = None
    xform_yp_rect_cache: Any = None

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

    def sync_from_locals(self, ns: dict, fields=None):
        """Incremental bridge: mirror legacy locals into typed contracts.

        ``fields`` optionally narrows the bridge to a named subset, so a caller
        can capture only its own direct mutations without overwriting typed
        state owned by handlers.
        """
        for st in self._substates(self):
            for k in st.__dataclass_fields__:
                if (fields is None or k in fields) and k in ns:
                    setattr(st, k, ns[k])
        return self

    def to_locals_dict(self):
        """Export typed state to legacy local names (migration bridge)."""
        out = {}
        for st in self._substates(self):
            for k in st.__dataclass_fields__:
                out[k] = getattr(st, k)
        return out
