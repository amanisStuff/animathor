"""View: panel mode sections (split for complexity)."""
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
from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip  # noqa: E402
from views.widgets import (  # noqa: E402
    draw_button, draw_card, draw_color_swatch as draw_swatch, draw_drag_field,
    draw_hue_cursor, draw_picker_cursor, draw_toggle,
    to_screen_rgb,
)

from views.panel_select import _draw_panel_select_mode  # noqa: E402
from views.panel_sections import draw_section_header  # noqa: E402

# Cached HSV picker gradients.
_SV_CACHE = {}
_SV_RAMP_CACHE = {}
_HUE_BAR_CACHE = {}


def _draw_wave_graph(screen, rect, poly, color, bg=PLOT_BG, line_w=2, mid=True):
    """Draw a normalized waveform polyline inside rect (x in [0,1], y in [-1,1])."""
    pygame.draw.rect(screen, bg, rect, border_radius=RADIUS_SM)
    if mid:
        pygame.draw.line(screen, PLOT_GRID, (rect.x + 3, rect.centery), (rect.right - 3, rect.centery), BORDER_WIDTH)
    if not poly or len(poly) < 2:
        return
    pad = 3
    hw = max(1, rect.w - 2 * pad)
    hh = max(1, rect.h - 2 * pad)
    pts = []
    for vx, vy in poly:
        px = rect.x + pad + clamp(vx, 0.0, 1.0) * hw
        py = rect.centery - clamp(vy, -1.15, 1.15) * (hh / 2.0)
        pts.append((px, py))
    pygame.draw.lines(screen, color, False, pts, line_w)


def _value_ramp(w, h):
    """Vertical white->black ramp used to turn an S gradient into an S/V square."""
    key = (w, h)
    ramp = _SV_RAMP_CACHE.get(key)
    if ramp is None:
        col = pygame.Surface((1, h))
        for iy in range(h):
            g = int(round(255 * (1.0 - iy / max(1, h - 1))))
            col.set_at((0, iy), (g, g, g))
        ramp = pygame.transform.smoothscale(col, (w, h))
        _SV_RAMP_CACHE[key] = ramp
    return ramp


def _sv_surface(hue, w, h):
    """Saturation/value square for a hue (built from a 1px row + value ramp)."""
    key = (round(float(hue), 1), w, h)
    surf = _SV_CACHE.get(key)
    if surf is None:
        row = pygame.Surface((w, 1))
        for ix in range(w):
            c = hsv_to_rgb(hue, ix / max(1, w - 1), 1.0)
            row.set_at((ix, 0), to_screen_rgb(c))
        surf = pygame.transform.smoothscale(row, (w, h))
        surf.blit(_value_ramp(w, h), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if len(_SV_CACHE) > 24:
            _SV_CACHE.clear()
        _SV_CACHE[key] = surf
    return surf


def _hue_bar_surface(w, h):
    """Full-saturation hue gradient strip."""
    key = (w, h)
    surf = _HUE_BAR_CACHE.get(key)
    if surf is None:
        surf = pygame.Surface((w, h))
        for ix in range(w):
            c = hsv_to_rgb((ix / max(1, w - 1)) * 360.0, 1.0, 1.0)
            pygame.draw.line(surf, to_screen_rgb(c), (ix, 0), (ix, h - 1))
        _HUE_BAR_CACHE[key] = surf
    return surf


def _draw_panel_draw_mode(screen, fonts, mouse_pos, state, x, y, _button, _queue_tip):
    font, font_small, font_title = fonts
    help_lines = []
    state["eyedropper_rect"] = pygame.Rect(0, 0, 0, 0)

    # Tools first: the active tool decides which options are shown below.
    draw_tool = state.get("draw_tool", "pen")
    tool_items = [("pen", "Pen"), ("eraser", "Eraser"), ("bucket", "Fill"), ("cutter", "Split curve")]
    tool_labels = {k: lbl for k, lbl in tool_items}
    screen.blit(font_small.render("Tool", True, MUTED_COLOR), (x, y + 5))
    btn_w = 28
    vx = x + 40
    vw = PANEL_W - 40 - 40 - btn_w * 2 - 8
    pr = pygame.Rect(vx, y, btn_w, 28)
    vr = pygame.Rect(vx + btn_w + 4, y, vw, 28)
    nr = pygame.Rect(vr.right + 4, y, btn_w, 28)
    state["draw_tool_prev_rect"] = pr
    state["draw_tool_next_rect"] = nr
    for _k in ("draw_tool_pen_rect", "draw_tool_eraser_rect", "draw_tool_bucket_rect", "draw_tool_cutter_rect"):
        state[_k] = pygame.Rect(0, 0, 0, 0)
    _button(pr, "<", font_=font_small)
    _button(vr, tool_labels.get(draw_tool, str(draw_tool).title()), icon=draw_tool if draw_tool in tool_labels else None)
    _button(nr, ">", font_=font_small)
    y += 34

    if draw_tool != "pen":
        # Pen-only controls aren't drawn; move their hit areas out of the way.
        state["trace_algo_rects"] = {}
        state["slider"].track.width = 0
        state["buttons"]["boost"].rect = pygame.Rect(0, 0, 0, 0)

    if draw_tool == "pen":
        draw_shape = state.get("draw_shape", "freehand")
        if draw_shape == "pen":
            # Bezier pen: click-place anchors and drag handles (not freehand fitting).
            state["trace_algo_rects"] = {}
            state["slider"].track.width = 0
            state["buttons"]["boost"].rect = pygame.Rect(0, 0, 0, 0)
            screen.blit(font.render("Bezier Pen", True, TEXT_COLOR), (x, y)); y += 24
            for msg in (
                "Click to place anchor points.",
                "Click-drag to pull curve handles.",
                "Click first anchor to close path.",
                "Enter: finish open path.",
                "Esc: cancel path. Backspace: undo point.",
            ):
                screen.blit(font_small.render(msg, True, MUTED_COLOR), (x, y)); y += 18
            y += 8
        else:
            # Points control (freehand fitting)
            screen.blit(font.render("Points / curve", True, TEXT_COLOR), (x, y)); y += 24
            limit = state["BOOST_MAX_POINTS"] if state["boost_points"] else state["NORMAL_MAX_POINTS"]
            hint = font_small.render(f"(2 - {limit})", True, MUTED_COLOR)
            screen.blit(hint, (x, y)); y += 18 + MIN_ELEMENT_SPACING
            pts_field = state["slider"]
            pts_field.track.topleft = (x, y)
            pts_field.track.width = PANEL_W - 40
            pts_field.value = state["max_points"]
            pts_field.max_v = limit
            pts_field.label = "Points"
            pts_field.enabled = True
            pts_field.draw(screen, font_small, mouse_pos)
            y += DRAG_FIELD_H + MIN_ELEMENT_SPACING
            b = state["buttons"]["boost"]
            b.rect.topleft = (x, y)
            b.label = "Boost: ON" if state["boost_points"] else "Boost limit"
            b.draw(screen, font, mouse_pos, active=state["boost_points"])
            draw_icon(screen, "boost", pygame.Rect(b.rect.x + 6, b.rect.centery - 10, 20, 20),
                      color=ACCENT if state["boost_points"] else TEXT_COLOR, size=20)
            _queue_tip(b.rect, "boost"); y += 44

            # Tracing algorithm (per new stroke)
            algo = state.get("trace_algorithm", "fit")
            algo_labels = {k: lbl for k, lbl in TRACE_ALGORITHMS}
            screen.blit(font.render("Tracing", True, TEXT_COLOR), (x, y))
            y += 24
            btn_w = 28
            vx = x
            vw = PANEL_W - 40 - btn_w * 2 - MIN_ELEMENT_SPACING * 2
            pr = pygame.Rect(vx, y, btn_w, 28)
            vr = pygame.Rect(vx + btn_w + MIN_ELEMENT_SPACING, y, vw, 28)
            nr = pygame.Rect(vr.right + MIN_ELEMENT_SPACING, y, btn_w, 28)
            state["trace_algo_prev_rect"] = pr
            state["trace_algo_next_rect"] = nr
            state["trace_algo_rects"] = {}
            _button(pr, "<", font_=font_small)
            _button(vr, algo_labels.get(algo, str(algo)))
            _button(nr, ">", font_=font_small)
            y += 28 + MIN_ELEMENT_SPACING
    elif draw_tool == "eraser":
        screen.blit(font_small.render("Click a curve or edge to erase it.", True, MUTED_COLOR), (x, y)); y += 22
    elif draw_tool == "cutter":
        screen.blit(font_small.render("Drag across curves to split them.", True, MUTED_COLOR), (x, y)); y += 22
        screen.blit(font_small.render("Each crossing adds a node; each half is a curve.", True, MUTED_COLOR), (x, y)); y += 22

        # Optional gap: 0 keeps the stroke connected at the new node.
        screen.blit(font.render("Gap", True, TEXT_COLOR), (x, y)); y += 24
        gap_val = int(state.get("cut_gap", 0) or 0)
        hint = font_small.render("(0 = stays connected)", True, MUTED_COLOR)
        screen.blit(hint, (x, y)); y += 18 + MIN_ELEMENT_SPACING
        _gap_slider = state.get("cut_gap_slider")
        if _gap_slider is not None:
            _gap_slider.track.topleft = (x, y)
            _gap_slider.track.width = PANEL_W - 40
            _gap_slider.value = gap_val
            _gap_slider.label = "Gap"
            _gap_slider.enabled = True
            _gap_slider.draw(screen, font_small, mouse_pos)
            y += DRAG_FIELD_H + MIN_ELEMENT_SPACING
    else:
        screen.blit(font_small.render("Click an enclosed area to fill it.", True, MUTED_COLOR), (x, y)); y += 24

        # Fill color: preset swatches plus an HSV picker for any color.
        screen.blit(font.render("Fill color", True, TEXT_COLOR), (x, y)); y += 22
        col = color_rgb(state.get("bucket_fill_color"), (0.45, 0.72, 1.0))
        h, s, vcol = rgb_to_hsv(*col)
        drag = state.get("bucket_picker_drag")
        if drag != "sv":
            state["bucket_picker_s"] = s
            state["bucket_picker_v"] = vcol
        if drag != "hue":
            state["bucket_picker_h"] = h
        ph = state.get("bucket_picker_h", h)
        ps = state.get("bucket_picker_s", s)
        pv = state.get("bucket_picker_v", vcol)

        # Current color preview + hex
        preview = pygame.Rect(x, y, 30, 30)
        pygame.draw.rect(screen, SURFACE, preview, border_radius=RADIUS_MD)
        pygame.draw.rect(screen, to_screen_rgb(col),
                         preview.inflate(-6, -6), border_radius=RADIUS_SM)
        pygame.draw.rect(screen, BUTTON_BORDER, preview, 1, border_radius=RADIUS_MD)
        screen.blit(font_small.render(rgb_to_hex(col), True, TEXT_COLOR), (x + 38, y + 7))
        y += 38

        # Saturation / value square
        sv_w = PANEL_W - 40
        sv_h = 84
        sv_rect = pygame.Rect(x, y, sv_w, sv_h)
        state["bucket_sv_rect"] = sv_rect
        sv_surf = _sv_surface(ph, sv_w, sv_h)
        screen.blit(sv_surf, sv_rect.topleft)
        pygame.draw.rect(screen, BUTTON_BORDER, sv_rect, 1, border_radius=RADIUS_SM)
        cxp = sv_rect.x + int(clamp(ps, 0.0, 1.0) * (sv_w - 1))
        cyp = sv_rect.y + int((1.0 - clamp(pv, 0.0, 1.0)) * (sv_h - 1))
        draw_picker_cursor(screen, (cxp, cyp))
        y += sv_h + 8

        # Hue bar
        hue_h = 12
        hue_rect = pygame.Rect(x, y, sv_w, hue_h)
        state["bucket_hue_rect"] = hue_rect
        screen.blit(_hue_bar_surface(sv_w, hue_h), hue_rect.topleft)
        pygame.draw.rect(screen, BUTTON_BORDER, hue_rect, 1, border_radius=RADIUS_SM)
        hx = hue_rect.x + int((clamp(ph, 0.0, 360.0) / 360.0) * (sv_w - 1))
        draw_hue_cursor(screen, hx, hue_rect)
        y += hue_h + 10

        # Preset swatches
        sw, sgap = 26, MIN_ELEMENT_SPACING
        per_row = max(1, (PANEL_W - 40 + sgap) // (sw + sgap))
        cur = tuple(round(c, 3) for c in col)
        srects = []
        for i, pcol in enumerate(BUCKET_SWATCHES):
            rr = pygame.Rect(x + (i % per_row) * (sw + sgap),
                             y + (i // per_row) * (sw + sgap), sw, sw)
            srects.append(rr)
            draw_swatch(screen, rr, pcol, cur == tuple(round(c, 3) for c in pcol), mouse_pos)
        state["bucket_swatch_rects"] = srects
        rows_used = (len(BUCKET_SWATCHES) + per_row - 1) // per_row
        y += rows_used * sw + (rows_used - 1) * sgap + MIN_ELEMENT_SPACING

    if draw_tool != "bucket":
        # Hide the fill picker hit-areas when another tool is active.
        state["bucket_sv_rect"] = pygame.Rect(0, 0, 0, 0)
        state["bucket_hue_rect"] = pygame.Rect(0, 0, 0, 0)
        state["bucket_swatch_rects"] = [pygame.Rect(0, 0, 0, 0) for _ in BUCKET_SWATCHES]

    if draw_tool != "cutter":
        # Hide the cutter gap slider when another tool is active.
        _gap_slider = state.get("cut_gap_slider")
        if _gap_slider is not None:
            _gap_slider.track.width = 0

    # Snapping toggle: turn off for precise, detailed drawing.
    snap_on = bool(state.get("snap_enabled", True))
    snap_r = pygame.Rect(x, y, PANEL_W - 40, 28)
    state["snap_toggle_rect"] = snap_r
    _button(snap_r, "Snapping: ON" if snap_on else "Snapping: OFF",
            active=snap_on, icon="snap")
    _queue_tip(snap_r, "snap")
    y += 36

    # Shape tools live in the bottom toolbar (drawn by the controller).

    # Reference image (folded by default; one click to reveal).
    y, ref_open = draw_section_header(
        screen, font_small, mouse_pos, state, x, y,
        "draw_reference", "Reference image", width=PANEL_W - 40)
    ref = state.get("reference_image")
    if ref_open:
        bw3 = (PANEL_W - 40 - 16) // 3
        load_r = pygame.Rect(x, y, bw3, 28)
        vis_r = pygame.Rect(x + bw3 + 8, y, bw3, 28)
        clear_r = pygame.Rect(x + (bw3 + 8) * 2, y, PANEL_W - 40 - (bw3 + 8) * 2, 28)
        state["ref_load_rect"] = load_r
        state["ref_vis_rect"] = vis_r
        state["ref_clear_rect"] = clear_r
        vis_label = "Hide" if (ref and ref.get("visible", True)) else "Show"
        vis_icon = "ref_visible" if (ref and ref.get("visible", True)) else "ref_hidden"
        for r, icon_name, label in ((load_r, "ref_load", "Load"), (vis_r, vis_icon, vis_label), (clear_r, "ref_clear", "Clear")):
            _button(r, label, icon=icon_name)
            _queue_tip(r, "ref_visible" if icon_name in ("ref_visible", "ref_hidden") else icon_name)
        y += 34
        if ref and ref.get("surface") is not None:
            opacity = clamp(ref.get("opacity", 0.5), 0.0, 1.0)
            screen.blit(font_small.render("Alt+drag to move the image", True, MUTED_COLOR), (x, y))
            y += 18 + MIN_ELEMENT_SPACING
            bar = pygame.Rect(x, y, PANEL_W - 40, DRAG_FIELD_H)
            state["ref_opacity_rect"] = bar
            draw_drag_field(
                screen, bar, opacity, 0.0, 1.0,
                f"{int(round(opacity * 100))}%", font_small,
                mouse_pos=mouse_pos, label="Opacity",
            )
            y += DRAG_FIELD_H + MIN_ELEMENT_SPACING
        else:
            state["ref_opacity_rect"] = pygame.Rect(0, 0, 0, 0)
            screen.blit(font_small.render("No reference image", True, MUTED_COLOR), (x, y)); y += 18
        err = state.get("reference_error")
        if err:
            # Word-wrap the error so it stays inside the panel.
            line = ""
            for word in str(err).split():
                trial = (line + " " + word).strip()
                if line and font_small.size(trial)[0] > PANEL_W - 40:
                    screen.blit(font_small.render(line, True, TEXT_DANGER), (x, y)); y += 16
                    line = word
                else:
                    line = trial
            if line:
                screen.blit(font_small.render(line, True, TEXT_DANGER), (x, y)); y += 16
    else:
        for key in ("ref_load_rect", "ref_vis_rect", "ref_clear_rect", "ref_opacity_rect"):
            state[key] = pygame.Rect(0, 0, 0, 0)

    y += 4

    stats = font_small.render(f"Strokes: {state['stroke_count']} | Backend: {CAIRO_BACKEND}", True, MUTED_COLOR)
    screen.blit(stats, (x, y)); y += 24
    _dt = state.get("draw_tool", "pen")
    if _dt == "eraser":
        help_lines = [
            "Eraser: click curve/edge to remove.",
            "Switch to Pen/Fill to draw.",
            "Shortcuts: Ctrl+Z/Ctrl+Y, C, Esc",
        ]
    elif _dt == "cutter":
        help_lines = [
            "Split: drag across curves to break them.",
            "Halves stay connected; select each in Curve mode.",
            "Shortcuts: Ctrl+Z/Ctrl+Y, C, Esc",
        ]
    elif _dt == "bucket":
        help_lines = [
            "Fill: click an enclosed area to create a filled shape (no stroke).",
            "Works on visible boundaries like a paint bucket.",
            "Shortcuts: Ctrl+Z/Ctrl+Y, C, Esc",
        ]
    else:
        help_lines = [
            "Pen: drag on canvas to draw.",
            "Pick a Shape to create standard shapes.",
            "Snapping joins nearby endpoints (S to toggle).",
            "Shortcuts: Ctrl+Z/Ctrl+Y, C, Esc",
        ]

    return y, help_lines


