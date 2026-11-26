"""View: right properties panel."""

import math

import pygame

import config as cfg
from config import *

import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))
import views.canvas as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'icons', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))

from panel_rects import visible_rects_from_state  # noqa: E402
from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip  # noqa: E402
from views.widgets import (  # noqa: E402
    draw_button, draw_card, draw_color_swatch as draw_swatch, draw_hue_cursor,
    draw_numeric_field_edit, draw_picker_cursor, draw_slider_knob,
    draw_toggle, draw_track, to_screen_rgb,
)

from views.panel_modes import _draw_panel_draw_mode, _draw_panel_select_mode  # noqa: E402
from views.panel_sections import draw_section_header  # noqa: E402


def draw_panel(screen, fonts, mouse_pos, state):
    font, font_small, font_title = fonts
    top = getattr(cfg, "TOP_BAR_H", 0)
    panel_rect = pygame.Rect(cfg.PANEL_X, top, PANEL_W, cfg.HEIGHT - top)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    pygame.draw.line(screen, PANEL_BORDER, (cfg.PANEL_X, top), (cfg.PANEL_X, cfg.HEIGHT), BORDER_WIDTH_ACTIVE)

    x = cfg.PANEL_X + 20
    y = top + 18 - int(state.get("panel_scroll", 0) or 0)
    tm = state.get("tool_mode", "draw")

    # Section headers are rebuilt every frame. Clear the persistent cache so a
    # header from a previous tool/submode cannot keep a stale hit rect.
    section_rects = state.get("panel_section_rects")
    if isinstance(section_rects, dict):
        section_rects.clear()
    else:
        state["panel_section_rects"] = {}

    # Tooltips are queued while drawing buttons, then rendered on top at the
    # end so later controls never cover them.
    _tips = []

    def _queue_tip(rect, key, text=None):
        if rect.collidepoint(mouse_pos):
            _tips.append(text or BUTTON_TIPS.get(key, ""))

    def _button(rect, label, active=False, enabled=True, icon=None, font_=None,
                radius=RADIUS_MD, show_caret=False):
        """Draw a control through the shared button primitive.

        Using one helper everywhere guarantees identical hover/active/disabled
        states, borders, radii and icon+label layout across the panel.
        """
        return draw_button(screen, rect, label, font_ or font_small,
                           mouse_pos=mouse_pos, active=active, enabled=enabled,
                           icon_name=icon, icon_size=ICON_SIZE, radius=radius,
                           show_caret=show_caret)

    if tm == "draw":
        state["eyedropper_rect"] = pygame.Rect(0, 0, 0, 0)
        title_text = "Tool options"
    elif tm == "eyedropper":
        title_text = "Eyedropper"
    else:
        title_text = "Selection"
    title = font_title.render(title_text, True, TEXT_COLOR)
    screen.blit(title, (x, y))
    y += 36

    if tm == "draw":
        y, help_lines = _draw_panel_draw_mode(screen, fonts, mouse_pos, state, x, y, _button, _queue_tip)
    else:
        y, help_lines = _draw_panel_select_mode(screen, fonts, mouse_pos, state, x, y, _button, _queue_tip)

    if help_lines:
        y, help_open = draw_section_header(
            screen, font_small, mouse_pos, state, x, y, "help", "Help",
            width=PANEL_W - 40)
        if help_open:
            for line in help_lines:
                txt = font_small.render(line, True, MUTED_COLOR)
                screen.blit(txt, (x, y)); y += 18

    # (Layers panel and export settings removed; export options live in the Export dialog.)

    # Track total (unscrolled) content height so the main loop can clamp scrolling.
    _scroll = int(state.get("panel_scroll", 0) or 0)
    content_bottom = y + _scroll
    state["panel_content_bottom"] = content_bottom
    max_scroll = max(0, content_bottom + 24 - cfg.HEIGHT)
    if max_scroll > 0:
        # simple scrollbar on the panel's right edge
        _tb = getattr(cfg, "TOP_BAR_H", 0)
        track = pygame.Rect(cfg.PANEL_X + PANEL_W - 7, _tb + 6, 5, cfg.HEIGHT - _tb - 12)
        pygame.draw.rect(screen, BORDER_SUBTLE, track, border_radius=RADIUS_XS)
        frac = min(1.0, (cfg.HEIGHT - 40) / max(1, content_bottom))
        thumb_h = max(30, int(track.h * frac))
        thumb_y = track.y + int((track.h - thumb_h) * (clamp(_scroll, 0, max_scroll) / max_scroll))
        pygame.draw.rect(screen, DISABLED, pygame.Rect(track.x, thumb_y, track.w, thumb_h), border_radius=RADIUS_XS)

    # Inline numeric editor (double-click on a draggable field). It paints
    # inside the field's published rect, so it adds no new hit targets and
    # cannot violate the 8px spacing/overlap contract.
    edit = state.get("drag_field_edit")
    if isinstance(edit, dict):
        kind = edit.get("kind")
        rect = None
        if kind == "wave":
            entry = (state.get("wave_slider_rects") or {}).get(edit.get("key"))
            if isinstance(entry, (tuple, list)) and len(entry) == 3:
                rect = entry[0]
        else:
            key = {
                "points": "slider", "cut_gap": "cut_gap_slider",
                "stroke_width": "width_slider", "obj_opacity": "obj_opacity_rect",
                "ref_opacity": "ref_opacity_rect", "alpha": "alpha_rect",
            }.get(kind)
            if key is not None:
                value = state.get(key)
                rect = getattr(value, "rect", value)
        if rect is None:
            rect = edit.get("rect")
        if rect is not None and rect.w > 0 and rect.h > 0:
            draw_numeric_field_edit(
                screen, rect, edit.get("value", 0.0), edit.get("lo", 0.0),
                edit.get("hi", 1.0), edit.get("buffer", ""),
                edit.get("suffix", ""), font_small, label=edit.get("label"),
            )

    # Draw the (single) hovered button's name / shortcut tooltip on top.
    if _tips:
        draw_tooltip(screen, mouse_pos, _tips[0])

def draw_panel_toggle(screen, mouse_pos, state):
    """Small tab on the panel edge that collapses/expands the right sidebar."""
    collapsed = bool(state.get("panel_collapsed"))
    top = getattr(cfg, "TOP_BAR_H", 0)
    w, h = 16, 48
    x = (cfg.WIDTH - w) if collapsed else (cfg.PANEL_X - w // 2 - 1)
    y = top + 10
    r = pygame.Rect(x, y, w, h)
    state["panel_toggle_rect"] = r
    hover = r.collidepoint(mouse_pos)
    bg = BUTTON_HOVER if hover else SURFACE_SUBTLE
    pygame.draw.rect(screen, bg, r, border_radius=RADIUS_SM)
    pygame.draw.rect(screen, BUTTON_BORDER, r, 1, border_radius=RADIUS_SM)
    cx, cy = r.centerx, r.centery
    if collapsed:
        pts = [(cx + 2, cy - 6), (cx - 3, cy), (cx + 2, cy + 6)]
    else:
        pts = [(cx - 3, cy - 6), (cx + 2, cy), (cx - 3, cy + 6)]
    pygame.draw.lines(screen, TEXT_COLOR, False, pts, BORDER_WIDTH_ACTIVE)
    if hover:
        draw_tooltip(screen, mouse_pos, "Show sidebar" if collapsed else "Hide sidebar")
    return r

def draw_marker_dropdown(screen, fonts, mouse_pos, state):
    """Dropdown for selecting a start/end marker type."""
    font, font_small, font_title = fonts
    which = state.get("marker_dropdown")
    if which not in ("start", "end"):
        state["marker_dropdown_rect"] = pygame.Rect(0, 0, 0, 0)
        state["marker_dropdown_item_rects"] = {}
        return
    anchor_key = "marker_start_rect" if which == "start" else "marker_end_rect"
    anchor = state.get(anchor_key)
    if not isinstance(anchor, pygame.Rect) or anchor.w <= 0:
        state["marker_dropdown_rect"] = pygame.Rect(0, 0, 0, 0)
        state["marker_dropdown_item_rects"] = {}
        return
    try:
        from models.markers import MARKER_TYPES, get_markers
    except Exception:
        MARKER_TYPES = ("none", "arrow", "triangle", "open_arrow", "circle", "square", "diamond", "bar")
        get_markers = lambda s: {"start": "none", "end": "none"}

    current = "none"
    strokes = state.get("strokes") or []
    sel = sorted(i for i in (state.get("selected_strokes") or set()) if isinstance(i, int) and 0 <= i < len(strokes))
    if sel:
        try:
            current = str(get_markers(strokes[sel[0]]).get(which, "none"))
        except Exception:
            current = "none"

    pad = SPACE_SM
    item_h = CONTROL_H - 2
    item_pitch = item_h + MIN_ELEMENT_SPACING
    w = max(160, anchor.w)
    h = pad * 2 + 22 + len(MARKER_TYPES) * item_pitch - MIN_ELEMENT_SPACING
    occupied = {
        key: rect for key, rect in visible_rects_from_state(state).items()
        if not key.startswith("marker_dropdown")
    }

    def _clear(candidate):
        top = getattr(cfg, "TOP_BAR_H", 0)
        if (candidate.x < 4 or candidate.right > cfg.WIDTH - 4
                or candidate.y < top + 4 or candidate.bottom > cfg.HEIGHT - 4):
            return False
        for rect in occupied.values():
            if candidate.colliderect(rect):
                return False
            h_gap = max(0, rect.left - candidate.right, candidate.left - rect.right)
            v_gap = max(0, rect.top - candidate.bottom, candidate.top - rect.bottom)
            if max(h_gap, v_gap) < MIN_ELEMENT_SPACING:
                return False
        return True

    candidates = (
        (anchor.x, anchor.bottom + MIN_ELEMENT_SPACING),
        (anchor.x, anchor.y - h - MIN_ELEMENT_SPACING),
        (anchor.x - w - MIN_ELEMENT_SPACING, anchor.y),
        (anchor.x - w - MIN_ELEMENT_SPACING, anchor.y - h - MIN_ELEMENT_SPACING),
    )
    x, y = next(
        ((cx, cy) for cx, cy in candidates if _clear(pygame.Rect(cx, cy, w, h))),
        (anchor.x, min(anchor.bottom + MIN_ELEMENT_SPACING, cfg.HEIGHT - h - 4)),
    )
    card = pygame.Rect(x, y, w, h)
    state["marker_dropdown_rect"] = card
    draw_card(screen, card, radius=RADIUS_LG)

    title = "Start marker" if which == "start" else "End marker"
    screen.blit(font_small.render(title, True, TEXT_PRIMARY), (x + pad, y + pad))
    item_rects = {}
    iy = y + pad + 22
    for mt in MARKER_TYPES:
        r = pygame.Rect(x + pad, iy, w - pad * 2, item_h)
        item_rects[str(mt)] = r
        label = str(mt).replace("_", " ").title()
        draw_button(screen, r, label, font_small, mouse_pos=mouse_pos,
                    active=(str(mt) == current), radius=RADIUS_SM)
        iy += item_pitch
    state["marker_dropdown_item_rects"] = item_rects

