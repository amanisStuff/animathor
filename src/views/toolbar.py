"""View: left tool toolbar (uses bundled Lucide icons)."""

import pygame

import config as cfg
from config import *

from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip

# Toolbar button -> bundled icon name and tip key.
_ICON_FOR = {
    "undo": "undo",
    "redo": "redo",
    "draw": "pen",
    "selection": "select",
}

TOOL_TIPS = {
    "undo": BUTTON_TIPS["undo"],
    "redo": BUTTON_TIPS["redo"],
    "draw": BUTTON_TIPS["pen"],
    "selection": BUTTON_TIPS["select"],
}


def draw_left_toolbar(screen, mouse_pos, tool_mode, btn_draw, btn_select, btn_undo=None, btn_redo=None, can_undo=False, can_redo=False):
    top = getattr(cfg, "TOP_BAR_H", 0)
    bar = pygame.Rect(0, top, LEFT_BAR_W, cfg.HEIGHT - top)
    pygame.draw.rect(screen, TOOLBAR_BG, bar)
    pygame.draw.line(screen, PANEL_BORDER, (LEFT_BAR_W - 1, top), (LEFT_BAR_W - 1, cfg.HEIGHT), 2)
    items = []
    if btn_undo is not None:
        items.append(("undo", btn_undo, False, can_undo))
    if btn_redo is not None:
        items.append(("redo", btn_redo, False, can_redo))
    items.extend((
        ("draw", btn_draw, tool_mode == "draw", True),
        ("selection", btn_select, tool_mode == "selection", True),
    ))
    tip = None
    for kind, btn, active, enabled in items:
        hover = btn.rect.collidepoint(mouse_pos) and enabled
        bg = TOOL_ACTIVE if active else (BUTTON_HOVER if hover else (248, 250, 252))
        border = ACCENT if active else BUTTON_BORDER
        if not enabled and kind in ("undo", "redo"):
            bg = (245, 246, 248)
            border = (210, 214, 220)
        pygame.draw.rect(screen, bg, btn.rect, border_radius=8)
        pygame.draw.rect(screen, border, btn.rect, width=2 if active else 1, border_radius=8)
        color = ACCENT if active else (70, 80, 95)
        draw_icon(screen, _ICON_FOR[kind], btn.rect, color=color, size=24, enabled=enabled)
        if hover and kind in TOOL_TIPS:
            tip = TOOL_TIPS[kind]
    # Draw tooltip on top so it is not covered by later buttons.
    if tip:
        draw_tooltip(screen, mouse_pos, tip)


# Shape key -> bundled icon name (mirrors the old sidebar Shape palette).
_SHAPE_ICON = {
    "freehand": "shape_free",
    "line": "shape_line",
    "rect": "shape_rect",
    "square": "shape_square",
    "ellipse": "shape_ellipse",
    "circle": "shape_circle",
    "triangle": "shape_triangle",
    "eraser": "eraser",
    "cutter": "cutter",
    "bucket": "bucket",
}


def draw_bottom_shape_toolbar(screen, fonts, mouse_pos, state):
    """Horizontal palette: shape tools plus eraser/fill, along the bottom."""
    font, font_small, font_title = fonts
    bar_h = getattr(cfg, "BOTTOM_BAR_H", 56)
    bar = pygame.Rect(cfg.CANVAS_X, cfg.HEIGHT - bar_h, cfg.CANVAS_W, bar_h)
    pygame.draw.rect(screen, TOOLBAR_BG, bar)
    pygame.draw.line(screen, PANEL_BORDER, (bar.x, bar.y), (bar.right - 1, bar.y), 2)

    shape = state.get("draw_shape", "freehand")
    draw_tool = state.get("draw_tool", "pen")
    entries = list(DRAW_SHAPES) + list(BOTTOM_TOOLS)
    tool_keys = {k for k, _ in BOTTOM_TOOLS}
    rects = {}
    pad, gap = 12, 6
    n = max(1, len(entries))
    bw = (bar.w - pad * 2 - gap * (n - 1)) // n
    tip = None
    for i, (key, label) in enumerate(entries):
        r = pygame.Rect(bar.x + pad + i * (bw + gap), bar.y + 5, bw, bar.h - 10)
        rects[key] = r
        if key in tool_keys:
            active = (draw_tool == key)
        else:
            active = (shape == key and draw_tool == "pen")
        open_menu = (state.get("shape_menu_key") == key)
        hover = r.collidepoint(mouse_pos)
        if key == "eraser":
            # Separate the drawing tools from the shape tools.
            pygame.draw.line(screen, BUTTON_BORDER, (r.x - gap // 2 - 1, bar.y + 12),
                             (r.x - gap // 2 - 1, bar.bottom - 12), 1)
        bg = TOOL_ACTIVE if active else (BUTTON_HOVER if hover else BUTTON_BG)
        pygame.draw.rect(screen, bg, r, border_radius=7)
        pygame.draw.rect(screen, ACCENT if (active or open_menu) else BUTTON_BORDER, r,
                         2 if (active or open_menu) else 1, border_radius=7)
        icon_name = _SHAPE_ICON.get(key)
        draw_icon(screen, icon_name,
                  pygame.Rect(r.x + 6, r.centery - 10, 20, 20),
                  color=ACCENT if active else TEXT_COLOR, size=20)
        t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
        screen.blit(t, t.get_rect(midleft=(r.x + 32, r.centery)))
        if key in _TOOL_META:
            # Small caret: right-click this button for its options.
            _cx, _cy = r.right - 9, r.y + 7
            pygame.draw.lines(screen, MUTED_COLOR, False,
                              [(_cx - 4, _cy - 1), (_cx, _cy + 2), (_cx + 4, _cy - 1)], 2)
        if hover:
            tip = f"{BUTTON_TIPS.get(icon_name, label)} - right-click for options"
    state["draw_shape_rects"] = rects
    if tip:
        draw_tooltip(screen, mouse_pos, tip)


def draw_shape_context_menu(screen, fonts, mouse_pos, state):
    """Right-click options popup for a shape button, drawn above that button.

    Contents come from ``_tool_option_rows`` so every tool gets its own options,
    plus the shared snapping toggle.
    """
    font, font_small, font_title = fonts
    key = state.get("shape_menu_key")
    if not key:
        state["shape_menu_rect"] = pygame.Rect(0, 0, 0, 0)
        state["shape_menu_item_rects"] = {}
        return

    tool_name, tool_icon = _TOOL_META.get(key, ("Options", "options"))
    rows = _tool_option_rows(state, key)

    pad, w, row_h, gap = 10, 240, 28, 4
    sw, sgap = 26, 6
    sw_per_row = max(1, (w - pad * 2 + sgap) // (sw + sgap))
    body = 0
    for row in rows:
        if row["kind"] == "choice":
            body += 20 + 26 + gap
        elif row["kind"] == "swatches":
            nrows = (max(1, len(row["items"])) + sw_per_row - 1) // sw_per_row
            body += 20 + nrows * sw + (nrows - 1) * sgap + gap
        else:
            body += row_h + gap
    if not rows:
        body = 24 + gap
    h = 32 + body + 8 + (row_h - 2) + 8

    anchor = state.get("shape_menu_anchor") or pygame.Rect(0, 0, 0, 0)
    x = anchor.x
    y = anchor.y - h - 8
    if y < getattr(cfg, "TOP_BAR_H", 28) + 4:
        y = anchor.bottom + 8
    x = max(cfg.CANVAS_X + 4, min(x, cfg.WIDTH - w - 8))
    panel = pygame.Rect(x, y, w, h)
    state["shape_menu_rect"] = panel

    pygame.draw.rect(screen, (222, 226, 234), panel.move(2, 3), border_radius=9)
    pygame.draw.rect(screen, (255, 255, 255), panel, border_radius=8)
    pygame.draw.rect(screen, PANEL_BORDER, panel, 1, border_radius=8)

    draw_icon(screen, tool_icon, pygame.Rect(x + pad, y + 7, 18, 18),
              color=TEXT_COLOR, size=20)
    screen.blit(font_small.render(tool_name, True, TEXT_COLOR), (x + pad + 24, y + 9))
    pygame.draw.line(screen, PANEL_BORDER, (x + pad, y + 30), (x + w - pad, y + 30), 1)

    rects = {}
    cy = y + 36
    for row in rows:
        kind = row["kind"]
        if kind == "choice":
            screen.blit(font_small.render(row["label"], True, MUTED_COLOR), (x + pad, cy))
            cy += 20
            n = max(1, len(row["items"]))
            bw = (w - pad * 2 - gap * (n - 1)) // n
            for i, (item_key, label) in enumerate(row["items"]):
                rr = pygame.Rect(x + pad + i * (bw + gap), cy, bw, 26)
                rects[item_key] = rr
                active = (row["value"] == item_key)
                bg = TOOL_ACTIVE if active else (BUTTON_HOVER if rr.collidepoint(mouse_pos) else BUTTON_BG)
                pygame.draw.rect(screen, bg, rr, border_radius=5)
                pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, rr,
                                 2 if active else 1, border_radius=5)
                t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
                screen.blit(t, t.get_rect(center=rr.center))
            cy += 26 + gap
        elif kind == "swatches":
            screen.blit(font_small.render(row["label"], True, MUTED_COLOR), (x + pad, cy))
            cy += 20
            _cfc = state.get("bucket_fill_color") or (0.45, 0.72, 1.0)
            current = tuple(round(float(c), 3) for c in _cfc[:3])
            items = row["items"]
            for i, col in enumerate(items):
                rr = pygame.Rect(x + pad + (i % sw_per_row) * (sw + sgap),
                                 cy + (i // sw_per_row) * (sw + sgap), sw, sw)
                rects[f"{row['key']}_{i}"] = rr
                selected = (current == tuple(round(c, 3) for c in col))
                bg = BUTTON_HOVER if rr.collidepoint(mouse_pos) else (255, 255, 255)
                pygame.draw.rect(screen, bg, rr, border_radius=5)
                pygame.draw.rect(screen, tuple(int(c * 255) for c in col),
                                 rr.inflate(-6, -6), border_radius=3)
                pygame.draw.rect(screen, ACCENT if selected else BUTTON_BORDER, rr,
                                 2 if selected else 1, border_radius=5)
            nrows = (max(1, len(items)) + sw_per_row - 1) // sw_per_row
            cy += nrows * sw + (nrows - 1) * sgap + gap
        elif kind == "stepper":
            rr = pygame.Rect(x + pad, cy, w - pad * 2, row_h)
            minus = pygame.Rect(rr.right - 62, rr.y + 2, 28, 24)
            plus = pygame.Rect(rr.right - 30, rr.y + 2, 28, 24)
            rects[row["minus"]] = minus
            rects[row["plus"]] = plus
            t = font_small.render(f"{row['label']}: {row['value']}", True, TEXT_COLOR)
            screen.blit(t, t.get_rect(midleft=(rr.x, rr.centery)))
            for br, sym in ((minus, "-"), (plus, "+")):
                bg = BUTTON_HOVER if br.collidepoint(mouse_pos) else BUTTON_BG
                pygame.draw.rect(screen, bg, br, border_radius=5)
                pygame.draw.rect(screen, BUTTON_BORDER, br, 1, border_radius=5)
                s = font.render(sym, True, TEXT_COLOR)
                screen.blit(s, s.get_rect(center=br.center))
            cy += row_h + gap
        else:  # toggle
            rr = pygame.Rect(x + pad, cy, w - pad * 2, row_h - 2)
            rects[row["key"]] = rr
            _toggle_row(screen, font_small, rr, mouse_pos, row["value"],
                        row.get("icon", "options"), row["label"],
                        "ON" if row["value"] else "OFF")
            cy += row_h + gap

    if not rows:
        screen.blit(font_small.render("No options for this tool", True, MUTED_COLOR),
                    (x + pad, cy + 2))
        cy += 24 + gap

    # Shared snapping toggle, available for every drawing tool.
    pygame.draw.line(screen, PANEL_BORDER, (x + pad, cy + 2), (x + w - pad, cy + 2), 1)
    cy += 8
    snap_on = bool(state.get("snap_enabled", True))
    rr = pygame.Rect(x + pad, cy, w - pad * 2, row_h - 2)
    rects["snap"] = rr
    _toggle_row(screen, font_small, rr, mouse_pos, snap_on, "snap", "Snapping",
                "ON" if snap_on else "OFF")

    state["shape_menu_item_rects"] = rects

    tip = None
    for tip_key in ("snap", "boost"):
        if rects.get(tip_key) and rects[tip_key].collidepoint(mouse_pos):
            tip = BUTTON_TIPS.get(tip_key)
            break
    if tip:
        draw_tooltip(screen, mouse_pos, tip)


def _toggle_row(screen, font_small, r, mouse_pos, active, icon_name, label, value):
    bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
    pygame.draw.rect(screen, bg, r, border_radius=6)
    pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r,
                     2 if active else 1, border_radius=6)
    draw_icon(screen, icon_name, pygame.Rect(r.x + 6, r.centery - 10, 20, 20),
              color=ACCENT if active else TEXT_COLOR, size=20)
    t = font_small.render(f"{label}: {value}", True, ACCENT if active else TEXT_COLOR)
    screen.blit(t, t.get_rect(midleft=(r.x + 32, r.centery)))


# Per-tool options metadata: tool key -> (display name, bundled icon).
_TOOL_META = {
    "freehand": ("Freehand", "shape_free"),
    "line": ("Line", "shape_line"),
    "rect": ("Rectangle", "shape_rect"),
    "square": ("Square", "shape_square"),
    "ellipse": ("Ellipse", "shape_ellipse"),
    "circle": ("Circle", "shape_circle"),
    "triangle": ("Triangle", "shape_triangle"),
    "eraser": ("Eraser", "eraser"),
    "cutter": ("Split curve", "cutter"),
    "bucket": ("Bucket fill", "bucket"),
    "selection": ("Selection", "select"),
}


def _tool_option_rows(state, key):
    """Rows describing a tool's options; rendered by draw_shape_context_menu."""
    if key == "freehand":
        return [
            {"kind": "choice", "label": "Fitting", "items": list(TRACE_ALGORITHMS),
             "value": state.get("trace_algorithm", "fit")},
            {"kind": "stepper", "label": "Points / curve",
             "value": state.get("max_points", 4),
             "minus": "points_minus", "plus": "points_plus"},
            {"kind": "toggle", "label": "Boost points", "key": "boost",
             "icon": "boost", "value": bool(state.get("boost_points"))},
        ]
    if key == "line":
        return [
            {"kind": "toggle", "label": "45 deg constrain", "key": "line_constrain",
             "icon": "shape_line", "value": bool(state.get("line_constrain"))},
            {"kind": "toggle", "label": "Arrowhead", "key": "line_arrow",
             "icon": "shape_line", "value": bool(state.get("line_arrow"))},
        ]
    if key in ("rect", "square"):
        return [{"kind": "stepper", "label": "Corner radius",
                 "value": f"{state.get('corner_radius', 0)}%",
                 "minus": "corner_minus", "plus": "corner_plus"}]
    if key in ("ellipse", "circle"):
        return [{"kind": "stepper", "label": "Segments",
                 "value": state.get("ellipse_segments", 4),
                 "minus": "segments_minus", "plus": "segments_plus"}]
    if key == "triangle":
        return [{"kind": "choice", "label": "Type", "items": list(TRIANGLE_VARIANTS),
                 "value": state.get("draw_shape_variant", "isosceles")}]
    if key == "bucket":
        return [{"kind": "swatches", "label": "Fill color", "key": "bucket_color",
                 "items": list(BUCKET_SWATCHES)}]
    if key == "cutter":
        return [{"kind": "stepper", "label": "Gap",
                 "value": f"{state.get('cut_gap', 0)} px",
                 "minus": "gap_minus", "plus": "gap_plus"}]
    return []
