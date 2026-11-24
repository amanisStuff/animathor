"""View: the top menu bar, its dropdowns and the shortcuts overlay.

The menu tree is declared once in :data:`MENUS`; item keys are handed back to
the controller, which owns the actions. Rendering reuses the same button/card
primitives as the rest of the chrome so the bar cannot drift from the rest of
the UI.
"""

import pygame

import command_ids as CMD

import config as cfg
from config import *

from views.icons import draw_tooltip
from views.widgets import draw_button, draw_card


# Each menu is ``(key, label, items)``. An item is
# ``(key, label, icon_name_or_None, shortcut_or_None)``; ``None`` marks a
# separator. The shortcut is shown right-aligned in the dropdown and becomes
# part of the hover tooltip. Item keys map to run_menu_action() in the
# controller.
MENUS = (
    ("file", "File", (
        (CMD.NEW, "New", None, "Ctrl+N"),
        None,
        (CMD.OPEN, "Open...", "open", "Ctrl+O"),
        (CMD.IMPORT_SVG, "Import SVG...", "import", "Ctrl+I"),
        (CMD.SAVE, "Save", "save", "Ctrl+S"),
        (CMD.SAVE_AS, "Save As...", "save", "Ctrl+Shift+S"),
        None,
        (CMD.EXPORT, "Export...", "export", "Ctrl+Shift+E"),
        None,
        (CMD.QUIT, "Quit", None, None),
    )),
    ("edit", "Edit", (
        (CMD.UNDO, "Undo", "undo", "Ctrl+Z"),
        (CMD.REDO, "Redo", "redo", "Ctrl+Y"),
        None,
        (CMD.SELECT_ALL, "Select All", None, "Ctrl+A"),
        (CMD.DUPLICATE, "Duplicate", "copy", "Ctrl+D"),
        None,
        (CMD.GROUP, "Group", None, "Ctrl+G"),
        (CMD.UNGROUP, "Ungroup", None, "Ctrl+Shift+G"),
        None,
        (CMD.SYMBOL_CREATE, "Create Symbol", None, None),
        (CMD.SYMBOL_INSERT, "Insert Symbol Instance", None, None),
        (CMD.SYMBOL_UPDATE, "Update Symbol Instances", None, None),
        (CMD.SYMBOL_DETACH, "Detach Symbol", None, None),
        None,
        (CMD.SHAPE_STATE_SAVE, "Save Shape State", None, None),
        (CMD.SHAPE_STATE_INSERT, "Insert Shape State", None, None),
        (CMD.SHAPE_STATE_DELETE, "Delete Shape State", None, None),
        None,
        (CMD.WORKSPACE, "Workspace", None, None),
        None,
        (CMD.COPY, "Copy", "copy", "Ctrl+C"),
        (CMD.CUT, "Cut", None, "Ctrl+X"),
        (CMD.PASTE, "Paste", None, "Ctrl+V"),
        None,
        (CMD.DELETE, "Delete", None, "Del"),
        (CMD.CYCLE_SUBMODE, "Cycle Selection Mode", None, "N"),
    )),
    ("view", "View", (
        (CMD.FIT, "Fit to Content", None, "Ctrl+0"),
        (CMD.ACTUAL_SIZE, "Actual Size", None, "Ctrl+1"),
        None,
        (CMD.TOGGLE_PANEL, "Toggle Properties Panel", None, None),
        (CMD.TOGGLE_SNAP, "Toggle Snapping", "snap", "S"),
        (CMD.TOGGLE_GRID, "Show Grid", None, "#"),
        (CMD.TOGGLE_RULERS, "Show Rulers & Guides", None, "Ctrl+R"),
        (CMD.TOGGLE_GRID_SNAP, "Snap to Grid", None, None),
        (CMD.CLEAR_GUIDES, "Clear Guides", None, None),
        None,
        (CMD.ARTBOARD_ADD, "Add Artboard (Canvas)", None, None),
        (CMD.ARTBOARD_FIT_SELECTION, "Artboard Fit to Selection", None, None),
        (CMD.ARTBOARD_REMOVE, "Remove Active Artboard", None, None),
        (CMD.ARTBOARD_NEXT, "Next Artboard", None, None),
    )),
    ("tools", "Tools", (
        (CMD.TOOL_PEN, "Pen", "pen", "B"),
        (CMD.TOOL_SELECT, "Select / Move", "select", "V"),
        (CMD.TOOL_EYEDROPPER, "Eyedropper", "eyedropper", "I"),
        None,
        (CMD.TOOL_ERASER, "Eraser", "eraser", "E"),
        (CMD.TOOL_BUCKET, "Bucket Fill", "bucket", "F"),
        (CMD.TOOL_CUTTER, "Split Curve", "cutter", "C"),
    )),
    ("help", "Help", (
        (CMD.SHORTCUTS, "Keyboard Shortcuts...", None, None),
    )),
)

# Compact reference shown by Help > Keyboard Shortcuts.
SHORTCUTS = (
    ("File", "Save / Save As / Open", "Ctrl+S / Ctrl+Shift+S / Ctrl+O"),
    ("File", "Export image", "Ctrl+Shift+E"),
    ("Edit", "Undo / Redo", "Ctrl+Z / Ctrl+Y (Ctrl+Shift+Z)"),
    ("Edit", "Select All / Duplicate", "Ctrl+A / Ctrl+D"),
    ("Edit", "Copy / Cut / Paste", "Ctrl+C / Ctrl+X / Ctrl+V"),
    ("Edit", "Group / Ungroup", "Ctrl+G / Ctrl+Shift+G"),
    ("Edit", "Delete selection", "Delete / Backspace"),
    ("View", "Fit / Actual size", "Ctrl+0 / Ctrl+1"),
    ("View", "Toggle snapping", "S"),
    ("View", "Grid / Rulers / Snap to grid", "# / Ctrl+R / menu"),
    ("Canvas", "Drag from ruler to add a guide", "release on canvas"),
    ("Tools", "Pen / Select / Eyedropper", "B / V / I"),
    ("Tools", "Eraser / Fill / Split", "E / F / C"),
    ("Canvas", "Pan / Zoom", "Space+drag or MMB / wheel"),
)


def draw_menu_bar(screen, font, mouse_pos, menu_open, state=None):
    """Draw the bar plus the open dropdown.

    Returns ``(label_rects, item_rects)`` -- clickable rects for the top-level
    labels and for the items of whichever menu is open. The controller keeps
    these between frames and hit-tests them on the next MOUSEBUTTONDOWN.
    """
    bar = pygame.Rect(0, 0, cfg.WIDTH, TOP_BAR_H)
    pygame.draw.rect(screen, SURFACE_SUBTLE, bar)
    pygame.draw.line(screen, PANEL_BORDER, (0, TOP_BAR_H - 1),
                     (cfg.WIDTH, TOP_BAR_H - 1), BORDER_WIDTH)

    label_rects = {}
    x = SPACE_SM
    # Workspace switcher: Draw <-> Library (top bar).
    workspace = "library" if (state is not None and state.get("workspace") == "library") else "draw"
    toggle_rect = pygame.Rect(x, 2, 92, TOP_BAR_H - 4)
    draw_button(screen, toggle_rect, workspace.capitalize(), font, mouse_pos=mouse_pos,
                active=(state is not None and state.get("workspace") == "library"))
    if state is not None:
        state["workspace_rect"] = toggle_rect
    x = toggle_rect.right + SPACE_MD
    for key, label, _items in MENUS:
        text_w = font.render(label, True, TEXT_PRIMARY).get_width()
        rect = pygame.Rect(x, 2, text_w + SPACE_XL, TOP_BAR_H - 4)
        label_rects[key] = rect
        draw_button(screen, rect, label, font, mouse_pos=mouse_pos,
                    active=(menu_open == key), radius=RADIUS_SM)
        x = rect.right + SPACE_XS

    item_rects = {}
    menu_tip = None
    for key, _label, items in MENUS:
        if menu_open != key:
            continue
        anchor = label_rects[key]
        height = sum(MENU_SEPARATOR_H if item is None else CONTROL_H for item in items)
        drop = pygame.Rect(anchor.x, TOP_BAR_H, MENU_WIDTH, height)
        draw_card(screen, drop, radius=RADIUS_LG)
        y = drop.y
        for item in items:
            if item is None:
                my = y + MENU_SEPARATOR_H // 2
                pygame.draw.line(screen, BORDER_SUBTLE,
                                 (drop.x + SPACE_SM, my), (drop.right - SPACE_SM, my),
                                 BORDER_WIDTH)
                y += MENU_SEPARATOR_H
                continue
            ikey, ilabel, icon, shortcut = item
            rect = pygame.Rect(drop.x, y, drop.w, CONTROL_H)
            item_rects[ikey] = rect
            hovered = draw_button(screen, rect, ilabel, font, mouse_pos=mouse_pos,
                                  icon_name=icon, icon_size=ICON_SIZE, radius=RADIUS_XS)
            if shortcut:
                hint = font.render(shortcut, True,
                                   PRIMARY if hovered else TEXT_SECONDARY)
                screen.blit(hint, (rect.right - SPACE_SM - hint.get_width(),
                                   rect.centery - hint.get_height() // 2))
            if hovered:
                menu_tip = f"{ilabel} ({shortcut})" if shortcut else ilabel
            y += CONTROL_H

    if menu_tip:
        draw_tooltip(screen, mouse_pos, menu_tip, font=font)
    return label_rects, item_rects


def draw_shortcuts_overlay(screen, font, small_font):
    """Draw the keyboard-shortcut reference card and return its rect."""
    width = min(cfg.WIDTH - SPACE_LG * 2, 600)
    row_h = CONTROL_H
    height = len(SHORTCUTS) * row_h + CONTROL_H + SPACE_MD * 2
    card = pygame.Rect((cfg.WIDTH - width) // 2, (cfg.HEIGHT - height) // 2,
                       width, height)
    draw_card(screen, card, radius=RADIUS_XL)

    title = font.render("Keyboard Shortcuts", True, TEXT_PRIMARY)
    screen.blit(title, (card.x + SPACE_MD, card.y + SPACE_SM))
    pygame.draw.line(screen, BORDER_SUBTLE,
                     (card.x + SPACE_MD, card.y + CONTROL_H),
                     (card.right - SPACE_MD, card.y + CONTROL_H), BORDER_WIDTH)

    y = card.y + CONTROL_H + SPACE_SM
    for group, action, shortcut in SHORTCUTS:
        screen.blit(small_font.render(group, True, TEXT_SECONDARY),
                    (card.x + SPACE_MD, y + SPACE_XS // 2))
        screen.blit(small_font.render(action, True, TEXT_PRIMARY),
                    (card.x + SPACE_MD + 70, y + SPACE_XS // 2))
        keys = small_font.render(shortcut, True, PRIMARY)
        screen.blit(keys, (card.right - SPACE_MD - keys.get_width(), y + SPACE_XS // 2))
        y += row_h
    return card


EXPORT_FORMATS = ("png", "svg", "pdf", "eps", "jpg", "webp")
EXPORT_SCALES = (1.0, 2.0, 3.0, 4.0)
EXPORT_DPIS = (72, 96, 150, 300, 600)


def draw_export_dialog(screen, font, small_font, mouse_pos, state):
    """Draw export options dialog; writes hit rects to state['export_dialog_rects']."""
    fmt = str(state.get("export_dialog_format", "png") or "png").lower()
    if fmt not in EXPORT_FORMATS:
        fmt = "png"
    scale = float(state.get("export_scale", 1.0) or 1.0)
    if scale not in EXPORT_SCALES:
        scale = min(EXPORT_SCALES, key=lambda s: abs(s - scale))
    dpi = int(state.get("export_dpi", 300) or 300)
    if dpi not in EXPORT_DPIS:
        dpi = min(EXPORT_DPIS, key=lambda d: abs(d - dpi))

    width = min(cfg.WIDTH - SPACE_LG * 2, 420)
    row_h = CONTROL_H + SPACE_XS
    height = CONTROL_H + SPACE_MD + row_h * 3 + SPACE_LG + CONTROL_H + SPACE_MD
    card = pygame.Rect((cfg.WIDTH - width) // 2, (cfg.HEIGHT - height) // 2, width, height)
    draw_card(screen, card, radius=RADIUS_XL)

    x = card.x + SPACE_MD
    inner_w = card.w - SPACE_MD * 2
    y = card.y + SPACE_SM
    title = font.render("Export", True, TEXT_PRIMARY)
    screen.blit(title, (x, y))
    pygame.draw.line(screen, BORDER_SUBTLE,
                     (x, card.y + CONTROL_H), (card.right - SPACE_MD, card.y + CONTROL_H), BORDER_WIDTH)
    y = card.y + CONTROL_H + SPACE_SM

    rects = {"card": card}

    def _stepper(label, value_text, prev_key, next_key):
        nonlocal y
        screen.blit(small_font.render(label, True, TEXT_SECONDARY), (x, y + 6))
        btn_w = 34
        value_w = inner_w - 110 - btn_w * 2 - SPACE_XS * 2
        vx = x + 110
        prev_r = pygame.Rect(vx, y, btn_w, CONTROL_H)
        val_r = pygame.Rect(vx + btn_w + SPACE_XS, y, value_w, CONTROL_H)
        next_r = pygame.Rect(val_r.right + SPACE_XS, y, btn_w, CONTROL_H)
        rects[prev_key] = prev_r
        rects[next_key] = next_r
        draw_button(screen, prev_r, "<", small_font, mouse_pos=mouse_pos, radius=RADIUS_SM)
        draw_button(screen, val_r, value_text, small_font, mouse_pos=mouse_pos, radius=RADIUS_SM)
        draw_button(screen, next_r, ">", small_font, mouse_pos=mouse_pos, radius=RADIUS_SM)
        y += row_h

    _stepper("Format", fmt.upper(), "format_prev", "format_next")
    _stepper("Scale", f"{int(scale)}x" if float(scale).is_integer() else f"{scale:g}x", "scale_prev", "scale_next")
    _stepper("DPI", f"{dpi}", "dpi_prev", "dpi_next")

    y += SPACE_SM
    btn_w = (inner_w - SPACE_SM) // 2
    cancel_r = pygame.Rect(x, y, btn_w, CONTROL_H)
    export_r = pygame.Rect(x + btn_w + SPACE_SM, y, btn_w, CONTROL_H)
    rects["cancel"] = cancel_r
    rects["export"] = export_r
    draw_button(screen, cancel_r, "Cancel", small_font, mouse_pos=mouse_pos, radius=RADIUS_MD)
    draw_button(screen, export_r, "Export...", small_font, mouse_pos=mouse_pos, radius=RADIUS_MD,
                active=True)
    state["export_dialog_rects"] = rects
    return card
