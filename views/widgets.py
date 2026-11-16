"""View: reusable UI widgets."""

import pygame

from config import *


class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def draw(self, screen, font, mouse_pos, active=False):
        hover = self.rect.collidepoint(mouse_pos)
        if active:
            color = TOOL_ACTIVE
            border = ACCENT
            tw = 2
        else:
            color = BUTTON_HOVER if hover else BUTTON_BG
            border = BUTTON_BORDER
            tw = 1
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, border, self.rect, width=tw, border_radius=6)
        txt = font.render(self.label, True, ACCENT if active else TEXT_COLOR)
        screen.blit(txt, txt.get_rect(center=self.rect.center))

    def hit(self, pos):
        return self.rect.collidepoint(pos)

class Slider:
    def __init__(self, x, y, w, min_v, max_v, value):
        self.track = pygame.Rect(x, y, w, 6)
        self.min_v = min_v
        self.max_v = max_v
        self.value = value
        self.dragging = False
        self.handle_r = 8

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
        pygame.draw.rect(screen, (220, 225, 235), self.track, border_radius=3)
        hx = self._value_to_x()
        filled = pygame.Rect(self.track.x, self.track.y, max(0, hx - self.track.x), self.track.h)
        pygame.draw.rect(screen, ACCENT, filled, border_radius=3)
        pygame.draw.circle(screen, (255, 255, 255), (hx, self.track.centery), self.handle_r)
        pygame.draw.circle(screen, ACCENT, (hx, self.track.centery), self.handle_r, width=2)
