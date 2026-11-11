import math
import sys

try:
    import cairo  # pycairo (often bundles Cairo on Windows)
    CAIRO_BACKEND = "pycairo"
except Exception:
    import cairocffi as cairo  # type: ignore
    CAIRO_BACKEND = "cairocffi"

import pygame

from bezier import stroke_to_beziers

CANVAS_W, HEIGHT = 1000, 700
PANEL_W = 280
WIDTH = CANVAS_W + PANEL_W
BG_COLOR = (1.0, 1.0, 1.0)
STROKE_COLOR = (0.1, 0.1, 0.15)
STROKE_WIDTH = 3.0
ACTIVE_COLOR = (0.2, 0.4, 0.9)

PANEL_BG = (245, 247, 250)
PANEL_BORDER = (210, 215, 225)
TEXT_COLOR = (30, 35, 45)
MUTED_COLOR = (90, 100, 115)
BUTTON_BG = (255, 255, 255)
BUTTON_HOVER = (232, 238, 248)
BUTTON_BORDER = (180, 190, 205)
ACCENT = (60, 120, 220)


def make_cairo_surface(width, height):
    # ARGB32 in cairo is native-endian; on little-endian it's BGRA in memory.
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    return surface


def draw_scene(cairo_surface, strokes, active_stroke=None):
    ctx = cairo.Context(cairo_surface)
    # Background
    ctx.set_source_rgb(*BG_COLOR)
    ctx.paint()

    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    # Finished strokes as fitted Bezier curves
    for stroke in strokes:
        if not stroke:
            continue
        ctx.new_path()
        ctx.set_source_rgb(*STROKE_COLOR)
        ctx.set_line_width(STROKE_WIDTH)
        p0 = stroke[0][0]
        ctx.move_to(p0[0], p0[1])
        for _, c1, c2, p3 in stroke:
            ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
        ctx.stroke()

        # Draw control handles lightly to show Bezier structure
        ctx.set_source_rgba(0.9, 0.3, 0.2, 0.35)
        ctx.set_line_width(1.0)
        for p0, c1, c2, p3 in stroke:
            ctx.move_to(p0[0], p0[1])
            ctx.line_to(c1[0], c1[1])
            ctx.move_to(p3[0], p3[1])
            ctx.line_to(c2[0], c2[1])
        ctx.stroke()
        for p0, c1, c2, p3 in stroke:
            for pt in (p0, c1, c2, p3):
                ctx.arc(pt[0], pt[1], 2.0, 0, 2 * math.pi)
                ctx.fill()

    # Active/raw stroke preview
    if active_stroke and len(active_stroke) >= 2:
        ctx.set_source_rgb(*ACTIVE_COLOR)
        ctx.set_line_width(2.0)
        ctx.new_path()
        ctx.move_to(active_stroke[0][0], active_stroke[0][1])
        for x, y in active_stroke[1:]:
            ctx.line_to(x, y)
        ctx.stroke()

    cairo_surface.flush()


def surface_to_pygame(cairo_surface):
    width = cairo_surface.get_width()
    height = cairo_surface.get_height()
    buf = cairo_surface.get_data()
    try:
        data = buf.tobytes()
    except Exception:
        data = bytes(buf)
    # Cairo ARGB32 is premultiplied BGRA on little-endian; good enough for display.
    return pygame.image.frombuffer(data, (width, height), "BGRA")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def draw(self, screen, font, mouse_pos):
        hover = self.rect.collidepoint(mouse_pos)
        color = BUTTON_HOVER if hover else BUTTON_BG
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, BUTTON_BORDER, self.rect, width=1, border_radius=6)
        txt = font.render(self.label, True, TEXT_COLOR)
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


def draw_panel(screen, fonts, mouse_pos, max_points, stroke_count, buttons, slider):
    font, font_small, font_title = fonts
    panel_rect = pygame.Rect(CANVAS_W, 0, PANEL_W, HEIGHT)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    pygame.draw.line(screen, PANEL_BORDER, (CANVAS_W, 0), (CANVAS_W, HEIGHT), 2)

    x = CANVAS_W + 20
    y = 20

    title = font_title.render("Controls", True, TEXT_COLOR)
    screen.blit(title, (x, y))
    y += 42

    # Max points control
    label = font.render("Max points / curve", True, TEXT_COLOR)
    screen.blit(label, (x, y))
    y += 26
    val = font_title.render(str(max_points), True, ACCENT)
    screen.blit(val, (x, y - 2))
    hint = font_small.render("(2 - 500)", True, MUTED_COLOR)
    screen.blit(hint, (x + val.get_width() + 10, y + 4))
    y += 34

    slider.track.topleft = (x, y)
    slider.draw(screen)
    y += 28

    for b in buttons["max"]:
        b.rect.topleft = (x + (0 if b.label == "-" else 70), y)
        b.draw(screen, font, mouse_pos)
    y += 54

    # Actions
    label2 = font.render("Actions", True, TEXT_COLOR)
    screen.blit(label2, (x, y))
    y += 30
    for i, b in enumerate(buttons["actions"]):
        b.rect.topleft = (x, y + i * 44)
        b.draw(screen, font, mouse_pos)
    y += len(buttons["actions"]) * 44 + 18

    # Stats and help
    stats = font.render("Strokes: %d" % stroke_count, True, TEXT_COLOR)
    screen.blit(stats, (x, y))
    y += 28
    stats2 = font_small.render("Cairo backend: %s" % CAIRO_BACKEND, True, MUTED_COLOR)
    screen.blit(stats2, (x, y))
    y += 30

    help_lines = [
        "Draw: left-drag on canvas",
        "Shortcuts: Ctrl+Z undo, C clear",
        "Max pts: [ / ] or - / +",
        "Esc: quit",
        "",
        "Each stroke is simplified and",
        "fitted to cubic Bezier curves",
        "rendered with Cairo 2D.",
    ]
    for line in help_lines:
        txt = font_small.render(line, True, MUTED_COLOR)
        screen.blit(txt, (x, y))
        y += 20


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Cairo Vector Draw - strokes to Bezier curves")
    clock = pygame.time.Clock()

    cairo_surface = make_cairo_surface(CANVAS_W, HEIGHT)
    strokes = []  # list of list[(p0,c1,c2,p3)]
    current_points = []
    drawing = False
    max_points_per_curve = 50  # max simplified points per stroke used for Bezier fitting

    font = pygame.font.SysFont(None, 24)
    font_small = pygame.font.SysFont(None, 20)
    font_title = pygame.font.SysFont(None, 30)
    fonts = (font, font_small, font_title)

    btn_dec = Button((0, 0, 56, 34), "-")
    btn_inc = Button((0, 0, 56, 34), "+")
    btn_undo = Button((0, 0, PANEL_W - 40, 36), "Undo")
    btn_clear = Button((0, 0, PANEL_W - 40, 36), "Clear")
    buttons = {"max": [btn_dec, btn_inc], "actions": [btn_undo, btn_clear]}
    slider = Slider(CANVAS_W + 20, 0, PANEL_W - 40, 2, 500, max_points_per_curve)

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            # Slider consumes drag/click events on it
            if slider.handle_event(event):
                max_points_per_curve = slider.value

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_c:
                    strokes.clear()
                elif event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if strokes:
                        strokes.pop()
                elif event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS):
                    max_points_per_curve = max(2, max_points_per_curve - 1)
                    slider.value = max_points_per_curve
                elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    max_points_per_curve = min(500, max_points_per_curve + 1)
                    slider.value = max_points_per_curve

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if event.pos[0] >= CANVAS_W:
                    # Panel interactions
                    if btn_dec.hit(event.pos):
                        max_points_per_curve = max(2, max_points_per_curve - 1)
                        slider.value = max_points_per_curve
                    elif btn_inc.hit(event.pos):
                        max_points_per_curve = min(500, max_points_per_curve + 1)
                        slider.value = max_points_per_curve
                    elif btn_undo.hit(event.pos):
                        if strokes:
                            strokes.pop()
                    elif btn_clear.hit(event.pos):
                        strokes.clear()
                else:
                    drawing = True
                    current_points = [event.pos]

            elif event.type == pygame.MOUSEMOTION and drawing:
                pos = event.pos
                if pos[0] < CANVAS_W:
                    if not current_points or math.hypot(pos[0] - current_points[-1][0], pos[1] - current_points[-1][1]) >= 2.0:
                        current_points.append(pos)
                else:
                    edge = (CANVAS_W - 1, pos[1])
                    if not current_points or current_points[-1] != edge:
                        current_points.append(edge)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if drawing:
                    drawing = False
                    if len(current_points) >= 2:
                        beziers = stroke_to_beziers(
                            current_points,
                            simplify_epsilon=2.5,
                            tension=0.0,
                            max_points=max_points_per_curve,
                        )
                        if beziers:
                            strokes.append(beziers)
                    current_points = []
                max_points_per_curve = slider.value

        active = current_points if drawing else None
        draw_scene(cairo_surface, strokes, active)
        frame = surface_to_pygame(cairo_surface)
        screen.blit(frame, (0, 0))
        draw_panel(screen, fonts, mouse_pos, max_points_per_curve, len(strokes), buttons, slider)

        pygame.display.flip()
        clock.tick(120)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
