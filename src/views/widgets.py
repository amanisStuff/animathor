"""View: reusable UI widgets and the shared drawing primitives.

Everything drawn by the chrome goes through the helpers here so buttons,
toggles, sliders, cards and tooltips share one visual language. All colours,
radii and spacing come from :mod:`config` theme tokens.
"""

import pygame

from config import *
from views.icons import draw_icon


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def make_fonts():
    """Return the standard ``(body, small, title)`` font tuple."""
    return (
        pygame.font.SysFont(None, FONT_SIZE_BODY),
        pygame.font.SysFont(None, FONT_SIZE_SMALL),
        pygame.font.SysFont(None, FONT_SIZE_TITLE),
    )


def draw_card(screen, rect, fill=SURFACE, border=BORDER_SUBTLE,
              radius=RADIUS_LG, shadow=True, width=BORDER_WIDTH):
    """Draw a raised surface (popover, menu, group box) with an optional shadow."""
    if shadow:
        pygame.draw.rect(screen, SHADOW_COLOR, rect.move(0, SHADOW_OFFSET), border_radius=radius)
    pygame.draw.rect(screen, fill, rect, border_radius=radius)
    if border:
        pygame.draw.rect(screen, border, rect, width=width, border_radius=radius)


def draw_button(screen, rect, label, font, mouse_pos=None, active=False,
                enabled=True, icon_name=None, icon_size=ICON_SIZE,
                radius=RADIUS_MD, align="center", color=None, show_caret=False):
    """Draw a standard button and return ``True`` when the pointer is over it.

    This is the single source of truth for button visuals: hover, active,
    disabled, optional leading icon and the small "right-click for options"
    caret all look identical wherever the button appears.
    """
    hover = enabled and mouse_pos is not None and rect.collidepoint(mouse_pos)
    if not enabled:
        bg, border, text = SURFACE_DISABLED, BORDER_DISABLED, TEXT_DISABLED
    elif active:
        bg, border, text = ACTIVE_BG, PRIMARY, PRIMARY
    else:
        bg, border, text = (HOVER_BG if hover else SURFACE), (PRIMARY if hover else BUTTON_BORDER), TEXT_PRIMARY
    if color is not None:
        text = color

    pygame.draw.rect(screen, bg, rect, border_radius=radius)
    pygame.draw.rect(screen, border, rect,
                     width=BORDER_WIDTH_ACTIVE if active else BORDER_WIDTH,
                     border_radius=radius)

    inset = SPACE_SM
    if icon_name:
        if not label:
            # Icon-only buttons (left toolbar) centre their icon.
            icon_rect = pygame.Rect(0, 0, icon_size, icon_size)
            icon_rect.center = rect.center
        else:
            icon_rect = pygame.Rect(rect.x + inset, rect.centery - icon_size // 2, icon_size, icon_size)
        draw_icon(screen, icon_name, icon_rect, color=text, size=icon_size, enabled=enabled)
        text_x = icon_rect.right + SPACE_XS
    else:
        text_x = rect.x + inset

    if label:
        surface = font.render(label, True, text)
        if align == "center" and not icon_name:
            dest = surface.get_rect(center=rect.center)
        else:
            dest = surface.get_rect(midleft=(text_x, rect.centery))
            if dest.right > rect.right - inset:
                dest.right = rect.right - inset
        screen.blit(surface, dest)

    if show_caret:
        cx, cy = rect.right - SPACE_MD, rect.y + SPACE_SM
        pygame.draw.lines(screen, TEXT_SECONDARY, False,
                          [(cx - SPACE_XS, cy - BORDER_WIDTH),
                           (cx, cy + BORDER_WIDTH_ACTIVE),
                           (cx + SPACE_XS, cy - BORDER_WIDTH)],
                          BORDER_WIDTH_ACTIVE)
    return hover


def draw_toggle(screen, rect, value, font, mouse_pos=None, label_on="ON", label_off="OFF"):
    """Draw a standard ON/OFF toggle chip."""
    hover = mouse_pos is not None and rect.collidepoint(mouse_pos)
    bg = ACTIVE_BG if value else (HOVER_BG if hover else SURFACE)
    border = PRIMARY if value else BUTTON_BORDER
    pygame.draw.rect(screen, bg, rect, border_radius=RADIUS_SM)
    pygame.draw.rect(screen, border, rect, BORDER_WIDTH, border_radius=RADIUS_SM)
    label = label_on if value else label_off
    surface = font.render(label, True, PRIMARY if value else TEXT_SECONDARY)
    screen.blit(surface, surface.get_rect(center=rect.center))


def draw_track(screen, rect, filled_to=None, enabled=True, radius=RADIUS_XS):
    """Draw a slider track (optionally filled from the left) with token colours."""
    track_color = BORDER_SUBTLE if enabled else BORDER_DISABLED
    pygame.draw.rect(screen, track_color, rect, border_radius=radius)
    if filled_to is not None and filled_to > rect.x:
        fill = pygame.Rect(rect.x, rect.y, min(filled_to - rect.x, rect.w), rect.h)
        pygame.draw.rect(screen, PRIMARY if enabled else DISABLED, fill, border_radius=radius)


def to_screen_rgb(color, default=(0.0, 0.0, 0.0)):
    """Convert a normalised 0..1 RGB triplet to a pygame 0..255 RGB tuple.

    One conversion helper keeps every swatch, preview and picker strip mapped
    from the app's float colour space to screen pixels the same way.
    """
    if color is None:
        color = default
    return tuple(int(clamp(c, 0.0, 1.0) * 255) for c in color[:3])


def draw_slider_knob(screen, cx, cy, enabled=True):
    """Draw the slider knob at the shared radius with one fixed colour scheme."""
    pygame.draw.circle(screen, SURFACE if enabled else BORDER_SUBTLE,
                       (cx, cy), SLIDER_KNOB_RADIUS)
    pygame.draw.circle(screen, PRIMARY if enabled else DISABLED, (cx, cy),
                       SLIDER_KNOB_RADIUS, width=BORDER_WIDTH_ACTIVE)


def draw_color_swatch(screen, rect, color, selected=False, mouse_pos=None):
    """Draw a colour swatch (or the slashed 'no fill' tile).

    Shared by the properties panel and the tool-options popover so every
    swatch has identical hover, selection and "no fill" treatment.
    """
    hover = mouse_pos is not None and rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, SURFACE, rect, border_radius=RADIUS_SM)
    inner = rect.inflate(-6, -6)
    if color is None:
        pygame.draw.rect(screen, SURFACE_SUBTLE, inner, border_radius=RADIUS_XS)
        pygame.draw.line(screen, NO_SWATCH_COLOR, inner.topleft, inner.bottomright,
                         BORDER_WIDTH_ACTIVE)
    else:
        pygame.draw.rect(screen, to_screen_rgb(color), inner, border_radius=RADIUS_XS)
    border = ACCENT if (selected or hover) else BUTTON_BORDER
    pygame.draw.rect(screen, border, rect,
                     width=BORDER_WIDTH_ACTIVE if selected else BORDER_WIDTH,
                     border_radius=RADIUS_SM)


def draw_picker_cursor(screen, pos):
    """Dual-ring SV-square cursor, shared by the stroke/fill and bucket pickers."""
    pygame.draw.circle(screen, SURFACE, pos, PICKER_HANDLE_RADIUS, BORDER_WIDTH_ACTIVE)
    pygame.draw.circle(screen, HANDLE_OUTLINE, pos, PICKER_HANDLE_RADIUS, BORDER_WIDTH)


def draw_hue_cursor(screen, x, rect):
    """Hue-bar cursor, shared by the stroke/fill and bucket pickers."""
    cursor = pygame.Rect(x - 3, rect.y - 2, 6, rect.h + 4)
    pygame.draw.rect(screen, SURFACE, cursor, BORDER_WIDTH_ACTIVE, border_radius=RADIUS_XS)
    pygame.draw.rect(screen, HANDLE_OUTLINE, cursor, BORDER_WIDTH, border_radius=RADIUS_XS)


class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def draw(self, screen, font, mouse_pos, active=False, enabled=True, icon_name=None):
        draw_button(screen, self.rect, self.label, font, mouse_pos=mouse_pos,
                    active=active, enabled=enabled, icon_name=icon_name)

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class Slider:
    def __init__(self, x, y, w, min_v, max_v, value):
        self.track = pygame.Rect(x, y, w, 6)
        self.min_v = min_v
        self.max_v = max_v
        self.value = value
        self.dragging = False

    def _value_to_x(self):
        if self.max_v == self.min_v:
            return self.track.x
        t = (self.value - self.min_v) / (self.max_v - self.min_v)
        return int(self.track.x + t * self.track.w)

    def _x_to_value(self, x):
        t = (x - self.track.x) / max(1, self.track.w)
        v = self.min_v + t * (self.max_v - self.min_v)
        return int(round(clamp(v, self.min_v, self.max_v)))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hx = self._value_to_x()
            hy = self.track.centery
            handle_rect = pygame.Rect(hx - 12, hy - 12, 24, 24)
            if handle_rect.collidepoint(event.pos) or self.track.inflate(0, 18).collidepoint(event.pos):
                self.dragging = True
                self.value = self._x_to_value(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._x_to_value(event.pos[0])
            return True
        return False

    def draw(self, screen):
        hx = self._value_to_x()
        draw_track(screen, self.track, filled_to=hx)
        draw_slider_knob(screen, hx, self.track.centery)
