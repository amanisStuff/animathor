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

from views.icons import BUTTON_TIPS, draw_icon, draw_tooltip  # noqa: E402


def _draw_wave_graph(screen, rect, poly, color, bg=(24, 26, 34), line_w=2, mid=True):
    """Draw a normalized waveform polyline inside rect (x in [0,1], y in [-1,1])."""
    pygame.draw.rect(screen, bg, rect, border_radius=4)
    if mid:
        pygame.draw.line(screen, (66, 70, 82), (rect.x + 3, rect.centery), (rect.right - 3, rect.centery), 1)
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

def draw_swatch(screen, rect, color, selected, mouse_pos):
    hover = rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=4)
    inner = rect.inflate(-6, -6)
    if color is None:
        # "none" swatch
        pygame.draw.rect(screen, (250, 250, 250), inner, border_radius=3)
        pygame.draw.line(screen, (200, 60, 60), inner.topleft, inner.bottomright, 2)
    else:
        rgb = tuple(int(c * 255) for c in color_rgb(color))
        pygame.draw.rect(screen, rgb, inner, border_radius=3)
    border = ACCENT if selected else (ACCENT if hover else BUTTON_BORDER)
    pygame.draw.rect(screen, border, rect, width=2 if selected else 1, border_radius=4)


# Cached HSV picker gradients: rebuilding the SV square pixel-by-pixel every
# frame costs tens of milliseconds, so keep the surfaces around.
_SV_CACHE = {}
_SV_RAMP_CACHE = {}
_HUE_BAR_CACHE = {}


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
            row.set_at((ix, 0), tuple(int(v * 255) for v in c))
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
            pygame.draw.line(surf, tuple(int(v * 255) for v in c), (ix, 0), (ix, h - 1))
        _HUE_BAR_CACHE[key] = surf
    return surf

def draw_panel(screen, fonts, mouse_pos, state):
    font, font_small, font_title = fonts
    top = getattr(cfg, "TOP_BAR_H", 0)
    panel_rect = pygame.Rect(cfg.PANEL_X, top, PANEL_W, cfg.HEIGHT - top)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    pygame.draw.line(screen, PANEL_BORDER, (cfg.PANEL_X, top), (cfg.PANEL_X, cfg.HEIGHT), 2)

    x = cfg.PANEL_X + 20
    y = top + 18 - int(state.get("panel_scroll", 0) or 0)
    tm = state.get("tool_mode", "draw")

    # Tooltips are queued while drawing buttons, then rendered on top at the
    # end so later controls never cover them.
    _tips = []

    def _queue_tip(rect, key, text=None):
        if rect.collidepoint(mouse_pos):
            _tips.append(text or BUTTON_TIPS.get(key, ""))

    def _icon_and_label(rect, icon_name, label, active):
        """Draw a small icon followed by a label inside a button rect."""
        color = ACCENT if active else TEXT_COLOR
        icon_r = pygame.Rect(rect.x + 4, rect.centery - 10, 20, 20)
        draw_icon(screen, icon_name, icon_r, color=color, size=20)
        label_surf = font_small.render(label, True, color)
        area = pygame.Rect(icon_r.right + 3, rect.y, rect.right - icon_r.right - 7, rect.h)
        screen.blit(label_surf, label_surf.get_rect(center=area.center))
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
        state["eyedropper_rect"] = pygame.Rect(0, 0, 0, 0)

        # Tools first: the active tool decides which options are shown below.
        draw_tool = state.get("draw_tool", "pen")
        total_w = PANEL_W - 40
        gap = 6
        bw = (total_w - gap) // 2
        rh = 28
        pen_r = pygame.Rect(x, y, bw, rh)
        er_r = pygame.Rect(x + bw + gap, y, total_w - bw - gap, rh)
        bucket_r = pygame.Rect(x, y + rh + gap, bw, rh)
        cutter_r = pygame.Rect(x + bw + gap, y + rh + gap, total_w - bw - gap, rh)
        state["draw_tool_pen_rect"] = pen_r
        state["draw_tool_eraser_rect"] = er_r
        state["draw_tool_bucket_rect"] = bucket_r
        state["draw_tool_cutter_rect"] = cutter_r
        for r, key, label in ((pen_r, "pen", "Pen"), (er_r, "eraser", "Eraser"),
                              (bucket_r, "bucket", "Fill"), (cutter_r, "cutter", "Split curve")):
            active_t = (draw_tool == key)
            bg = TOOL_ACTIVE if active_t else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, ACCENT if active_t else BUTTON_BORDER, r, 2 if active_t else 1, border_radius=6)
            _icon_and_label(r, key, label, active_t)
            _queue_tip(r, key)
        y += rh * 2 + gap + 10

        if draw_tool != "pen":
            # Pen-only controls aren't drawn; move their hit areas out of the way.
            state["trace_algo_rects"] = {}
            state["slider"].track.width = 0
            state["buttons"]["boost"].rect = pygame.Rect(0, 0, 0, 0)

        if draw_tool == "pen":
            # Points control
            label = font.render("Points / curve", True, TEXT_COLOR)
            screen.blit(label, (x, y)); y += 24
            limit = state["BOOST_MAX_POINTS"] if state["boost_points"] else state["NORMAL_MAX_POINTS"]
            val = font_title.render(str(state["max_points"]), True, ACCENT)
            screen.blit(val, (x, y - 2))
            hint = font_small.render(f"(2 - {limit})", True, MUTED_COLOR)
            screen.blit(hint, (x + val.get_width() + 10, y + 4)); y += 32
            state["slider"].track.topleft = (x, y)
            state["slider"].track.width = PANEL_W - 40
            state["slider"].draw(screen); y += 24
            b = state["buttons"]["boost"]
            b.rect.topleft = (x, y)
            b.label = "Boost: ON" if state["boost_points"] else "Boost limit"
            b.draw(screen, font, mouse_pos, active=state["boost_points"])
            draw_icon(screen, "boost", pygame.Rect(b.rect.x + 6, b.rect.centery - 10, 20, 20),
                      color=ACCENT if state["boost_points"] else TEXT_COLOR, size=20)
            _queue_tip(b.rect, "boost"); y += 44

            # Tracing algorithm (per new stroke)
            screen.blit(font.render("Tracing", True, TEXT_COLOR), (x, y)); y += 22
            algo = state.get("trace_algorithm", "fit")
            rects = {}
            bw = (PANEL_W - 40 - 8) // 3
            _trace_tip = {"fit": "trace_fit", "catmull-rom": "trace_catmull_rom", "single": "trace_single"}
            for i, (key, label) in enumerate(TRACE_ALGORITHMS):
                r = pygame.Rect(x + i * (bw + 4), y, bw, 28)
                rects[key] = r
                active = (algo == key)
                bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
                pygame.draw.rect(screen, bg, r, border_radius=6)
                pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r, 2 if active else 1, border_radius=6)
                t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
                screen.blit(t, t.get_rect(center=r.center))
                _queue_tip(r, _trace_tip.get(key))
            state["trace_algo_rects"] = rects
            y += 36
        elif draw_tool == "eraser":
            screen.blit(font_small.render("Click a curve or edge to erase it.", True, MUTED_COLOR), (x, y)); y += 22
        elif draw_tool == "cutter":
            screen.blit(font_small.render("Drag across curves to split them.", True, MUTED_COLOR), (x, y)); y += 22
            screen.blit(font_small.render("Each crossing adds a node; each half is a curve.", True, MUTED_COLOR), (x, y)); y += 22

            # Optional gap: 0 keeps the stroke connected at the new node.
            screen.blit(font.render("Gap", True, TEXT_COLOR), (x, y)); y += 24
            gap_val = int(state.get("cut_gap", 0) or 0)
            val = font_title.render(f"{gap_val} px", True, ACCENT)
            screen.blit(val, (x, y - 2))
            hint = font_small.render("(0 = stays connected)", True, MUTED_COLOR)
            screen.blit(hint, (x + val.get_width() + 10, y + 4)); y += 30
            _gap_slider = state.get("cut_gap_slider")
            if _gap_slider is not None:
                _gap_slider.track.topleft = (x, y)
                _gap_slider.track.width = PANEL_W - 40
                _gap_slider.value = gap_val
                _gap_slider.draw(screen)
            y += 26
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
            pygame.draw.rect(screen, (255, 255, 255), preview, border_radius=6)
            pygame.draw.rect(screen, tuple(int(c * 255) for c in col),
                             preview.inflate(-6, -6), border_radius=4)
            pygame.draw.rect(screen, BUTTON_BORDER, preview, 1, border_radius=6)
            screen.blit(font_small.render(rgb_to_hex(col), True, TEXT_COLOR), (x + 38, y + 7))
            y += 38

            # Saturation / value square
            sv_w = PANEL_W - 40
            sv_h = 84
            sv_rect = pygame.Rect(x, y, sv_w, sv_h)
            state["bucket_sv_rect"] = sv_rect
            sv_surf = _sv_surface(ph, sv_w, sv_h)
            screen.blit(sv_surf, sv_rect.topleft)
            pygame.draw.rect(screen, BUTTON_BORDER, sv_rect, 1, border_radius=4)
            cxp = sv_rect.x + int(clamp(ps, 0.0, 1.0) * (sv_w - 1))
            cyp = sv_rect.y + int((1.0 - clamp(pv, 0.0, 1.0)) * (sv_h - 1))
            pygame.draw.circle(screen, (255, 255, 255), (cxp, cyp), 5, 2)
            pygame.draw.circle(screen, (0, 0, 0), (cxp, cyp), 5, 1)
            y += sv_h + 8

            # Hue bar
            hue_h = 12
            hue_rect = pygame.Rect(x, y, sv_w, hue_h)
            state["bucket_hue_rect"] = hue_rect
            screen.blit(_hue_bar_surface(sv_w, hue_h), hue_rect.topleft)
            pygame.draw.rect(screen, BUTTON_BORDER, hue_rect, 1, border_radius=4)
            hx = hue_rect.x + int((clamp(ph, 0.0, 360.0) / 360.0) * (sv_w - 1))
            pygame.draw.rect(screen, (255, 255, 255), (hx - 3, hue_rect.y - 2, 6, hue_h + 4), 2, border_radius=2)
            pygame.draw.rect(screen, (0, 0, 0), (hx - 3, hue_rect.y - 2, 6, hue_h + 4), 1, border_radius=2)
            y += hue_h + 10

            # Preset swatches
            sw, sgap = 26, 6
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
            y += rows_used * (sw + sgap) + 2

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
        bg = TOOL_ACTIVE if snap_on else (BUTTON_HOVER if snap_r.collidepoint(mouse_pos) else BUTTON_BG)
        pygame.draw.rect(screen, bg, snap_r, border_radius=6)
        pygame.draw.rect(screen, ACCENT if snap_on else BUTTON_BORDER, snap_r, 2 if snap_on else 1, border_radius=6)
        _icon_and_label(snap_r, "snap", "Snapping: ON" if snap_on else "Snapping: OFF", snap_on)
        _queue_tip(snap_r, "snap")
        y += 36

        # Shape tools live in the bottom toolbar (drawn by the controller).

        # Reference image
        screen.blit(font.render("Reference image", True, TEXT_COLOR), (x, y)); y += 22
        ref = state.get("reference_image")
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
            bg = BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, BUTTON_BORDER, r, 1, border_radius=6)
            _icon_and_label(r, icon_name, label, False)
            _queue_tip(r, "ref_visible" if icon_name in ("ref_visible", "ref_hidden") else icon_name)
        y += 34
        if ref and ref.get("surface") is not None:
            op = int(round(clamp(ref.get("opacity", 0.5), 0.0, 1.0) * 100))
            screen.blit(font_small.render(f"Opacity {op}%  (Alt+drag to move)", True, MUTED_COLOR), (x, y)); y += 18
            bar = pygame.Rect(x, y, PANEL_W - 40, 10)
            state["ref_opacity_rect"] = bar
            pygame.draw.rect(screen, (225, 228, 235), bar, border_radius=4)
            fill_w = int(bar.w * clamp(ref.get("opacity", 0.5), 0.0, 1.0))
            if fill_w > 0:
                pygame.draw.rect(screen, ACCENT, (bar.x, bar.y, fill_w, bar.h), border_radius=4)
            pygame.draw.rect(screen, BUTTON_BORDER, bar, 1, border_radius=4)
            y += 18
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
                    screen.blit(font_small.render(line, True, (190, 70, 60)), (x, y)); y += 16
                    line = word
                else:
                    line = trial
            if line:
                screen.blit(font_small.render(line, True, (190, 70, 60)), (x, y)); y += 16
        y += 4

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
    else:
        # Selection mode: transform operations and modern color selection
        sel_strokes = state.get("selected_strokes", set())
        sel_count = len(sel_strokes)
        # Submode toggle: Transform / Edit Nodes / Curve
        submode = state.get("selection_submode", "transform")
        toggle = pygame.Rect(x, y, PANEL_W - 40, 30)
        state["nodes_toggle_rect"] = toggle
        pygame.draw.rect(screen, BUTTON_BG, toggle, border_radius=6)
        pygame.draw.rect(screen, BUTTON_BORDER, toggle, 1, border_radius=6)
        modes = (("Transform", "transform"), ("Nodes", "nodes"), ("Curve", "curve"))
        part = toggle.w // len(modes)
        for i, (label, key) in enumerate(modes):
            r = pygame.Rect(toggle.x + i * part, toggle.y, part if i < len(modes)-1 else toggle.w - i*part, toggle.h)
            active = (submode == key)
            if active:
                pygame.draw.rect(screen, TOOL_ACTIVE, r.inflate(-4, -4), border_radius=5)
            t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
            _queue_tip(r, None, f"{label} mode (N to cycle)")
        y += 34
        # Eyedropper (pick style) - tool within selection panel
        pick_active = bool(state.get("eyedropper_pick"))
        ed_rect = pygame.Rect(x, y, PANEL_W - 40, 28)
        state["eyedropper_rect"] = ed_rect
        bg = TOOL_ACTIVE if pick_active else (BUTTON_HOVER if ed_rect.collidepoint(mouse_pos) else BUTTON_BG)
        pygame.draw.rect(screen, bg, ed_rect, border_radius=6)
        pygame.draw.rect(screen, ACCENT if pick_active else BUTTON_BORDER, ed_rect, 2 if pick_active else 1, border_radius=6)
        ed_label = "Eyedropper: click a stroke..." if pick_active else "Eyedropper - pick style (I)"
        _icon_and_label(ed_rect, "eyedropper", ed_label, pick_active)
        _queue_tip(ed_rect, "eyedropper")
        y += 32
        if pick_active:
            hint = font_small.render("Samples stroke/fill color, size, wave effects", True, MUTED_COLOR)
            screen.blit(hint, (x, y)); y += 18

        sel_stroke = state.get("selected_obj")
        # Elevation / z-order controls (transform mode)
        state.setdefault("elev_front_rect", pygame.Rect(0,0,0,0))
        state.setdefault("elev_forward_rect", pygame.Rect(0,0,0,0))
        state.setdefault("elev_backward_rect", pygame.Rect(0,0,0,0))
        state.setdefault("elev_back_rect", pygame.Rect(0,0,0,0))
        if submode == "transform" and sel_count > 0:
            screen.blit(font_small.render("Elevation", True, TEXT_COLOR), (x, y)); y += 20
            gap = 6
            bw = (PANEL_W - 40 - gap) // 2
            labels = [("To Front", "elev_front_rect", "elev_front"), ("Forward", "elev_forward_rect", "elev_forward"),
                      ("Backward", "elev_backward_rect", "elev_backward"), ("To Back", "elev_back_rect", "elev_back")]
            for i, (label, key, icon_name) in enumerate(labels):
                row, col = divmod(i, 2)
                r = pygame.Rect(x + col * (bw + gap), y + row * 28, bw, 24)
                state[key] = r
                bg = BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG
                pygame.draw.rect(screen, bg, r, border_radius=5)
                pygame.draw.rect(screen, BUTTON_BORDER, r, 1, border_radius=5)
                _icon_and_label(r, icon_name, label, False)
                _queue_tip(r, icon_name)
            y += 2 * 28 + 8
        else:
            state["elev_front_rect"] = pygame.Rect(0,0,0,0)
            state["elev_forward_rect"] = pygame.Rect(0,0,0,0)
            state["elev_backward_rect"] = pygame.Rect(0,0,0,0)
            state["elev_back_rect"] = pygame.Rect(0,0,0,0)

        # Boolean operations (transform mode, 2+ selected shapes)
        state.setdefault("bool_union_rect", pygame.Rect(0,0,0,0))
        state.setdefault("bool_intersect_rect", pygame.Rect(0,0,0,0))
        if submode == "transform" and sel_count >= 2:
            screen.blit(font_small.render("Boolean", True, TEXT_COLOR), (x, y)); y += 20
            bgap = 6
            bwidth = (PANEL_W - 40 - bgap) // 2
            for bi, (blabel, bkey, bicon) in enumerate([
                    ("Union", "bool_union_rect", "union"),
                    ("Intersect", "bool_intersect_rect", "intersect")]):
                br = pygame.Rect(x + (bi % 2) * (bwidth + bgap), y + (bi // 2) * 28, bwidth, 24)
                state[bkey] = br
                bg = BUTTON_HOVER if br.collidepoint(mouse_pos) else BUTTON_BG
                pygame.draw.rect(screen, bg, br, border_radius=5)
                pygame.draw.rect(screen, BUTTON_BORDER, br, 1, border_radius=5)
                _icon_and_label(br, bicon, blabel, False)
                _queue_tip(br, bicon)
            y += 28 + 8
        else:
            state["bool_union_rect"] = pygame.Rect(0,0,0,0)
            state["bool_intersect_rect"] = pygame.Rect(0,0,0,0)

        # Mirror (flip) and alignment tools (transform mode)
        for _k in ("mirror_h_rect", "mirror_v_rect",
                   "align_left_rect", "align_hcenter_rect", "align_right_rect",
                   "align_top_rect", "align_vmiddle_rect", "align_bottom_rect"):
            state.setdefault(_k, pygame.Rect(0, 0, 0, 0))
        if submode == "transform" and sel_count >= 1:
            screen.blit(font_small.render("Flip", True, TEXT_COLOR), (x, y)); y += 20
            mgap = 6
            mwidth = (PANEL_W - 40 - mgap) // 2
            for mi, (mlabel, mkey, icon_name) in enumerate([
                    ("Horizontal", "mirror_h_rect", "flip_h"),
                    ("Vertical", "mirror_v_rect", "flip_v")]):
                mr = pygame.Rect(x + mi * (mwidth + mgap), y, mwidth, 24)
                state[mkey] = mr
                bg = BUTTON_HOVER if mr.collidepoint(mouse_pos) else BUTTON_BG
                pygame.draw.rect(screen, bg, mr, border_radius=5)
                pygame.draw.rect(screen, BUTTON_BORDER, mr, 1, border_radius=5)
                _icon_and_label(mr, icon_name, mlabel, False)
                _queue_tip(mr, icon_name)
            y += 24 + 8

            screen.blit(font_small.render("Align", True, TEXT_COLOR), (x, y)); y += 20
            agap = 6
            aw = (PANEL_W - 40 - 2 * agap) // 3
            align_defs = [
                ("Left", "align_left_rect", "align_left"),
                ("Center", "align_hcenter_rect", "align_hcenter"),
                ("Right", "align_right_rect", "align_right"),
                ("Top", "align_top_rect", "align_top"),
                ("Middle", "align_vmiddle_rect", "align_vmiddle"),
                ("Bottom", "align_bottom_rect", "align_bottom"),
            ]
            for ai, (_alabel, akey, icon_name) in enumerate(align_defs):
                row, col = divmod(ai, 3)
                ar = pygame.Rect(x + col * (aw + agap), y + row * 26, aw, 22)
                state[akey] = ar
                bg = BUTTON_HOVER if ar.collidepoint(mouse_pos) else BUTTON_BG
                pygame.draw.rect(screen, bg, ar, border_radius=5)
                pygame.draw.rect(screen, BUTTON_BORDER, ar, 1, border_radius=5)
                draw_icon(screen, icon_name, ar, color=TEXT_COLOR, size=20)
                _queue_tip(ar, icon_name)
            y += 2 * 26 + 8
        else:
            state["mirror_h_rect"] = pygame.Rect(0, 0, 0, 0)
            state["mirror_v_rect"] = pygame.Rect(0, 0, 0, 0)
            state["align_left_rect"] = pygame.Rect(0, 0, 0, 0)
            state["align_hcenter_rect"] = pygame.Rect(0, 0, 0, 0)
            state["align_right_rect"] = pygame.Rect(0, 0, 0, 0)
            state["align_top_rect"] = pygame.Rect(0, 0, 0, 0)
            state["align_vmiddle_rect"] = pygame.Rect(0, 0, 0, 0)
            state["align_bottom_rect"] = pygame.Rect(0, 0, 0, 0)

        # Curve/stroke-edit controls
        state.setdefault("curve_hide_rect", pygame.Rect(0,0,0,0))
        state.setdefault("curve_redraw_rect", pygame.Rect(0,0,0,0))
        state.setdefault("curve_cut_rect", pygame.Rect(0,0,0,0))
        state.setdefault("curve_join_rect", pygame.Rect(0,0,0,0))
        _sel_curves_panel = set(state.get("selected_curves") or [])
        if not _sel_curves_panel and state.get("selected_curve"):
            _sel_curves_panel = {state.get("selected_curve")}
        if submode == "curve" and len(_sel_curves_panel) > 1:
            screen.blit(font_small.render(f"Selected curves: {len(_sel_curves_panel)}", True, MUTED_COLOR), (x, y)); y += 22
            screen.blit(font_small.render("Shift+click to add or remove curves.", True, MUTED_COLOR), (x, y)); y += 20
            join_rect = pygame.Rect(x, y, PANEL_W - 40, 30)
            state["curve_join_rect"] = join_rect
            state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
            state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
            state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
            bg = BUTTON_HOVER if join_rect.collidepoint(mouse_pos) else BUTTON_BG
            pygame.draw.rect(screen, bg, join_rect, border_radius=6)
            pygame.draw.rect(screen, BUTTON_BORDER, join_rect, 1, border_radius=6)
            jlabel = font_small.render("Join curves", True, TEXT_COLOR)
            screen.blit(jlabel, jlabel.get_rect(center=join_rect.center))
            _queue_tip(join_rect, None, "Join selected curves (adjacent components)")
            y += 38
            _gap_slider = state.get("cut_gap_slider")
            if _gap_slider is not None:
                _gap_slider.track.width = 0
            state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
            state["wave_add_rect"] = pygame.Rect(0,0,0,0)
            state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
            state["wave_slider_rects"] = {}
            state["wave_shape_rects"] = {}
            state["wave_row_rects"] = []
            state["wave_formula_rect"] = pygame.Rect(0,0,0,0)
            state["wave_custom_box_rect"] = pygame.Rect(0,0,0,0)
            state["wave_smooth_rect"] = pygame.Rect(0,0,0,0)
            state["wave_reverse_rect"] = pygame.Rect(0,0,0,0)
        elif submode == "curve" and sel_count == 1 and sel_stroke is not None:
            sc = state.get("selected_curve")
            if sc and sc[0] in sel_strokes:
                comp_i = sc[1]
                comps = _stroke_components(sel_stroke)
                label_what = "stroke" if len(comps) > 1 else "curve"
                screen.blit(font_small.render(f"Selected {label_what}: {comp_i + 1}/{max(1,len(comps))}", True, MUTED_COLOR), (x, y)); y += 22
                hidden = set(sel_stroke.get("hidden_segs", set()) or set()) if isinstance(sel_stroke, dict) else set()
                ranges = _component_ranges(sel_stroke)
                comp_hidden = []
                if 0 <= comp_i < len(ranges):
                    s0, s1 = ranges[comp_i]
                    comp_hidden = [i for i in range(s0, min(s1, len(segs_of(sel_stroke)))) if i in hidden]
                if 0 <= comp_i < len(comps):
                    ci = comps[comp_i]
                    info = f"Settings: {ci.get('algorithm','fit')}, pts {ci.get('draw_max_points',4)}"
                    screen.blit(font_small.render(info, True, MUTED_COLOR), (x, y)); y += 18
                if comp_hidden:
                    hint = "Hidden curve segment(s)" if len(comp_hidden) < (ranges[comp_i][1]-ranges[comp_i][0] if 0 <= comp_i < len(ranges) else 999) else "Hidden curve"
                    screen.blit(font_small.render(f"Hint: {hint} (shown dashed in edit modes)", True, (170, 95, 40)), (x, y)); y += 18
                total_w = PANEL_W - 40
                btn_gap = 6
                btn_w = (total_w - btn_gap) // 2
                redraw_rect = pygame.Rect(x, y, btn_w, 30)
                cut_rect = pygame.Rect(x + btn_w + btn_gap, y, total_w - btn_w - btn_gap, 30)
                state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
                state["curve_redraw_rect"] = redraw_rect
                state["curve_cut_rect"] = cut_rect
                bg = BUTTON_HOVER if redraw_rect.collidepoint(mouse_pos) else BUTTON_BG
                pygame.draw.rect(screen, bg, redraw_rect, border_radius=6)
                pygame.draw.rect(screen, BUTTON_BORDER, redraw_rect, 1, border_radius=6)
                _icon_and_label(redraw_rect, "curve_redraw", "Redraw", False)
                _queue_tip(redraw_rect, "curve_redraw")
                cut_active = bool(state.get("curve_cut_mode"))
                cbg = TOOL_ACTIVE if cut_active else (BUTTON_HOVER if cut_rect.collidepoint(mouse_pos) else BUTTON_BG)
                pygame.draw.rect(screen, cbg, cut_rect, border_radius=6)
                pygame.draw.rect(screen, ACCENT if cut_active else BUTTON_BORDER, cut_rect,
                                 2 if cut_active else 1, border_radius=6)
                _icon_and_label(cut_rect, "cutter", "Split curve", cut_active)
                _queue_tip(cut_rect, "curve_cut")
                y += 38
                if cut_active:
                    screen.blit(font_small.render("Drag across the selected curve to cut it.",
                                                  True, ACCENT), (x, y)); y += 20

                    # Optional gap: 0 keeps the stroke connected at the new node.
                    screen.blit(font.render("Gap", True, TEXT_COLOR), (x, y)); y += 24
                    gap_val = int(state.get("cut_gap", 0) or 0)
                    val = font_title.render(f"{gap_val} px", True, ACCENT)
                    screen.blit(val, (x, y - 2))
                    hint = font_small.render("(0 = stays connected)", True, MUTED_COLOR)
                    screen.blit(hint, (x + val.get_width() + 10, y + 4)); y += 30
                    _gap_slider = state.get("cut_gap_slider")
                    if _gap_slider is not None:
                        _gap_slider.track.topleft = (x, y)
                        _gap_slider.track.width = PANEL_W - 40
                        _gap_slider.value = gap_val
                        _gap_slider.draw(screen)
                    y += 26
                else:
                    _gap_slider = state.get("cut_gap_slider")
                    if _gap_slider is not None:
                        _gap_slider.track.width = 0

                # Curve styles list (non-destructive). Styles are added to this curve.
                comp = comps[comp_i] if 0 <= comp_i < len(comps) else {}
                styles = _component_styles(comp)
                has_wave = any(isinstance(s, dict) and s.get("type") == "wave" for s in styles)
                waves_all = _get_wave_styles(comp) if has_wave else []
                n_waves = len(waves_all)
                collapsed = bool(state.get("wave_list_collapsed"))
                arrow = ">" if collapsed else "v"
                header_label = f"{arrow} Curve styles"
                if has_wave:
                    header_label += f" ({n_waves})"
                hdr_rect = pygame.Rect(x, y, PANEL_W - 40, 22)
                state["wave_list_header_rect"] = hdr_rect
                hbg = BUTTON_HOVER if hdr_rect.collidepoint(mouse_pos) else None
                if hbg:
                    pygame.draw.rect(screen, hbg, hdr_rect, border_radius=5)
                screen.blit(font_small.render(header_label, True, TEXT_COLOR), (x + 4, y + 3))
                y += 24

                state["wave_add_rect"] = pygame.Rect(0,0,0,0)
                state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
                state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
                state["wave_slider_rects"] = {}
                state["wave_shape_rects"] = {}
                state["wave_row_rects"] = []
                state["wave_formula_rect"] = pygame.Rect(0,0,0,0)
                state["wave_custom_box_rect"] = pygame.Rect(0,0,0,0)
                state["wave_smooth_rect"] = pygame.Rect(0,0,0,0)
                state["wave_reverse_rect"] = pygame.Rect(0,0,0,0)

                if collapsed:
                    # keep details hidden but allow adding a wave
                    add_rect = pygame.Rect(x, y, PANEL_W - 40, 24)
                    state["wave_add_rect"] = add_rect
                    abg = BUTTON_HOVER if add_rect.collidepoint(mouse_pos) else BUTTON_BG
                    pygame.draw.rect(screen, abg, add_rect, border_radius=5)
                    pygame.draw.rect(screen, BUTTON_BORDER, add_rect, 1, border_radius=5)
                    _icon_and_label(add_rect, "wave_add", "Add Wave distortion", False)
                    _queue_tip(add_rect, "wave_add")
                    y += 30
                elif has_wave:
                    # active (expanded) wave index, clamped to the current stack
                    wi = int(state.get("wave_active_index", 0) or 0)
                    if not (0 <= wi < n_waves):
                        wi = max(0, n_waves - 1)
                    wave = waves_all[wi]
                    enabled = bool(wave.get("enabled"))
                    shape = str(wave.get("shape", "sine") or "sine").lower()

                    # ---- modifier stack rows: click a row to edit that wave ----
                    row_h = 26
                    for i, wv in enumerate(waves_all):
                        row = pygame.Rect(x, y, PANEL_W - 40, row_h)
                        is_active = (i == wi)
                        wv_on = bool(wv.get("enabled"))
                        rbg = (44, 52, 76) if is_active else (BUTTON_HOVER if row.collidepoint(mouse_pos) else BUTTON_BG)
                        pygame.draw.rect(screen, rbg, row, border_radius=6)
                        pygame.draw.rect(screen, ACCENT if is_active else BUTTON_BORDER, row, 2 if is_active else 1, border_radius=6)
                        wshape_i = str(wv.get("shape", "sine") or "sine").lower()
                        if wshape_i == "noise":
                            lbl = f"Noise {i + 1}"
                        else:
                            wlabel = WAVE_SHAPE_LABEL_DICT.get(wshape_i, "Wave")
                            lbl = f"Wave {i + 1} \u00b7 {wlabel}"
                        t = font_small.render(lbl, True, TEXT_COLOR if is_active else MUTED_COLOR)
                        screen.blit(t, (row.x + 8, row.y + 5))
                        if is_active:
                            tog_rect = pygame.Rect(row.right - 74, row.y + 3, 46, row_h - 6)
                            rem_rect = pygame.Rect(row.right - 26, row.y + 3, 22, row_h - 6)
                            state["wave_toggle_rect"] = tog_rect
                            state["wave_remove_rect"] = rem_rect
                            tbg = TOOL_ACTIVE if wv_on else (BUTTON_HOVER if tog_rect.collidepoint(mouse_pos) else BUTTON_BG)
                            pygame.draw.rect(screen, tbg, tog_rect, border_radius=5)
                            pygame.draw.rect(screen, ACCENT if wv_on else BUTTON_BORDER, tog_rect, 1, border_radius=5)
                            tt = font_small.render("ON" if wv_on else "OFF", True, ACCENT if wv_on else MUTED_COLOR)
                            screen.blit(tt, tt.get_rect(center=tog_rect.center))
                            _queue_tip(tog_rect, "wave_toggle")
                            xbg = BUTTON_HOVER if rem_rect.collidepoint(mouse_pos) else BUTTON_BG
                            pygame.draw.rect(screen, xbg, rem_rect, border_radius=5)
                            pygame.draw.rect(screen, BUTTON_BORDER, rem_rect, 1, border_radius=5)
                            xt = font_small.render("\u00d7", True, (205, 115, 115))
                            screen.blit(xt, xt.get_rect(center=rem_rect.center))
                            _queue_tip(rem_rect, "wave_remove")
                        else:
                            stt = font_small.render("ON" if wv_on else "OFF", True, ACCENT if wv_on else MUTED_COLOR)
                            screen.blit(stt, (row.right - 8 - stt.get_width(), row.y + 5))
                        state["wave_row_rects"].append((i, row))
                        y += row_h + 2
                    y += 4

                    # ---- live preview of the composed wave (instant feedback) ----
                    screen.blit(font_small.render("Preview", True, TEXT_COLOR), (x, y))
                    fval = float(wave.get("frequency", 0.0))
                    if fval > 1.0:
                        # legacy files: frequency meant "N cycles across the curve"
                        cap_txt = f"density {fval:.1f}" if shape == "noise" else f"{fval:.1f} cycles"
                    else:
                        # new semantics: cycle length = freq * bbox diagonal
                        cap_txt = f"cycle {fval:.2f}x diag"
                    cyc_t = font_small.render(cap_txt, True, MUTED_COLOR)
                    screen.blit(cyc_t, (x + PANEL_W - 40 - cyc_t.get_width(), y))
                    y += 18
                    prev_rect = pygame.Rect(x, y, PANEL_W - 40, 36)
                    _draw_wave_graph(screen, prev_rect, _wave_preview_polyline(wave), ACCENT if enabled else (128, 134, 148))
                    if not enabled:
                        hint = font_small.render("disabled - click ON to apply", True, (178, 182, 194))
                        screen.blit(hint, hint.get_rect(center=prev_rect.center))
                    y += 36 + 6

                    # ---- add another wave on top of the stack ----
                    add_rect = pygame.Rect(x, y, PANEL_W - 40, 24)
                    state["wave_add_rect"] = add_rect
                    abg = BUTTON_HOVER if add_rect.collidepoint(mouse_pos) else BUTTON_BG
                    pygame.draw.rect(screen, abg, add_rect, border_radius=5)
                    pygame.draw.rect(screen, BUTTON_BORDER, add_rect, 1, border_radius=5)
                    _icon_and_label(add_rect, "wave_add", "Add Wave distortion", False)
                    _queue_tip(add_rect, "wave_add")
                    y += 24 + 6

                    # ---- shape selector: waveform thumbnail icons ----
                    screen.blit(font_small.render("Shape", True, TEXT_COLOR), (x, y)); y += 20
                    shape_rects = {}
                    bw = (PANEL_W - 40 - 8) // 3
                    for i, (key, label) in enumerate(WAVE_SHAPE_LABELS):
                        rowi, coli = divmod(i, 3)
                        r = pygame.Rect(x + coli * (bw + 4), y + rowi * 38, bw, 34)
                        shape_rects[key] = r
                        active = (shape == key)
                        bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
                        pygame.draw.rect(screen, bg, r, border_radius=5)
                        pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r, 2 if active else 1, border_radius=5)
                        # miniature waveform preview of THIS shape
                        icon_wave = dict(wave)
                        icon_wave["shape"] = key
                        icon_rect = pygame.Rect(r.x + 4, r.y + 4, r.w - 8, 13)
                        _draw_wave_graph(screen, icon_rect, _wave_icon_polyline(icon_wave),
                                         ACCENT if active else (176, 182, 196),
                                         bg=(40, 46, 66) if active else (34, 37, 48), line_w=1)
                        t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
                        screen.blit(t, t.get_rect(center=(r.centerx, r.y + 25)))
                    state["wave_shape_rects"] = shape_rects
                    y += ((len(WAVE_SHAPE_LABELS) + 2) // 3) * 38 + 4

                    # Formula input (contextual: only for the formula shape)
                    state["wave_formula_rect"] = pygame.Rect(0,0,0,0)
                    if shape == "formula":
                        screen.blit(font_small.render("Formula (x=p, t,s)", True, TEXT_COLOR), (x, y)); y += 18
                        frect = pygame.Rect(x, y, PANEL_W - 40, 26)
                        state["wave_formula_rect"] = frect
                        focused = bool(state.get("wave_formula_focus"))
                        bg = (255,255,255) if focused else (BUTTON_HOVER if frect.collidepoint(mouse_pos) else BUTTON_BG)
                        pygame.draw.rect(screen, bg, frect, border_radius=5)
                        pygame.draw.rect(screen, ACCENT if focused else BUTTON_BORDER, frect, 2 if focused else 1, border_radius=5)
                        ftxt = str(wave.get("formula", "sin(x)") or "sin(x)")
                        if focused and (pygame.time.get_ticks() // 500) % 2 == 0:
                            ftxt_disp = ftxt + "|"
                        else:
                            ftxt_disp = ftxt
                        # clip text to fit
                        while ftxt_disp and font_small.size(ftxt_disp)[0] > frect.w - 12:
                            ftxt_disp = ftxt_disp[1:]
                        tt = font_small.render(ftxt_disp, True, TEXT_COLOR)
                        screen.blit(tt, (frect.x + 6, frect.y + 5))
                        y += 32
                    else:
                        state["wave_formula_focus"] = False

                    # Custom wave drawing mode - dedicated preview box (contextual)
                    BOX_W = 180
                    BOX_H = 80
                    state["wave_custom_draw"] = False
                    if shape != "custom":
                        state["wave_custom_finished"] = False
                    state["wave_custom_box_rect"] = pygame.Rect(0, 0, 0, 0)
                    if shape == "custom":
                        # dedicated box for the custom wave (Bit Invader style:
                        # hold and drag inside to paint the waveform)
                        bx = x + 8
                        by = y + 8
                        # draw box background
                        box_rect = pygame.Rect(bx, by, BOX_W, BOX_H)
                        state["wave_custom_box_rect"] = box_rect
                        cp = wave.get("custom_points", None)
                        if cp and len(cp) >= 2:
                            bg_col = (30, 30, 40)
                        else:
                            bg_col = (50, 50, 60)
                        pygame.draw.rect(screen, bg_col, box_rect, border_radius=4)
                        pygame.draw.rect(screen, (100, 100, 120), box_rect, 2, border_radius=4)

                        # draw the waveform as one continuous polyline
                        # (no per-point vertex handles: painting is the only edit)
                        if cp and len(cp) >= 2:
                            # scale samples to fit inside the box
                            # cx in [0,1], cy in [-1,1]
                            prev_px, prev_py = None, None
                            for cx, cy in cp:
                                px = bx + 6 + cx * (BOX_W - 12)
                                py = by + BOX_H//2 + cy * (BOX_H//2 - 4)  # map -1..1 to box height
                                if prev_px is not None:
                                    pygame.draw.line(screen, (100, 150, 255), (prev_px, prev_py), (int(px), int(py)), 2)
                                prev_px, prev_py = int(px), int(py)

                            # close the path by connecting last to first
                            if len(cp) > 2:
                                pygame.draw.line(screen, (100, 150, 255), (int(prev_px), int(prev_py)), (int(bx+6), int(by+BOX_H//2)), 1)

                        # grid lines inside box (subtle)
                        pygame.draw.line(screen, (70, 70, 80), (bx + 6, by + 4), (bx + BOX_W - 6, by + 4), 1)
                        pygame.draw.line(screen, (70, 70, 80), (bx + 6, by + BOX_H - 4), (bx + BOX_W - 6, by + BOX_H - 4), 1)

                        # Smooth button next to the box (relaxes painted samples)
                        has_wave_pts = bool(cp and len(cp) >= 2)
                        smooth_rect = pygame.Rect(bx, by + BOX_H + 6, 74, 20)
                        state["wave_smooth_rect"] = smooth_rect
                        sbg = BUTTON_HOVER if smooth_rect.collidepoint(mouse_pos) else BUTTON_BG
                        pygame.draw.rect(screen, sbg, smooth_rect, border_radius=5)
                        pygame.draw.rect(screen, BUTTON_BORDER if has_wave_pts else (70, 70, 80), smooth_rect, 1, border_radius=5)
                        st_text = font_small.render("Smooth", True, TEXT_COLOR if has_wave_pts else MUTED_COLOR)
                        screen.blit(st_text, st_text.get_rect(center=smooth_rect.center))

                        if has_wave_pts:
                            pt_count = f"{len(cp)} samples"
                        else:
                            pt_count = "hold & drag to draw"
                        instr = font_small.render(f"Custom: {pt_count}", True, (200, 200, 200))
                        screen.blit(instr, (smooth_rect.right + 8, smooth_rect.y + 3))

                        # finish instruction
                        finish_instr = font_small.render("Esc to finish", True, (180, 180, 180))
                        screen.blit(finish_instr, (smooth_rect.right + 8, smooth_rect.y + 18))

                        # advance past the box, its button and instructions
                        y = by + BOX_H + 34

                        # set custom_draw state (Esc/Enter finishes editing until
                        # the box or the Custom shape button is clicked again)
                        state["wave_custom_draw"] = not bool(state.get("wave_custom_finished", False))
                    # NOTE: when switching away from "custom", keep the stored
                    # custom_points so they are restored if the user switches back.

                    # ---- parameters (contextual: grayed out when inapplicable) ----
                    screen.blit(font_small.render("Parameters", True, TEXT_COLOR), (x, y)); y += 20

                    def _wave_slider(label, key, val, lo, hi, fmt=None, enabled=True):
                        nonlocal y
                        col = TEXT_COLOR if enabled else MUTED_COLOR
                        screen.blit(font_small.render(label, True, col), (x, y))
                        txt = fmt(val) if fmt else str(val)
                        vt = font_small.render(txt, True, ACCENT if enabled else MUTED_COLOR)
                        screen.blit(vt, (x + PANEL_W - 40 - vt.get_width(), y))
                        y += 18
                        track = pygame.Rect(x, y, PANEL_W - 40, 6)
                        track_col = (220, 225, 235) if enabled else (208, 212, 220)
                        pygame.draw.rect(screen, track_col, track, border_radius=3)
                        if hi == lo:
                            tx = track.x
                        else:
                            tx = int(track.x + (clamp(val, lo, hi) - lo) / (hi - lo) * track.w)
                        filled = pygame.Rect(track.x, track.y, max(0, tx - track.x), track.h)
                        pygame.draw.rect(screen, ACCENT if enabled else (180, 186, 198), filled, border_radius=3)
                        pygame.draw.circle(screen, (255, 255, 255) if enabled else (226, 229, 234), (tx, track.centery), 7)
                        pygame.draw.circle(screen, ACCENT if enabled else (180, 186, 198), (tx, track.centery), 7, width=2)
                        if enabled:
                            # grayed-out sliders are not interactive
                            hit = track.inflate(0, 16)
                            state.setdefault("wave_slider_rects", {})[key] = (hit, lo, hi)
                        y += 8

                    amp_v = float(wave.get("amplitude", 0.0))
                    freq_v = float(wave.get("frequency", 0.0))
                    phase_v = float(wave.get("phase", 0.0))
                    noise_v = float(wave.get("noise", 0.0))
                    seed_v = int(wave.get("seed", 0) or 0)
                    nscale_v = float(wave.get("noise_scale", 2.0))
                    noise_on = abs(noise_v) > 1e-6
                    _wave_slider("Amplitude", "amplitude", amp_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
                    _wave_slider("Frequency", "frequency", freq_v, 0.01, 1.0, fmt=lambda v: f"{v:.2f}")
                    if shape == "noise":
                        # standalone noise layer: amplitude (amount) and frequency
                        # (density) drive it; phase does not apply to random noise
                        _wave_slider("Phase", "phase", phase_v, 0.0, 360.0, fmt=lambda v: str(int(round(v))), enabled=False)
                        _wave_slider("Noise scale", "noise_scale", nscale_v, 0.2, 10.0, fmt=lambda v: f"{v:.1f}")
                        _wave_slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
                    else:
                        _wave_slider("Phase", "phase", phase_v, 0.0, 360.0, fmt=lambda v: str(int(round(v))))
                        if noise_on:
                            # legacy per-wave noise (saved by older versions) stays
                            # adjustable here; new noise belongs in its own row
                            _wave_slider("Noise", "noise", noise_v, 0.0, 100.0, fmt=lambda v: str(int(round(v))))
                            _wave_slider("Noise scale", "noise_scale", nscale_v, 0.2, 10.0, fmt=lambda v: f"{v:.1f}")
                            _wave_slider("Seed", "seed", seed_v, 0.0, 999.0, fmt=lambda v: str(int(round(v))))
                    # Reverse toggle: invert the wave (-f(x))
                    rev = bool(wave.get("reverse"))
                    rev_rect = pygame.Rect(x, y, PANEL_W - 40, 22)
                    state["wave_reverse_rect"] = rev_rect
                    rbg = TOOL_ACTIVE if rev else (BUTTON_HOVER if rev_rect.collidepoint(mouse_pos) else BUTTON_BG)
                    pygame.draw.rect(screen, rbg, rev_rect, border_radius=5)
                    pygame.draw.rect(screen, ACCENT if rev else BUTTON_BORDER, rev_rect, 1, border_radius=5)
                    rt = font_small.render(f"Reverse wave -f(x): {'ON' if rev else 'OFF'}", True, TEXT_COLOR)
                    screen.blit(rt, (rev_rect.x + 8, rev_rect.y + 4))
                    y += 26
                    y += 4
                else:
                    add_rect = pygame.Rect(x, y, PANEL_W - 40, 28)
                    state["wave_add_rect"] = add_rect
                    bg = BUTTON_HOVER if add_rect.collidepoint(mouse_pos) else BUTTON_BG
                    pygame.draw.rect(screen, bg, add_rect, border_radius=6)
                    pygame.draw.rect(screen, BUTTON_BORDER, add_rect, 1, border_radius=6)
                    _icon_and_label(add_rect, "wave_add", "Add Wave distortion", False)
                    _queue_tip(add_rect, "wave_add")
                    y += 34
                    screen.blit(font_small.render("No curve styles added", True, MUTED_COLOR), (x, y)); y += 18
            else:
                screen.blit(font_small.render("Click a stroke to edit separately", True, MUTED_COLOR), (x, y)); y += 24
                state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
                state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
                state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
                state["curve_join_rect"] = pygame.Rect(0,0,0,0)
                _gap_slider = state.get("cut_gap_slider")
                if _gap_slider is not None:
                    _gap_slider.track.width = 0
                state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
                state["wave_add_rect"] = pygame.Rect(0,0,0,0)
                state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
                state["wave_slider_rects"] = {}
                state["wave_shape_rects"] = {}
                state["wave_row_rects"] = []
        elif submode == "curve":
            screen.blit(font_small.render("Click a stroke to edit separately", True, MUTED_COLOR), (x, y)); y += 24
            state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
            state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
            state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
            state["curve_join_rect"] = pygame.Rect(0,0,0,0)
            _gap_slider = state.get("cut_gap_slider")
            if _gap_slider is not None:
                _gap_slider.track.width = 0
            state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
            state["wave_add_rect"] = pygame.Rect(0,0,0,0)
            state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
            state["wave_slider_rects"] = {}
            state["wave_shape_rects"] = {}
            state["wave_row_rects"] = []
        else:
            state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
            state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
            state["curve_cut_rect"] = pygame.Rect(0,0,0,0)
            state["curve_join_rect"] = pygame.Rect(0,0,0,0)
            _gap_slider = state.get("cut_gap_slider")
            if _gap_slider is not None:
                _gap_slider.track.width = 0
            state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
            state["wave_add_rect"] = pygame.Rect(0,0,0,0)
            state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
            state["wave_slider_rects"] = {}
            state["wave_shape_rects"] = {}
            state["wave_row_rects"] = []

        if sel_count == 0:
            info = font_small.render("Select a stroke", True, MUTED_COLOR)
            screen.blit(info, (x, y)); y += 28
            # clear style control rects
            state["tab_stroke_rect"] = pygame.Rect(0,0,0,0)
            state["tab_fill_rect"] = pygame.Rect(0,0,0,0)
            state["sv_rect"] = pygame.Rect(0,0,0,0)
            state["hue_rect"] = pygame.Rect(0,0,0,0)
            state["nofill_rect"] = pygame.Rect(0,0,0,0)
            state["alpha_rect"] = pygame.Rect(0,0,0,0)
            for i in range(len(state["stroke_swatch_rects"])): state["stroke_swatch_rects"][i] = pygame.Rect(0,0,0,0)
            for i in range(len(state["fill_swatch_rects"])): state["fill_swatch_rects"][i] = pygame.Rect(0,0,0,0)
        else:
            stroke = sel_stroke if sel_stroke is not None else state.get("selected_obj")
            if sel_count > 1:
                screen.blit(font_small.render(f"Multiple selected ({sel_count})", True, MUTED_COLOR), (x, y)); y += 20

            comp_style_target = None
            point_style_target = None
            if submode == "curve" and sel_count == 1 and state.get("selected_curve") and stroke is not None:
                scv = state.get("selected_curve")
                if scv and scv[0] in sel_strokes:
                    comp_style_target = scv[1]
            if submode == "nodes" and sel_count == 1 and stroke is not None:
                sp = state.get("selected_point")
                if sp and sp[1] in ("p0", "p3"):
                    point_style_target = sp  # (seg_i, anchor_name)
            shape_style_enabled = (submode == "transform")
            component_stroke_enabled = (comp_style_target is not None)
            point_width_enabled = (point_style_target is not None)
            width_enabled = shape_style_enabled or component_stroke_enabled or point_width_enabled
            stroke_color_enabled = shape_style_enabled or component_stroke_enabled
            fill_enabled = shape_style_enabled
            if component_stroke_enabled and state.get("color_target") == "fill":
                # fill can't apply to individual curve stroke
                state["color_target"] = "stroke"
            color_target = state.get("color_target", "stroke")
            state["style_controls_enabled"] = shape_style_enabled  # shape-level color picker (fill etc.)

            # effective values for display/controls
            eff_sw = stroke.get("stroke_width", 3.0) if stroke else 3.0
            eff_sc = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if stroke else (0.1, 0.1, 0.15)
            if component_stroke_enabled and stroke is not None:
                eff_sc, eff_sw = _effective_component_style(stroke, comp_style_target)
            elif point_width_enabled and stroke is not None:
                seg_i, an = point_style_target
                pw = get_point_width(stroke, seg_i, an)
                if pw is None:
                    # fallback to segment endpoint/component width
                    ws, we = _segment_endpoint_widths(stroke, seg_i)
                    pw = ws if an == "p0" else we
                eff_sw = float(pw)
            state["point_style_target"] = point_style_target if point_width_enabled else None

            # Stroke width
            screen.blit(font.render("Stroke width", True, TEXT_COLOR if width_enabled else MUTED_COLOR), (x, y)); y += 22
            wv = font_title.render(str(int(round(eff_sw))), True, ACCENT if width_enabled else MUTED_COLOR)
            screen.blit(wv, (x, y - 2)); y += 30
            state["width_slider"].track.topleft = (x, y)
            state["width_slider"].track.width = PANEL_W - 40
            state["width_slider"].value = int(round(clamp(eff_sw, state["width_slider"].min_v, state["width_slider"].max_v)))
            state["width_slider"].draw(screen)
            y += 20
            algo_label = next((lbl for k, lbl in TRACE_ALGORITHMS if k == stroke.get("algorithm", "fit")), stroke.get("algorithm", "fit"))
            if sel_count == 1:
                screen.blit(font_small.render(f"Tracing: {algo_label}", True, MUTED_COLOR), (x, y)); y += 20
            else:
                y += 4
            if submode == "nodes":
                if point_width_enabled:
                    screen.blit(font_small.render("Stroke width applies to selected point (lines between points)", True, MUTED_COLOR), (x, y)); y += 18
                else:
                    screen.blit(font_small.render("Select an anchor point to set its stroke width", True, MUTED_COLOR), (x, y)); y += 18
            elif submode == "curve" and not component_stroke_enabled:
                screen.blit(font_small.render("Select a curve to edit its stroke", True, MUTED_COLOR), (x, y)); y += 18
            elif submode == "curve" and component_stroke_enabled:
                screen.blit(font_small.render("Stroke applies to selected curve", True, MUTED_COLOR), (x, y)); y += 18

            # --- Modern color picker ---
            screen.blit(font.render("Color", True, TEXT_COLOR if (stroke_color_enabled or fill_enabled) else MUTED_COLOR), (x, y)); y += 22
            # target tabs
            tab_w = (PANEL_W - 40 - 8) // 2
            tab_stroke = pygame.Rect(x, y, tab_w, 26)
            tab_fill = pygame.Rect(x + tab_w + 8, y, tab_w, 26)
            state["tab_stroke_rect"] = tab_stroke if stroke_color_enabled else pygame.Rect(0,0,0,0)
            state["tab_fill_rect"] = tab_fill if fill_enabled else pygame.Rect(0,0,0,0)
            for rect, label, key in ((tab_stroke, "Stroke", "stroke"), (tab_fill, "Fill", "fill")):
                enabled_tab = stroke_color_enabled if key == "stroke" else fill_enabled
                active = (color_target == key) and enabled_tab
                bg = TOOL_ACTIVE if active else (BUTTON_HOVER if (enabled_tab and rect.collidepoint(mouse_pos)) else BUTTON_BG)
                pygame.draw.rect(screen, bg, rect, border_radius=6)
                border_c = ACCENT if active else BUTTON_BORDER
                if not enabled_tab:
                    border_c = BUTTON_BORDER
                pygame.draw.rect(screen, border_c, rect, 2 if active else 1, border_radius=6)
                tc = (ACCENT if active else TEXT_COLOR) if enabled_tab else MUTED_COLOR
                t = font_small.render(label, True, tc)
                screen.blit(t, t.get_rect(center=rect.center))
            y += 32

            # current color for target
            fill_grad = None
            fill_grad_stop = int(state.get("fill_gradient_stop", 0) or 0)
            if color_target == "stroke":
                cur_color = eff_sc if stroke_color_enabled else (stroke.get("stroke_color", (0.1, 0.1, 0.15)) if stroke else (0.1,0.1,0.15))
                cur_color = cur_color or (0.1, 0.1, 0.15)
                display_color = cur_color
            else:
                fill_grad = get_fill_gradient(stroke) if (stroke is not None and 'get_fill_gradient' in globals()) else (stroke.get("fill_gradient") if isinstance(stroke, dict) and isinstance(stroke.get("fill_gradient"), dict) and stroke.get("fill_gradient", {}).get("type") in ("linear","radial") else None)
                if fill_grad is not None:
                    stops_n = 0
                    try:
                        if 'get_gradient_stops' in globals() and callable(globals().get('get_gradient_stops')):
                            stops_n = len(get_gradient_stops(fill_grad) or [])
                        else:
                            stops_n = len(fill_grad.get("stops") or [])
                    except Exception:
                        stops_n = len(fill_grad.get("stops") or [])
                    if stops_n <= 0:
                        fill_grad_stop = 0
                    else:
                        fill_grad_stop = max(0, min(fill_grad_stop, stops_n - 1))
                    state["fill_gradient_stop"] = fill_grad_stop
                    cur_color = get_gradient_stop_color(fill_grad, fill_grad_stop) if 'get_gradient_stop_color' in globals() else (1.0,1.0,1.0,1.0)
                else:
                    cur_color = stroke.get("fill_color", None) if stroke else None
                display_color = cur_color if cur_color is not None else (1.0, 1.0, 1.0)
            h, s, vcol = rgb_to_hsv(*display_color)
            # keep picker state in sync if not dragging
            if not state.get("picker_drag_sv") and not state.get("picker_drag_hue"):
                state["picker_h"] = h
                state["picker_s"] = s
                state["picker_v"] = vcol
            ph = state.get("picker_h", h)
            ps = state.get("picker_s", s)
            pv = state.get("picker_v", vcol)

            # preview + hex + no-fill
            preview = pygame.Rect(x, y, 34, 34)
            pygame.draw.rect(screen, (255, 255, 255), preview, border_radius=6)
            inner = preview.inflate(-6, -6)
            has_fill_now = (cur_color is not None) or (color_target == "fill" and fill_grad is not None)
            if color_target == "fill" and not has_fill_now:
                pygame.draw.rect(screen, (250, 250, 250), inner, border_radius=4)
                pygame.draw.line(screen, (200, 60, 60), inner.topleft, inner.bottomright, 2)
                hex_txt = "None"
            else:
                if color_target == "fill" and fill_grad is not None:
                    # gradient preview (multi-stop)
                    stops = get_gradient_stops(fill_grad) if 'get_gradient_stops' in globals() else (fill_grad.get("stops") or [])
                    for ix in range(inner.w):
                        t = ix / max(1, inner.w - 1)
                        sc = (0.0, 0.0, 0.0, 1.0)
                        try:
                            ordered = sorted(stops, key=lambda s: float((s or {}).get("pos", 0.0))) if stops else []
                            if not ordered:
                                sc = (0.0, 0.0, 0.0, 1.0)
                            elif t <= float(ordered[0].get("pos", 0.0)):
                                sc = color_rgba(ordered[0].get("color"), (0, 0, 0, 1))
                            elif t >= float(ordered[-1].get("pos", 1.0)):
                                sc = color_rgba(ordered[-1].get("color"), (1, 1, 1, 1))
                            else:
                                sc = color_rgba(ordered[-1].get("color"), (1, 1, 1, 1))
                                for a, b in zip(ordered, ordered[1:]):
                                    pa = float(a.get("pos", 0.0)); pb = float(b.get("pos", 1.0))
                                    if pa <= t <= pb:
                                        lt = 0.0 if pb - pa <= 1e-9 else (t - pa) / (pb - pa)
                                        ca = color_rgba(a.get("color"), (0, 0, 0, 1))
                                        cb = color_rgba(b.get("color"), (1, 1, 1, 1))
                                        sc = tuple(ca[k] + (cb[k] - ca[k]) * lt for k in range(4))
                                        break
                        except Exception:
                            sc = (0.0, 0.0, 0.0, 1.0)
                        a = float(sc[3]) if len(sc) >= 4 else 1.0
                        bgv = 235 if (ix // 6) % 2 == 0 else 210
                        r = int((sc[0] * a + (bgv / 255.0) * (1 - a)) * 255)
                        g = int((sc[1] * a + (bgv / 255.0) * (1 - a)) * 255)
                        b = int((sc[2] * a + (bgv / 255.0) * (1 - a)) * 255)
                        pygame.draw.line(screen, (r, g, b), (inner.x + ix, inner.y), (inner.x + ix, inner.bottom - 1))
                else:
                    rgb_show = tuple(int(c * 255) for c in color_rgb(display_color))
                    pygame.draw.rect(screen, rgb_show, inner, border_radius=4)
                hex_txt = rgb_to_hex(display_color)
            pygame.draw.rect(screen, BUTTON_BORDER, preview, 1, border_radius=6)
            screen.blit(font_small.render(hex_txt, True, TEXT_COLOR), (x + 42, y + 9))
            # No fill button
            if color_target == "fill":
                nofill = pygame.Rect(x + 150, y + 4, 70, 26)
                state["nofill_rect"] = nofill
                nf_active = not has_fill_now
                pygame.draw.rect(screen, TOOL_ACTIVE if nf_active else BUTTON_BG, nofill, border_radius=6)
                pygame.draw.rect(screen, ACCENT if nf_active else BUTTON_BORDER, nofill, 1, border_radius=6)
                nt = font_small.render("No fill", True, ACCENT if nf_active else TEXT_COLOR)
                screen.blit(nt, nt.get_rect(center=nofill.center))
            else:
                state["nofill_rect"] = pygame.Rect(0, 0, 0, 0)
            y += 40
            # Fill type + gradient stop controls
            state.setdefault("fill_type_rects", {})
            state.setdefault("fill_stop_rects", {})
            state.setdefault("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0))
            state.setdefault("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0))
            state.setdefault("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
            if color_target == "fill":
                fill_mode = "none"
                if fill_grad is not None:
                    fill_mode = str(fill_grad.get("type", "linear"))
                elif stroke is not None and stroke.get("fill_color") is not None:
                    fill_mode = "solid"
                # two rows: common types + shaped gradient types (spiral, conic, diamond, square)
                label_rows = [
                    [("solid", "Solid"), ("linear", "Linear"), ("radial", "Radial")],
                    [("conic", "Conic"), ("spiral", "Spiral"), ("diamond", "Diamond"), ("square", "Square")],
                ]
                # clear previous rects to avoid stale keys
                state["fill_type_rects"] = {}
                for row in label_rows:
                    n = max(1, len(row))
                    bw = (PANEL_W - 40 - (n - 1) * 4) // n
                    for i, (key, label) in enumerate(row):
                        r = pygame.Rect(x + i * (bw + 4), y, bw, 22)
                        state["fill_type_rects"][key] = r
                        active = (fill_mode == key)
                        bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
                        pygame.draw.rect(screen, bg, r, border_radius=5)
                        pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r, 1, border_radius=5)
                        t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
                        screen.blit(t, t.get_rect(center=r.center))
                    y += 26
                y += 4

                # gradient stops (multi-stop)
                state["fill_stop_rects"] = {}
                state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
                if fill_grad is not None:
                    _get_stops = globals().get("get_gradient_stops")
                    if callable(_get_stops):
                        try:
                            stops = _get_stops(fill_grad) or []
                        except Exception:
                            stops = list(fill_grad.get("stops") or [])
                    else:
                        stops = list(fill_grad.get("stops") or [])
                    if not stops:
                        stops = [{"pos": 0.0, "color": [0.0, 0.0, 0.0, 1.0]},
                                 {"pos": 1.0, "color": [1.0, 1.0, 1.0, 1.0]}]
                    nstops = len(stops)
                    try:
                        fill_grad_stop = int(state.get("fill_gradient_stop", 0) or 0)
                    except Exception:
                        fill_grad_stop = 0
                    fill_grad_stop = max(0, min(fill_grad_stop, nstops - 1))
                    state["fill_gradient_stop"] = fill_grad_stop

                    avail_w = PANEL_W - 40
                    btn_w = 22
                    gap = 6
                    sw_area_w = max(60, avail_w - 2 * (btn_w + gap))
                    # Choose swatch size/gap so all stops remain visible and individually clickable.
                    sw_gap = 6
                    if nstops > 1:
                        sw = int((sw_area_w - (nstops - 1) * sw_gap) / nstops)
                    else:
                        sw = 26
                    if sw < 18:
                        sw_gap = 4
                        sw = int((sw_area_w - (nstops - 1) * sw_gap) / max(1, nstops))
                    if sw < 14:
                        sw_gap = 2
                        sw = int((sw_area_w - (nstops - 1) * sw_gap) / max(1, nstops))
                    sw = max(12, min(26, sw))
                    total_sw_w = nstops * sw + max(0, nstops - 1) * sw_gap
                    start_x = x
                    if total_sw_w > sw_area_w and nstops > 1:
                        # Compress spacing as a last resort to avoid overlapping hit targets.
                        sw_gap = max(1, int((sw_area_w - nstops * sw) / (nstops - 1)))
                        total_sw_w = nstops * sw + max(0, nstops - 1) * sw_gap
                    if total_sw_w < sw_area_w:
                        start_x = x  # left-align; keeps layout stable
                    for i in range(nstops):
                        r = pygame.Rect(start_x + i * (sw + sw_gap), y, sw, sw)
                        # Keep within swatch area without stacking on top of another stop.
                        if r.right > x + sw_area_w:
                            r.x = x + sw_area_w - sw
                        state["fill_stop_rects"][str(i)] = r
                        st = stops[i]
                        if isinstance(st, dict):
                            cstop = color_rgba(st.get("color"), (0, 0, 0, 1))
                        else:
                            try:
                                cstop = color_rgba(st[1], (0, 0, 0, 1))
                            except Exception:
                                cstop = (0.0, 0.0, 0.0, 1.0)
                        draw_swatch(screen, r, cstop, i == fill_grad_stop, mouse_pos)
                    bx = x + sw_area_w + gap
                    add_r = pygame.Rect(bx, y, btn_w, sw)
                    rem_r = pygame.Rect(bx + btn_w + 4, y, btn_w, sw)
                    state["fill_stop_add_rect"] = add_r
                    state["fill_stop_remove_rect"] = rem_r
                    for r, label, enabled_btn in ((add_r, "+", True), (rem_r, "-", nstops > 2)):
                        if enabled_btn:
                            bg = BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG
                            border = BUTTON_BORDER
                            col = TEXT_COLOR
                        else:
                            bg = (235, 238, 242)
                            border = (220, 224, 230)
                            col = MUTED_COLOR
                        pygame.draw.rect(screen, bg, r, border_radius=5)
                        pygame.draw.rect(screen, border, r, 1, border_radius=5)
                        t = font_small.render(label, True, col)
                        screen.blit(t, t.get_rect(center=r.center))
                    y += sw + 6

                    # selected stop position (distance)
                    sel_st = stops[fill_grad_stop] if 0 <= fill_grad_stop < nstops else stops[0]
                    try:
                        sel_pos = float((sel_st or {}).get("pos", 0.0)) if isinstance(sel_st, dict) else float(sel_st[0])
                    except Exception:
                        sel_pos = 0.0
                    sel_pos = clamp(sel_pos, 0.0, 1.0)
                    pos_label = font_small.render(f"Stop {fill_grad_stop + 1}  Pos {int(round(sel_pos * 100))}%", True, TEXT_COLOR)
                    screen.blit(pos_label, (x, y))
                    y += 16
                    pos_h = 10
                    pos_rect = pygame.Rect(x, y, PANEL_W - 40, pos_h)
                    state["fill_stop_pos_rect"] = pos_rect
                    for ix in range(pos_rect.w):
                        tt = ix / max(1, pos_rect.w - 1)
                        samp = (128, 128, 128)
                        try:
                            ordered = []
                            for s in stops:
                                if isinstance(s, dict):
                                    ordered.append((float(s.get("pos", 0.0)), color_rgba(s.get("color"), (0, 0, 0, 1))))
                                else:
                                    try:
                                        ordered.append((float(s[0]), color_rgba(s[1], (0, 0, 0, 1))))
                                    except Exception:
                                        pass
                            ordered.sort(key=lambda t: t[0])
                            if ordered:
                                if tt <= ordered[0][0]:
                                    sc = ordered[0][1]
                                elif tt >= ordered[-1][0]:
                                    sc = ordered[-1][1]
                                else:
                                    sc = ordered[-1][1]
                                    for a, b in zip(ordered, ordered[1:]):
                                        pa, ca = a; pb, cb = b
                                        if pa <= tt <= pb:
                                            lt = 0.0 if pb - pa <= 1e-9 else (tt - pa) / (pb - pa)
                                            sc = tuple(ca[k] + (cb[k] - ca[k]) * lt for k in range(4))
                                            break
                                bgv = 235 if (ix // 6) % 2 == 0 else 210
                                a = float(sc[3]) if len(sc) >= 4 else 1.0
                                samp = (int((sc[0] * a + (bgv / 255.0) * (1 - a)) * 255),
                                        int((sc[1] * a + (bgv / 255.0) * (1 - a)) * 255),
                                        int((sc[2] * a + (bgv / 255.0) * (1 - a)) * 255))
                        except Exception:
                            pass
                        pygame.draw.line(screen, samp, (pos_rect.x + ix, pos_rect.y), (pos_rect.x + ix, pos_rect.bottom - 1))
                    pygame.draw.rect(screen, BUTTON_BORDER, pos_rect, 1, border_radius=4)
                    # Draw markers for all stops so unselected stop colors/positions remain visible.
                    for i, st in enumerate(stops):
                        try:
                            sp = float((st or {}).get("pos", 0.0)) if isinstance(st, dict) else float(st[0])
                        except Exception:
                            sp = 0.0
                        sp = clamp(sp, 0.0, 1.0)
                        if isinstance(st, dict):
                            scol = color_rgba(st.get("color"), (0, 0, 0, 1))
                        else:
                            try:
                                scol = color_rgba(st[1], (0, 0, 0, 1))
                            except Exception:
                                scol = (0.0, 0.0, 0.0, 1.0)
                        sx = pos_rect.x + int(sp * (pos_rect.w - 1))
                        if i == fill_grad_stop:
                            pygame.draw.rect(screen, (255, 255, 255), (sx - 3, pos_rect.y - 2, 6, pos_rect.h + 4), 2, border_radius=2)
                            pygame.draw.rect(screen, (0, 0, 0), (sx - 3, pos_rect.y - 2, 6, pos_rect.h + 4), 1, border_radius=2)
                        else:
                            mr = pygame.Rect(sx - 3, pos_rect.y - 1, 6, pos_rect.h + 2)
                            # show the stop's own color on the marker for visibility
                            sr, sg, sb = [int(clamp(c, 0.0, 1.0) * 255) for c in scol[:3]]
                            pygame.draw.rect(screen, (sr, sg, sb), mr, border_radius=2)
                            pygame.draw.rect(screen, (255, 255, 255), mr, 1, border_radius=2)
                            pygame.draw.rect(screen, (40, 40, 40), mr.inflate(2, 2), 1, border_radius=3)
                    y += pos_h + 8
            else:
                state["fill_type_rects"] = {}
                state["fill_stop_rects"] = {}
                state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)

            # SV square
            sv_w = PANEL_W - 40
            sv_h = 110
            sv_rect = pygame.Rect(x, y, sv_w, sv_h)
            state["sv_rect"] = sv_rect
            # draw SV gradient for current hue
            screen.blit(_sv_surface(ph, sv_w, sv_h), sv_rect.topleft)
            pygame.draw.rect(screen, BUTTON_BORDER, sv_rect, 1, border_radius=4)
            # SV cursor
            cxp = sv_rect.x + int(ps * (sv_w - 1))
            cyp = sv_rect.y + int((1.0 - pv) * (sv_h - 1))
            pygame.draw.circle(screen, (255, 255, 255), (cxp, cyp), 6, 2)
            pygame.draw.circle(screen, (0, 0, 0), (cxp, cyp), 6, 1)
            y += sv_h + 8

            # Hue bar
            hue_h = 14
            hue_rect = pygame.Rect(x, y, sv_w, hue_h)
            state["hue_rect"] = hue_rect
            screen.blit(_hue_bar_surface(sv_w, hue_h), hue_rect.topleft)
            pygame.draw.rect(screen, BUTTON_BORDER, hue_rect, 1, border_radius=4)
            hx = hue_rect.x + int((ph / 360.0) * (sv_w - 1))
            pygame.draw.rect(screen, (255, 255, 255), (hx - 3, hue_rect.y - 2, 6, hue_h + 4), 2, border_radius=2)
            pygame.draw.rect(screen, (0, 0, 0), (hx - 3, hue_rect.y - 2, 6, hue_h + 4), 1, border_radius=2)
            y += hue_h + 8

            # Alpha / opacity slider (stroke always; fill only when a fill color exists)
            show_alpha = (color_target == "stroke") or (cur_color is not None)
            state["alpha_rect"] = pygame.Rect(0, 0, 0, 0)
            if show_alpha:
                cur_alpha = color_alpha(cur_color, 1.0)
                screen.blit(font_small.render(f"Opacity {int(round(cur_alpha * 100))}%", True, TEXT_COLOR), (x, y))
                y += 16
                alpha_h = 12
                alpha_rect = pygame.Rect(x, y, sv_w, alpha_h)
                state["alpha_rect"] = alpha_rect
                # simple gradient bar from transparent to current rgb
                base_rgb = color_rgb(display_color, (1.0, 1.0, 1.0))
                for ix in range(sv_w):
                    a = ix / max(1, sv_w - 1)
                    # blend over a light checker-like background approximation
                    bgv = 235 if (ix // 6) % 2 == 0 else 210
                    r = int((base_rgb[0] * a + (bgv / 255.0) * (1 - a)) * 255)
                    g = int((base_rgb[1] * a + (bgv / 255.0) * (1 - a)) * 255)
                    b = int((base_rgb[2] * a + (bgv / 255.0) * (1 - a)) * 255)
                    pygame.draw.line(screen, (r, g, b), (alpha_rect.x + ix, alpha_rect.y), (alpha_rect.x + ix, alpha_rect.y + alpha_h - 1))
                pygame.draw.rect(screen, BUTTON_BORDER, alpha_rect, 1, border_radius=4)
                ax = alpha_rect.x + int(clamp(cur_alpha, 0.0, 1.0) * (sv_w - 1))
                pygame.draw.rect(screen, (255, 255, 255), (ax - 3, alpha_rect.y - 2, 6, alpha_h + 4), 2, border_radius=2)
                pygame.draw.rect(screen, (0, 0, 0), (ax - 3, alpha_rect.y - 2, 6, alpha_h + 4), 1, border_radius=2)
                y += alpha_h + 8
            else:
                y += 2

            # Preset swatches
            presets = STROKE_SWATCHES
            sw = 26
            state["stroke_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in presets]
            state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in presets]
            for i, col in enumerate(presets):
                r = pygame.Rect(x + i * (sw + 6), y, sw, sw)
                if color_target == "stroke":
                    state["stroke_swatch_rects"][i] = r
                else:
                    state["fill_swatch_rects"][i] = r
                sel_match = (cur_color == col) if cur_color is not None else False
                draw_swatch(screen, r, col, sel_match, mouse_pos)
            y += sw + 10

            # Disable non-applicable style controls
            if not fill_enabled:
                state["tab_fill_rect"] = pygame.Rect(0,0,0,0)
                state["nofill_rect"] = pygame.Rect(0,0,0,0)
                state["fill_type_rects"] = {}
                state["fill_stop_rects"] = {}
                state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
                if not stroke_color_enabled:
                    state["tab_stroke_rect"] = pygame.Rect(0,0,0,0)
            if not (stroke_color_enabled or fill_enabled):
                state["sv_rect"] = pygame.Rect(0,0,0,0)
                state["hue_rect"] = pygame.Rect(0,0,0,0)
                state["alpha_rect"] = pygame.Rect(0,0,0,0)
                state["stroke_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
                state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
                state["fill_type_rects"] = {}
                state["fill_stop_rects"] = {}
                state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
            elif component_stroke_enabled and not fill_enabled:
                # only stroke color editable for selected curve; fill swatches/controls off
                state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
                state["fill_type_rects"] = {}
                state["fill_stop_rects"] = {}
                state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
            state["component_style_target"] = comp_style_target if component_stroke_enabled else None

        sel_label = "-" if sel_count == 0 else (str(next(iter(sel_strokes)) + 1) if sel_count == 1 else f"{sel_count}")
        stats = font_small.render(f"Strokes: {state['stroke_count']} | Selected: {sel_label}", True, MUTED_COLOR)
        screen.blit(stats, (x, y)); y += 20
        submode = state.get("selection_submode", "transform")
        if state.get("redrawing_curve"):
            help_lines = [
                "Draw to redraw selected stroke.",
                "Start/end stay fixed.",
                "Release mouse to apply.",
            ]
        elif sel_count == 0:
            help_lines = [
                "Click stroke to select.",
                "Shift+click: multi-select.",
                "N: cycle Transform/Nodes/Curve.",
                "Shortcuts: Ctrl+Z/Ctrl+Y, C, Esc",
            ]
        elif sel_count > 1:
            help_lines = [
                f"{sel_count} shapes selected.",
                "Shift+click: toggle selection.",
                "Drag/handles: move or transform.",
                "N: cycle Transform/Nodes/Curve.",
                "Delete: remove selected.",
            ]
        elif submode == "transform":
            help_lines = [
                "Drag inside box to move.",
                "Drag handles to scale/rotate.",
                "N: cycle Transform/Nodes/Curve.",
                "Delete: remove selected.",
            ]
        elif submode == "nodes":
            help_lines = [
                "Drag anchors/handles to edit.",
                "Smooth joins mirror handles.",
                "N: cycle Transform/Nodes/Curve.",
                "Delete: remove selected.",
            ]
        else:
            help_lines = [
                "Click a curve/component to select.",
                "Shift+click to select multiple curves.",
                "Select multiple curves and use Join to merge.",
                "Redraw/Split edit the active curve.",
                "N: cycle Transform/Nodes/Curve.",
            ]

    for line in help_lines:
        txt = font_small.render(line, True, MUTED_COLOR)
        screen.blit(txt, (x, y)); y += 18

    # Track total (unscrolled) content height so the main loop can clamp scrolling.
    _scroll = int(state.get("panel_scroll", 0) or 0)
    content_bottom = y + _scroll
    state["panel_content_bottom"] = content_bottom
    max_scroll = max(0, content_bottom + 24 - cfg.HEIGHT)
    if max_scroll > 0:
        # simple scrollbar on the panel's right edge
        _tb = getattr(cfg, "TOP_BAR_H", 0)
        track = pygame.Rect(cfg.PANEL_X + PANEL_W - 7, _tb + 6, 5, cfg.HEIGHT - _tb - 12)
        pygame.draw.rect(screen, (58, 62, 74), track, border_radius=3)
        frac = min(1.0, (cfg.HEIGHT - 40) / max(1, content_bottom))
        thumb_h = max(30, int(track.h * frac))
        thumb_y = track.y + int((track.h - thumb_h) * (clamp(_scroll, 0, max_scroll) / max_scroll))
        pygame.draw.rect(screen, (148, 154, 168), pygame.Rect(track.x, thumb_y, track.w, thumb_h), border_radius=3)

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
    bg = BUTTON_HOVER if hover else (250, 251, 253)
    pygame.draw.rect(screen, bg, r, border_radius=4)
    pygame.draw.rect(screen, BUTTON_BORDER, r, 1, border_radius=4)
    cx, cy = r.centerx, r.centery
    if collapsed:
        pts = [(cx + 2, cy - 6), (cx - 3, cy), (cx + 2, cy + 6)]
    else:
        pts = [(cx - 3, cy - 6), (cx + 2, cy), (cx - 3, cy + 6)]
    pygame.draw.lines(screen, TEXT_COLOR, False, pts, 2)
    if hover:
        draw_tooltip(screen, mouse_pos, "Show sidebar" if collapsed else "Hide sidebar")
    return r
