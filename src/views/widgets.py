"""View: reusable UI widgets and the shared drawing primitives.

Everything drawn by the chrome goes through the helpers here so buttons,
toggles, sliders, cards and tooltips share one visual language. All colours,
radii and spacing come from :mod:`config` theme tokens.
"""

import pygame

from config import *
from models.interaction import scrub_value
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
    """Legacy slider knob helper, kept for callers outside the draggable fields."""
    pygame.draw.circle(screen, SURFACE if enabled else BORDER_SUBTLE,
                       (cx, cy), SLIDER_KNOB_RADIUS)
    pygame.draw.circle(screen, PRIMARY if enabled else DISABLED, (cx, cy),
                       SLIDER_KNOB_RADIUS, width=BORDER_WIDTH_ACTIVE)


def drag_modifiers(event=None):
    """Return ``(fine, coarse)`` for a drag event (Ctrl = fine, Shift = coarse)."""
    mod = getattr(event, "mod", None)
    if mod is None:
        mod = pygame.key.get_mods()
    return (bool(mod & (pygame.KMOD_CTRL | pygame.KMOD_META)),
            bool(mod & pygame.KMOD_SHIFT))


def draw_drag_field(screen, rect, value, min_v, max_v, text, font,
                    active=False, enabled=True, mouse_pos=None, label=None):
    """Draw a Blender/Krita style draggable numeric field.

    The whole field is the hit target: its value comes from horizontal drag
    distance, not from the click position. A soft fill shows the position in
    range and the value is rendered as a numeric label inside the field.
    """
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    hover = enabled and mouse_pos is not None and rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, SURFACE_SUNKEN if enabled else SURFACE_DISABLED,
                     rect, border_radius=RADIUS_MD)
    if enabled and max_v > min_v:
        t = clamp((float(value) - min_v) / (max_v - min_v), 0.0, 1.0)
        fill_w = int(rect.w * t)
        if fill_w > 1:
            pygame.draw.rect(screen, ACTIVE_BG,
                             pygame.Rect(rect.x, rect.y, fill_w, rect.h),
                             border_radius=RADIUS_MD)
    border = PRIMARY if (active or hover) and enabled else BUTTON_BORDER
    pygame.draw.rect(screen, border, rect,
                     width=BORDER_WIDTH_ACTIVE if active else BORDER_WIDTH,
                     border_radius=RADIUS_MD)
    vs = font.render(str(text), True,
                     PRIMARY if (enabled and active) else TEXT_DISABLED if not enabled else TEXT_PRIMARY)
    screen.blit(vs, vs.get_rect(right=rect.right - SPACE_SM, centery=rect.centery))
    if label:
        ls = font.render(label, True, TEXT_SECONDARY if enabled else TEXT_DISABLED)
        max_w = max(0, rect.w - vs.get_width() - SPACE_SM * 3)
        while ls.get_width() > max_w and label:
            label = label[:-1]
            ls = font.render(label, True, TEXT_SECONDARY if enabled else TEXT_DISABLED)
        if ls.get_width() <= max_w:
            screen.blit(ls, (rect.x + SPACE_SM, rect.centery - ls.get_height() // 2))


def draw_numeric_field_edit(screen, rect, value, lo, hi, buffer, suffix, font,
                            label=None):
    """Draw the active inline editor over a draggable numeric field.

    The field keeps its normal appearance with an active border; the typed
    buffer replaces the value label and a blinking caret marks the insertion
    point. Drawing is clipped to the published field rect so the 8px spacing
    contract is unchanged.
    """
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    draw_drag_field(screen, rect, value, lo, hi, "", font, active=True)
    text = str(buffer) + str(suffix or "")
    if (pygame.time.get_ticks() // 500) % 2 == 0:
        text += "|"
    surface = font.render(text, True, PRIMARY)
    old_clip = screen.get_clip()
    screen.set_clip(rect)
    try:
        screen.blit(surface, surface.get_rect(
            right=rect.right - SPACE_SM, centery=rect.centery))
        if label:
            label_surface = font.render(label, True, TEXT_SECONDARY)
            max_w = max(0, rect.w - surface.get_width() - SPACE_SM * 3)
            while label_surface.get_width() > max_w and label:
                label = label[:-1]
                label_surface = font.render(label, True, TEXT_SECONDARY)
            if label_surface.get_width() <= max_w:
                screen.blit(label_surface,
                            (rect.x + SPACE_SM, rect.centery - label_surface.get_height() // 2))
    finally:
        screen.set_clip(old_clip)


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


class DragField:
    """Numeric input that changes by dragging horizontally (scrub input).

    Mouse down on the field starts a drag from the *current* value; motion maps
    the horizontal distance to the value range. Ctrl gives fine control, Shift
    coarse control. ``track`` is kept as an alias of ``rect`` for legacy callers.
    """

    def __init__(self, rect, value, min_v, max_v, *, label="", fmt=None,
                 font=None, step=None, enabled=True):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.min_v = min_v
        self.max_v = max_v
        self.label = label
        self.fmt = fmt or (lambda v: str(v))
        self.font = font
        self.step = step
        self.enabled = enabled
        self.dragging = False
        self._start_x = 0
        self._start_value = float(value)

    @property
    def track(self):
        return self.rect

    def _value_to_x(self):
        """Legacy absolute mapping helper; dragging now uses ``scrub_value``."""
        if self.max_v == self.min_v:
            return self.rect.x
        t = (self.value - self.min_v) / (self.max_v - self.min_v)
        return int(self.rect.x + t * self.rect.w)

    def _x_to_value(self, x):
        """Legacy absolute mapping helper; dragging now uses ``scrub_value``."""
        t = (x - self.rect.x) / max(1, self.rect.w)
        v = self.min_v + t * (self.max_v - self.min_v)
        return int(round(clamp(v, self.min_v, self.max_v)))

    def display_text(self):
        return self.fmt(self.value)

    def begin_drag(self, pos):
        if not self.enabled or self.rect.w <= 0:
            return False
        self.dragging = True
        self._start_x = pos[0]
        self._start_value = float(self.value)
        return True

    def move_drag(self, pos, event=None):
        if not self.dragging:
            return False
        fine, coarse = drag_modifiers(event)
        self.value = scrub_value(
            self._start_value, self.min_v, self.max_v, self.rect.w,
            self._start_x, pos[0], step=self.step, fine=fine, coarse=coarse,
        )
        return True

    def end_drag(self):
        if not self.dragging:
            return False
        self.dragging = False
        return True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return self.begin_drag(event.pos)
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            return self.move_drag(event.pos, event)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            return self.end_drag()
        return False

    def draw(self, screen, font=None, mouse_pos=None):
        draw_drag_field(
            screen, self.rect, self.value, self.min_v, self.max_v,
            self.display_text(), font or self.font or make_fonts()[1],
            active=self.dragging, enabled=self.enabled,
            mouse_pos=mouse_pos, label=self.label,
        )


class Slider(DragField):
    """Backward-compatible constructor for the draggable numeric field."""

    def __init__(self, x, y, w, min_v, max_v, value):
        integral = all(isinstance(v, int) for v in (min_v, max_v, value))
        super().__init__(
            pygame.Rect(x, y, w, DRAG_FIELD_H), value, min_v, max_v,
            step=1 if integral else None,
            fmt=lambda v: str(int(round(v))) if integral else str(v),
        )

