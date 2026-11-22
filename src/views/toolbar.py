"""View: left tool toolbar and bottom shape toolbar.

All chrome is drawn with the shared primitives from :mod:`views.widgets`,
so the toolbars use the same radii, colours and interaction states as the
properties panel and popovers.
"""

import pygame

import config as cfg
from config import *

from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip
from views.widgets import draw_button, draw_card, draw_color_swatch

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
    pygame.draw.line(screen, PANEL_BORDER, (LEFT_BAR_W - 1, top), (LEFT_BAR_W - 1, cfg.HEIGHT), BORDER_WIDTH)

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
        hovered = draw_button(screen, btn.rect, "", None, mouse_pos=mouse_pos,
                              active=active, enabled=enabled,
                              icon_name=_ICON_FOR[kind], icon_size=24,
                              radius=RADIUS_LG)
        if hovered and kind in TOOL_TIPS:
            tip = TOOL_TIPS[kind]
    if tip:
        draw_tooltip(screen, mouse_pos, tip)


# Shape key -> bundled icon name (mirrors the old sidebar Shape palette).
_SHAPE_ICON = {
    "freehand": "shape_free",
    "pen": "pen",
    "line": "shape_line",
    "rect": "shape_rect",
    "square": "shape_square",
    "ellipse": "shape_ellipse",
    "circle": "shape_circle",
    "triangle": "shape_triangle",
    "polygon": "shape_polygon",
    "star": "shape_star",
    "eraser": "eraser",
    "cutter": "cutter",
    "bucket": "bucket",
    "text": "text",
}


def draw_bottom_shape_toolbar(screen, fonts, mouse_pos, state):
    """Bottom bar; contents change with the current view/mode."""
    font, font_small, font_title = fonts
    bar_h = getattr(cfg, "BOTTOM_BAR_H", 56)
    bar = pygame.Rect(cfg.CANVAS_X, cfg.HEIGHT - bar_h, cfg.CANVAS_W, bar_h)
    pygame.draw.rect(screen, TOOLBAR_BG, bar)
    pygame.draw.line(screen, PANEL_BORDER, (bar.x, bar.y), (bar.right - 1, bar.y), BORDER_WIDTH_ACTIVE)

    tool_mode = state.get("tool_mode", "draw")
    submode = state.get("selection_submode", "transform")

    rects = {}
    tip = None
    pad, gap = SPACE_MD + SPACE_XS, SPACE_SM

    if tool_mode == "selection":
        if submode == "transform":
            entries = [
                ("mirror_h", "flip_h", "Flip H"),
                ("mirror_v", "flip_v", "Flip V"),
                ("align_left", "align_left", "Left"),
                ("align_hcenter", "align_hcenter", "Center"),
                ("align_right", "align_right", "Right"),
                ("align_top", "align_top", "Top"),
                ("align_vmiddle", "align_vmiddle", "Middle"),
                ("align_bottom", "align_bottom", "Bottom"),
            ]
            n = max(1, len(entries))
            bw = (bar.w - pad * 2 - gap * (n - 1)) // n
            has_sel = bool(state.get("selected_strokes"))
            for i, (key, icon_name, label) in enumerate(entries):
                r = pygame.Rect(bar.x + pad + i * (bw + gap), bar.y + SPACE_SM, bw, bar.h - SPACE_SM * 2)
                rects[key] = r
                hovered = draw_button(screen, r, label, font_small, mouse_pos=mouse_pos,
                                      enabled=has_sel, icon_name=icon_name,
                                      icon_size=ICON_SIZE, radius=RADIUS_LG)
                if hovered:
                    tip = BUTTON_TIPS.get(icon_name, label)
        elif submode == "nodes":
            msg = font_small.render("Nodes view: drag nodes and handles on the canvas", True, MUTED_COLOR)
            screen.blit(msg, msg.get_rect(midleft=(bar.x + pad, bar.centery)))
        elif submode == "curve":
            msg = font_small.render("Curve view: select curves and use Tool options to split, join, or redraw", True, MUTED_COLOR)
            screen.blit(msg, msg.get_rect(midleft=(bar.x + pad, bar.centery)))
        else:
            msg = font_small.render("Selection view", True, MUTED_COLOR)
            screen.blit(msg, msg.get_rect(midleft=(bar.x + pad, bar.centery)))
        state["draw_shape_rects"] = rects
        state["shape_menu_key"] = None
        state["shape_menu_rect"] = pygame.Rect(0, 0, 0, 0)
        state["shape_menu_item_rects"] = {}
        if tip:
            draw_tooltip(screen, mouse_pos, tip)
        return

    # Draw mode: shapes + drawing tools
    shape = state.get("draw_shape", "freehand")
    draw_tool = state.get("draw_tool", "pen")
    entries = list(DRAW_SHAPES) + list(BOTTOM_TOOLS)
    tool_keys = {k for k, _ in BOTTOM_TOOLS}
    shape_families = {
        "rect": ("rect", "square"),
        "ellipse": ("ellipse", "circle"),
    }
    n = max(1, len(entries))
    bw = (bar.w - pad * 2 - gap * (n - 1)) // n
    for i, (key, label) in enumerate(entries):
        r = pygame.Rect(bar.x + pad + i * (bw + gap), bar.y + SPACE_SM, bw, bar.h - SPACE_SM * 2)
        rects[key] = r
        if key in tool_keys:
            active = (draw_tool == key)
        else:
            family = shape_families.get(key, (key,))
            active = (shape in family and draw_tool == "pen")
        open_menu = (state.get("shape_menu_key") == key)
        display_label = label
        icon_key = key
        if key == "rect" and shape == "square":
            display_label = "Square"
            icon_key = "square"
        elif key == "ellipse" and shape == "circle":
            display_label = "Circle"
            icon_key = "circle"
        if key == "eraser":
            # Separate the drawing tools from the shape tools.
            pygame.draw.line(screen, BUTTON_BORDER, (r.x - gap // 2 - 1, bar.y + SPACE_MD),
                             (r.x - gap // 2 - 1, bar.bottom - SPACE_MD), BORDER_WIDTH)
        hovered = draw_button(screen, r, display_label, font_small, mouse_pos=mouse_pos,
                              active=active or open_menu,
                              icon_name=_SHAPE_ICON.get(icon_key), icon_size=ICON_SIZE,
                              radius=RADIUS_LG, show_caret=key in _TOOL_META)
        if hovered:
            tip = f"{BUTTON_TIPS.get(_SHAPE_ICON.get(icon_key), display_label)} - right-click for options"
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

    pad, w, row_h, gap = SPACE_MD, 240, CONTROL_H, SPACE_XS
    sw, sgap = 26, SPACE_SM
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

    draw_card(screen, panel, radius=RADIUS_XL)

    draw_icon(screen, tool_icon, pygame.Rect(x + pad, y + 7, 18, 18),
              color=TEXT_PRIMARY, size=ICON_SIZE)
    screen.blit(font_small.render(tool_name, True, TEXT_PRIMARY), (x + pad + 24, y + 9))
    pygame.draw.line(screen, PANEL_BORDER, (x + pad, y + 30), (x + w - pad, y + 30), BORDER_WIDTH)

    rects = {}
    cy = y + 36
    for row in rows:
        kind = row["kind"]
        if kind == "choice":
            screen.blit(font_small.render(row["label"], True, MUTED_COLOR), (x + pad, cy))
            cy += 20
            items = list(row.get("items", []))
            val = row.get("value")
            labels = {k: lbl for k, lbl in items}
            cur_label = labels.get(val, str(val))
            ck = str(row.get("key", row.get("label", "choice")))
            prev_k = f"choice_prev:{ck}"
            next_k = f"choice_next:{ck}"
            btn_w = 28
            prev_r = pygame.Rect(x + pad, cy, btn_w, 26)
            next_r = pygame.Rect(x + w - pad - btn_w, cy, btn_w, 26)
            mid_r = pygame.Rect(prev_r.right + gap, cy, next_r.left - prev_r.right - gap * 2, 26)
            rects[prev_k] = prev_r
            rects[next_k] = next_r
            draw_button(screen, prev_r, "<", font_small, mouse_pos=mouse_pos, radius=RADIUS_SM)
            draw_button(screen, mid_r, cur_label, font_small, mouse_pos=mouse_pos, radius=RADIUS_SM)
            draw_button(screen, next_r, ">", font_small, mouse_pos=mouse_pos, radius=RADIUS_SM)
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
                draw_color_swatch(screen, rr, col, selected=selected, mouse_pos=mouse_pos)
            nrows = (max(1, len(items)) + sw_per_row - 1) // sw_per_row
            cy += nrows * sw + (nrows - 1) * sgap + gap
        elif kind == "stepper":
            rr = pygame.Rect(x + pad, cy, w - pad * 2, row_h)
            minus = pygame.Rect(rr.right - 62, rr.y + 2, 28, 24)
            plus = pygame.Rect(rr.right - 30, rr.y + 2, 28, 24)
            rects[row["minus"]] = minus
            rects[row["plus"]] = plus
            t = font_small.render(f"{row['label']}: {row['value']}", True, TEXT_PRIMARY)
            screen.blit(t, t.get_rect(midleft=(rr.x, rr.centery)))
            for br, sym in ((minus, "-"), (plus, "+")):
                draw_button(screen, br, sym, font, mouse_pos=mouse_pos, radius=RADIUS_SM)
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
    pygame.draw.line(screen, PANEL_BORDER, (x + pad, cy + 2), (x + w - pad, cy + 2), BORDER_WIDTH)
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
    draw_button(screen, r, f"{label}: {value}", font_small, mouse_pos=mouse_pos,
                active=active, icon_name=icon_name, icon_size=ICON_SIZE,
                radius=RADIUS_MD)


# Per-tool options metadata: tool key -> (display name, bundled icon).
_TOOL_META = {
    "freehand": ("Freehand", "shape_free"),
    "pen": ("Bezier Pen", "pen"),
    "line": ("Line", "shape_line"),
    "rect": ("Rectangle", "shape_rect"),
    "square": ("Square", "shape_square"),
    "ellipse": ("Ellipse", "shape_ellipse"),
    "circle": ("Circle", "shape_circle"),
    "triangle": ("Triangle", "shape_triangle"),
    "polygon": ("Polygon", "shape_polygon"),
    "star": ("Star", "shape_star"),
    "eraser": ("Eraser", "eraser"),
    "cutter": ("Split curve", "cutter"),
    "bucket": ("Bucket fill", "bucket"),
    "selection": ("Selection", "select"),
}


def _tool_option_rows(state, key):
    """Rows describing a tool's options; rendered by draw_shape_context_menu."""
    if key == "freehand":
        return [
            {"kind": "choice", "label": "Fitting", "key": "trace_algorithm",
             "items": list(TRACE_ALGORITHMS),
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
    if key == "rect":
        shape = state.get("draw_shape", "rect")
        return [
            {"kind": "choice", "label": "Shape", "key": "rect_variant",
             "items": [("rect", "Rectangle"), ("square", "Square")],
             "value": shape if shape in ("rect", "square") else "rect"},
            {"kind": "stepper", "label": "Corner radius",
             "value": f"{state.get('corner_radius', 0)}%",
             "minus": "corner_minus", "plus": "corner_plus"},
        ]
    if key == "ellipse":
        shape = state.get("draw_shape", "ellipse")
        return [
            {"kind": "choice", "label": "Shape", "key": "ellipse_variant",
             "items": [("ellipse", "Ellipse"), ("circle", "Circle")],
             "value": shape if shape in ("ellipse", "circle") else "ellipse"},
            {"kind": "stepper", "label": "Segments",
             "value": state.get("ellipse_segments", 4),
             "minus": "segments_minus", "plus": "segments_plus"},
        ]
    if key == "triangle":
        return [{"kind": "choice", "label": "Type", "key": "triangle_variant",
                 "items": list(TRIANGLE_VARIANTS),
                 "value": state.get("draw_shape_variant", "isosceles")}]
    if key == "polygon":
        return [{"kind": "stepper", "label": "Sides",
                 "value": state.get("polygon_sides", 6),
                 "minus": "sides_minus", "plus": "sides_plus"}]
    if key == "star":
        return [
            {"kind": "stepper", "label": "Points",
             "value": state.get("star_points", 5),
             "minus": "spokes_minus", "plus": "spokes_plus"},
            {"kind": "stepper", "label": "Inner",
             "value": f"{int(round(float(state.get('star_inner_ratio', 0.5)) * 100))}%",
             "minus": "inner_minus", "plus": "inner_plus"},
        ]
    if key == "bucket":
        return [{"kind": "swatches", "label": "Fill color", "key": "bucket_color",
                 "items": list(BUCKET_SWATCHES)}]
    if key == "cutter":
        return [{"kind": "stepper", "label": "Gap",
                 "value": f"{state.get('cut_gap', 0)} px",
                 "minus": "gap_minus", "plus": "gap_plus"}]
    return []
