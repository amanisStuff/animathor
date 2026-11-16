"""View: left tool toolbar."""

import math

import pygame

import config as cfg
from config import *


def draw_icon(screen, kind, rect, active, enabled=True):
    cx, cy = rect.center
    color = ACCENT if active else (70, 80, 95)
    if not enabled:
        color = (170, 176, 184)
    if kind == "draw":
        # pen nib
        tip = (cx - 8, cy + 9)
        left = (cx - 2, cy - 10)
        right = (cx + 9, cy - 3)
        pygame.draw.polygon(screen, color, [tip, left, right])
        # slit
        slit_color = (255, 255, 255) if active else TOOLBAR_BG
        if not enabled:
            slit_color = (245, 246, 248)
        pygame.draw.line(screen, slit_color, (cx - 4, cy + 1), tip, 2)
        # breather hole
        pygame.draw.circle(screen, slit_color, (cx + 1, cy - 3), 2)
    elif kind == "selection":
        # cursor/arrow (same as former "edit")
        pts = [(cx - 7, cy - 10), (cx - 7, cy + 8), (cx - 2, cy + 3), (cx + 2, cy + 10), (cx + 5, cy + 8), (cx + 1, cy + 1), (cx + 7, cy + 1)]
        pygame.draw.polygon(screen, color, pts)
    elif kind == "undo":
        rect_arc = pygame.Rect(0, 0, 20, 20)
        rect_arc.center = (cx + 2, cy)
        pygame.draw.arc(screen, color, rect_arc, math.radians(40), math.radians(320), 3)
        head = [(cx - 8, cy - 4), (cx - 14, cy + 2), (cx - 6, cy + 6)]
        pygame.draw.polygon(screen, color, head)
    elif kind == "redo":
        rect_arc = pygame.Rect(0, 0, 20, 20)
        rect_arc.center = (cx - 2, cy)
        pygame.draw.arc(screen, color, rect_arc, math.radians(-140), math.radians(140), 3)
        head = [(cx + 8, cy - 4), (cx + 14, cy + 2), (cx + 6, cy + 6)]
        pygame.draw.polygon(screen, color, head)

TOOL_TIPS = {
    "undo": "Undo (Ctrl+Z)",
    "redo": "Redo (Ctrl+Y / Ctrl+Shift+Z)",
    "draw": "Draw / Brush (B)",
    "selection": "Move / Select (V)",
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
    tip_pos = None
    font_tip = pygame.font.SysFont(None, 20)
    for kind, btn, active, enabled in items:
        hover = btn.rect.collidepoint(mouse_pos) and enabled
        bg = TOOL_ACTIVE if active else (BUTTON_HOVER if hover else (248, 250, 252))
        border = ACCENT if active else BUTTON_BORDER
        if not enabled and kind in ("undo", "redo"):
            bg = (245, 246, 248)
            border = (210, 214, 220)
        pygame.draw.rect(screen, bg, btn.rect, border_radius=8)
        pygame.draw.rect(screen, border, btn.rect, width=2 if active else 1, border_radius=8)
        draw_icon(screen, kind, btn.rect, active, enabled=enabled)
        if hover and kind in TOOL_TIPS:
            tip = TOOL_TIPS[kind]
            tip_pos = (btn.rect.right + 8, btn.rect.top + 6)
    # draw tooltip on top
    if tip and tip_pos:
        surf = font_tip.render(tip, True, (30, 35, 45))
        pad = 5
        r = surf.get_rect(topleft=tip_pos)
        r.inflate_ip(pad * 2, pad * 2)
        pygame.draw.rect(screen, (255, 255, 245), r, border_radius=4)
        pygame.draw.rect(screen, (160, 160, 150), r, 1, border_radius=4)
        screen.blit(surf, (r.x + pad, r.y + pad))
