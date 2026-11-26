"""Collapsible section headers for the right properties panel.

Sections are stored in ``state["panel_sections"]`` as ``key -> bool`` (expanded).
A missing key falls back to :data:`DEFAULT_OPEN`, so existing callers and tests
that build their own state dict keep working without changes.

Headers publish their hit rect under ``state["panel_section_rects"]`` and keep
the 8px spacing contract: a header is a real UI element and is validated like
any other published rect. When a section is closed its body is not drawn and
the body's rects are cleared, so no stale hit areas survive a frame.
"""

from __future__ import annotations

import pygame

import config as cfg
from config import *  # noqa: F401,F403
from panel_rects import publish_rect

# Sections expanded on first use. Transform and curve/wave controls stay open;
# secondary action groups, appearance extras and reference options start closed
# so the panel reads as a short stack instead of one long wall.
DEFAULT_OPEN = {
    "selection_arrange": False,
    "selection_transform": True,
    "selection_text": True,
    "selection_stroke": False,
    "selection_appearance": False,
    "selection_color": True,
    "curve_color": False,
    "curve_styles": True,
    "draw_options": True,
    "draw_reference": False,
    "help": False,
}

# Rect keys owned by each section body. Used to clear hit areas when closed.
SECTION_RECT_KEYS = {
    "selection_arrange": (
        "elev_front_rect", "elev_forward_rect", "elev_backward_rect", "elev_back_rect",
        "bool_union_rect", "bool_intersect_rect", "bool_subtract_rect", "bool_exclude_rect",
        "mirror_h_rect", "mirror_v_rect",
        "align_left_rect", "align_hcenter_rect", "align_right_rect",
        "align_top_rect", "align_vmiddle_rect", "align_bottom_rect",
        "distribute_h_rect", "distribute_v_rect",
    ),
    "selection_transform": (
        "xform_x_rect", "xform_y_rect", "xform_w_rect", "xform_h_rect", "xform_r_rect",
        "xform_xm_rect", "xform_xp_rect", "xform_ym_rect", "xform_yp_rect",
        "xform_wm_rect", "xform_wp_rect", "xform_hm_rect", "xform_hp_rect",
        "xform_rm_rect", "xform_rp_rect",
    ),
    "selection_text": (
        "text_edit_rect", "text_font_rect", "text_size_minus_rect",
        "text_size_plus_rect", "text_on_path_rect", "text_off_path_rect",
    ),
    "selection_path": (
        "path_close_rect", "path_reverse_rect", "path_add_rect",
        "path_delete_rect", "path_smooth_rect", "path_corner_rect",
        "path_expand_rect",
    ),
    "selection_stroke": (
        "width_profile_prev_rect", "width_profile_next_rect",
        "cap_prev_rect", "cap_next_rect",
        "join_prev_rect", "join_next_rect",
        "dash_prev_rect", "dash_next_rect",
        "marker_start_rect", "marker_end_rect",
        "marker_dropdown_rect", "marker_dropdown_item_rects",
    ),
    "selection_appearance": (
        "obj_opacity_rect", "shadow_toggle_rect",
        "shadow_blur_minus_rect", "shadow_blur_plus_rect",
    ),
    "selection_color": (
        "tab_stroke_rect", "tab_fill_rect", "nofill_rect",
        "fill_type_prev_rect", "fill_type_next_rect",
        "fill_stop_rects", "fill_stop_add_rect", "fill_stop_remove_rect",
        "fill_stop_pos_rect",
        "pattern_type_rect", "pattern_size_minus_rect", "pattern_size_plus_rect",
        "sv_rect", "hue_rect", "alpha_rect",
        "stroke_swatch_rects", "fill_swatch_rects",
    ),
    "curve_actions": (
        "curve_hide_rect", "curve_redraw_rect", "curve_cut_rect", "curve_join_rect",
    ),
    "curve_styles": (
        "wave_list_header_rect", "wave_toggle_rect", "wave_add_rect",
        "displacement_add_rect", "repeat_add_rect", "thickness_add_rect",
        "wave_remove_rect", "wave_bake_rect", "wave_formula_rect",
        "wave_custom_box_rect", "wave_smooth_rect", "wave_clear_rect",
        "wave_done_rect", "repeat_pick_curve_rect",
        "wave_reverse_rect", "wave_clamp_rect",
        "wave_row_rects", "wave_slider_rects", "wave_shape_rects",
        "displacement_profile_rects",
    ),
    "draw_reference": (
        "ref_load_rect", "ref_vis_rect", "ref_clear_rect", "ref_opacity_rect",
    ),
}

COLOR_RECT_KEYS = SECTION_RECT_KEYS["selection_color"]


def _section_map(state):
    sections = state.get("panel_sections")
    if not isinstance(sections, dict):
        sections = {}
        state["panel_sections"] = sections
    rects = state.get("panel_section_rects")
    if not isinstance(rects, dict):
        rects = {}
        state["panel_section_rects"] = rects
    return sections, rects


def is_open(state, key):
    """Return whether ``key`` is expanded (applying the default when unset)."""
    sections, _ = _section_map(state)
    return bool(sections.get(key, DEFAULT_OPEN.get(key, True)))


def set_open(state, key, value):
    """Persist an explicit expanded state for ``key``."""
    sections, _ = _section_map(state)
    sections[key] = bool(value)
    return bool(value)


def toggle(state, key):
    """Flip and persist the expanded state for ``key``."""
    return set_open(state, key, not is_open(state, key))


def _zero_like(value):
    if isinstance(value, pygame.Rect):
        return pygame.Rect(0, 0, 0, 0)
    if isinstance(value, tuple):
        return tuple(_zero_like(item) for item in value)
    return value


def clear_rects(state, keys):
    """Clear visible hit areas owned by a collapsed section."""
    for key in keys:
        if key not in state:
            continue
        value = state[key]
        if isinstance(value, pygame.Rect):
            state[key] = pygame.Rect(0, 0, 0, 0)
        elif isinstance(value, dict):
            for inner_key, inner in list(value.items()):
                value[inner_key] = _zero_like(inner)
        elif isinstance(value, list):
            for index, inner in enumerate(value):
                value[index] = _zero_like(inner)


def clear_section(state, key):
    """Clear a registered section's body rects."""
    clear_rects(state, SECTION_RECT_KEYS.get(key, ()))


def draw_section_header(screen, font, mouse_pos, state, x, y, key, label,
                        width=None, count=None, height=None):
    """Draw a clickable header and return ``(next_y, expanded)``.

    The header is a full-width 24px row followed by ``MIN_ELEMENT_SPACING``.
    It is published in ``panel_section_rects`` so the shared spacing validator
    treats it exactly like any other independent panel element.
    """
    sections, rects = _section_map(state)
    w = width if width is not None else (cfg.PANEL_W - 40)
    h = height if height is not None else 24
    rect = pygame.Rect(x, y, w, h)
    rects[key] = rect
    publish_rect(state, "panel_section_rects", rects)

    expanded = bool(sections.get(key, DEFAULT_OPEN.get(key, True)))
    caret = "▾" if expanded else "▸"
    text = f"{caret} {label}"
    if count:
        text += f" ({count})"
    hover = rect.collidepoint(mouse_pos)
    bg = BUTTON_HOVER if hover else SURFACE_SUBTLE
    pygame.draw.rect(screen, bg, rect, border_radius=RADIUS_MD)
    pygame.draw.rect(screen, BORDER_SUBTLE, rect, 1, border_radius=RADIUS_MD)
    screen.blit(font.render(text, True, TEXT_PRIMARY), (rect.x + 8, rect.centery - font.get_height() // 2))
    return rect.bottom + MIN_ELEMENT_SPACING, expanded
