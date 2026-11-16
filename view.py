"""MVC View: all rendering - cairo canvas drawing, pygame panel/toolbar
and UI widgets. Reads Model data; never mutates it."""

import math

try:
    import cairo  # pycairo (often bundles Cairo on Windows)
    CAIRO_BACKEND = "pycairo"
except Exception:
    import cairocffi as cairo  # type: ignore
    CAIRO_BACKEND = "cairocffi"

import pygame

try:
    import tkinter as tk
    from tkinter import filedialog as tk_filedialog
except Exception:
    tk = None
    tk_filedialog = None

import config as cfg
from config import *
from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

# Model names are available here under their bare names (read-only use).
import model as _model
for _name in dir(_model):
    if not _name.startswith('__'):
        globals().setdefault(_name, getattr(_model, _name))


def make_cairo_surface(width, height):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    return surface

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

def _draw_variable_width_segments(ctx, stroke, seg_indices, base_color=None):
    """Draw selected segments with variable width (e.g. per-point endpoint widths)."""
    segs = segs_of(stroke)
    if not seg_indices:
        return
    ordered = [i for i in sorted(seg_indices) if 0 <= i < len(segs)]
    if not ordered:
        return
    seg_cs = []
    w_start = []
    w_end = []
    for i in ordered:
        ci = _component_index_for_seg(stroke, i)
        sc, _sw = _effective_component_style(stroke, ci)
        ws, we = _segment_endpoint_widths(stroke, i)
        seg_cs.append(sc if base_color is None else base_color)
        w_start.append(max(0.5, float(ws)))
        w_end.append(max(0.5, float(we)))
    ctx.save()
    steps = 8
    for k, i in enumerate(ordered):
        p0, c1, c2, p3 = segs[i]
        ws, we = w_start[k], w_end[k]
        ctx.set_source_rgba(*color_rgba(seg_cs[k], (0.1, 0.1, 0.15, 1.0)))
        pts = []
        for s in range(steps + 1):
            t = s / steps
            x, y = cubic_bezier_point(p0, c1, c2, p3, t)
            dx, dy = cubic_bezier_derivative(p0, c1, c2, p3, t)
            l = math.hypot(dx, dy)
            if l < 1e-6:
                dx, dy = (p3[0] - p0[0], p3[1] - p0[1])
                l = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / l, dx / l
            w = ws + (we - ws) * t
            hw = w * 0.5
            pts.append((x + nx * hw, y + ny * hw, x - nx * hw, y - ny * hw))
        for s in range(steps):
            ax, ay, bx, by = pts[s][0], pts[s][1], pts[s][2], pts[s][3]
            cx, cy, dx_, dy_ = pts[s + 1][0], pts[s + 1][1], pts[s + 1][2], pts[s + 1][3]
            ctx.new_path()
            ctx.move_to(ax, ay); ctx.line_to(cx, cy); ctx.line_to(dx_, dy_); ctx.line_to(bx, by); ctx.close_path()
            ctx.fill()
        x0, y0 = cubic_bezier_point(p0, c1, c2, p3, 0.0)
        x1, y1 = cubic_bezier_point(p0, c1, c2, p3, 1.0)
        ctx.set_source_rgba(*color_rgba(seg_cs[k], (0.1, 0.1, 0.15, 1.0)))
        ctx.new_path(); ctx.arc(x0, y0, ws * 0.5, 0, 2 * math.pi); ctx.fill()
        ctx.new_path(); ctx.arc(x1, y1, we * 0.5, 0, 2 * math.pi); ctx.fill()
    ctx.restore()

def draw_stroke_path(ctx, stroke):
    if _stroke_has_wave(stroke):
        return draw_stroke_path_distorted(ctx, stroke)
    segs = segs_of(stroke)
    if not segs:
        return False
    hidden = set()
    if isinstance(stroke, dict):
        hidden = set(stroke.get("hidden_segs", set()) or set())
    visible = [i for i in range(len(segs)) if i not in hidden]
    if not visible:
        return False
    ctx.new_path()
    drew = False
    for i in range(len(segs)):
        if i in hidden:
            continue
        p0, c1, c2, p3 = segs[i]
        if not drew or not _pts_close(segs[i][0], segs[i - 1][3], 1e-3):
            ctx.move_to(p0[0], p0[1])
        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
        drew = True
    # if closed and fully visible, close path for nicer fill
    if len(visible) == len(segs) and _pts_close(segs[0][0], segs[-1][3], 6.0):
        ctx.close_path()
    return True

def draw_stroke_path_distorted(ctx, stroke):
    segs = segs_of(stroke)
    if not segs:
        return False
    hidden = set()
    if isinstance(stroke, dict):
        hidden = set(stroke.get("hidden_segs", set()) or set())
    visible = [i for i in range(len(segs)) if i not in hidden]
    if not visible:
        return False
    comps = _stroke_components(stroke)
    ranges = _component_ranges(stroke)
    ctx.new_path()
    drew_any = False
    for ci, (s0, s1) in enumerate(ranges):
        comp_visible = [i for i in range(s0, min(s1, len(segs))) if i not in hidden]
        if not comp_visible:
            continue
        poly = _component_distorted_polyline(stroke, ci)
        if poly and len(poly) >= 2 and _component_wave_enabled(comps[ci] if ci < len(comps) else {}):
            # draw distorted polyline for whole component if fully/mostly visible; if partial hidden, fall back per-seg
            if len(comp_visible) == (min(s1, len(segs)) - s0):
                if not drew_any or not _pts_close(poly[0], segs[s0][0], 1e-3):
                    ctx.move_to(poly[0][0], poly[0][1])
                else:
                    ctx.line_to(poly[0][0], poly[0][1])
                for pt in poly[1:]:
                    ctx.line_to(pt[0], pt[1])
                drew_any = True
                continue
            # partial hidden: sample base segs for visible ones with distortion per seg
            for i in comp_visible:
                p0, c1, c2, p3 = segs[i]
                steps = 20
                pts = [cubic_bezier_point(p0, c1, c2, p3, t / steps) for t in range(steps + 1)]
                # approximate local distortion by sampling component and mapping? easier: draw base for hidden-partial case
                if not drew_any or not _pts_close(pts[0], segs[i - 1][3] if i > 0 else pts[0], 1e-3):
                    ctx.move_to(pts[0][0], pts[0][1])
                for pt in pts[1:]:
                    ctx.line_to(pt[0], pt[1])
                drew_any = True
            continue
        # base draw for this component range
        for i in comp_visible:
            p0, c1, c2, p3 = segs[i]
            if not drew_any or not _pts_close(segs[i][0], segs[i - 1][3] if i > 0 else segs[i][0], 1e-3):
                ctx.move_to(p0[0], p0[1])
            ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
            drew_any = True
    if not drew_any:
        return False
    if len(visible) == len(segs) and _pts_close(segs[0][0], segs[-1][3], 6.0):
        ctx.close_path()
    return True

def draw_scene(cairo_surface, strokes, active_stroke=None, snap_point=None, selected_index=None, selected_indices=None, edit_mode=False, selection_submode="transform", selected_curve=None, snap_kind="connect", redrawing_curve=None, ref_img=None):
    # Backward compat: selected_index (single) or selected_indices (collection)
    if selected_indices is None and selected_index is not None:
        selected_indices = selected_index
    sel_set = _selection_set(selected_indices)

    ctx = cairo.Context(cairo_surface)
    try:
        ctx.set_antialias(cairo.ANTIALIAS_BEST)
    except Exception:
        pass
    ctx.set_source_rgb(*BG_COLOR)
    ctx.paint()

    # Reference image, behind strokes
    if ref_img and ref_img.get("visible", True) and ref_img.get("surface") is not None:
        try:
            rsurf = ref_img["surface"]
            ctx.save()
            ctx.translate(float(ref_img.get("x", 0)), float(ref_img.get("y", 0)))
            s = float(ref_img.get("scale", 1.0))
            ctx.scale(s, s)
            ctx.set_source_surface(rsurf, 0, 0)
            ctx.paint_with_alpha(clamp(float(ref_img.get("opacity", 0.5)), 0.0, 1.0))
            ctx.restore()
        except Exception:
            pass

    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    redraw_target = None
    if redrawing_curve is not None:
        redraw_target = (redrawing_curve.get("stroke_idx"), redrawing_curve.get("comp_idx", redrawing_curve.get("seg_idx")))

    def _draw_hidden_segments(ctx, stroke, segs, hidden_set, stroke_width):
        if not hidden_set:
            return
        ctx.save()
        try:
            ctx.set_dash([6, 4])
        except Exception:
            pass
        # distinct style for hidden curves in edit modes
        ctx.set_source_rgba(0.95, 0.45, 0.2, 0.55)
        ctx.set_line_width(max(1.5, float(stroke_width)))
        ctx.new_path()
        for i in sorted(hidden_set):
            if 0 <= i < len(segs):
                p0, c1, c2, p3 = segs[i]
                ctx.move_to(p0[0], p0[1])
                ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
        ctx.stroke()
        try:
            ctx.set_dash([])
        except Exception:
            pass
        ctx.restore()

    def _draw_stroke_segments(ctx, stroke, seg_indices, stroke_color, stroke_width):
        if not seg_indices:
            return
        seg_set = set(seg_indices)
        if _stroke_needs_variable_width(stroke, seg_set):
            _draw_variable_width_segments(ctx, stroke, seg_set, None)
            return
        segs_all = segs_of(stroke)
        ranges = _component_ranges(stroke)
        comps = _stroke_components(stroke)

        def _draw_polyline(pts):
            if not pts or len(pts) < 2:
                return False
            ctx.move_to(pts[0][0], pts[0][1])
            for pt in pts[1:]:
                ctx.line_to(pt[0], pt[1])
            return True

        # draw by components to support per-component styles and wave distortion
        for ci, (s0, s1) in enumerate(ranges):
            idxs = [i for i in range(s0, min(s1, len(segs_all))) if i in seg_set]
            if not idxs:
                continue
            sc_i, sw_i = _effective_component_style(stroke, ci)
            comp = comps[ci] if ci < len(comps) else {}
            ctx.new_path()
            drew_c = False
            if _component_wave_enabled(comp) and len(idxs) == (min(s1, len(segs_all)) - s0):
                poly = sample_distorted_component(stroke, ci)
                if poly and len(poly) >= 2:
                    drew_c = _draw_polyline(poly)
            if not drew_c:
                for i in idxs:
                    p0, c1, c2, p3 = segs_all[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                    drew_c = True
            if drew_c:
                ctx.set_source_rgba(*color_rgba(sc_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_color, (0.1, 0.1, 0.15, 1.0)))
                ctx.set_line_width(sw_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_width)
                ctx.stroke()


    for idx, stroke in enumerate(strokes):
        segs = segs_of(stroke)
        if not segs:
            continue
        stroke_color = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if isinstance(stroke, dict) else (0.1, 0.1, 0.15)
        stroke_width = stroke.get("stroke_width", 3.0) if isinstance(stroke, dict) else 3.0
        fill_color = stroke.get("fill_color") if isinstance(stroke, dict) else None
        hidden = set(stroke.get("hidden_segs", set()) or set()) if isinstance(stroke, dict) else set()
        is_selected_stroke = (idx in sel_set and edit_mode)
        show_hidden = edit_mode and selection_submode in ("curve", "nodes") and bool(hidden)

        # Hint: show original/base (guide) shape for distorted curves so they remain selectable
        if _stroke_has_wave(stroke):
            comps = _stroke_components(stroke)
            ranges = _component_ranges(stroke)
            ctx.save()
            try:
                ctx.set_dash([4, 4])
            except Exception:
                pass
            for ci, (s0, s1) in enumerate(ranges):
                comp = comps[ci] if ci < len(comps) else {}
                if not _component_wave_enabled(comp):
                    continue
                ctx.new_path()
                drew_g = False
                for i in range(s0, min(s1, len(segs))):
                    if i in hidden:
                        continue
                    p0, c1, c2, p3 = segs[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                    drew_g = True
                if drew_g:
                    ctx.set_source_rgba(0.1, 0.45, 0.95, 0.35)
                    ctx.set_line_width(max(1.0, float(stroke_width) * 0.8))
                    ctx.stroke()
            try:
                ctx.set_dash([])
            except Exception:
                pass
            ctx.restore()

        if redraw_target and redraw_target[0] == idx:
            comp_i = redraw_target[1]
            ranges = _component_ranges(stroke)
            in_redraw = set()
            if 0 <= comp_i < len(ranges):
                s0, s1 = ranges[comp_i]
                in_redraw = set(range(s0, min(s1, len(segs))))

            # draw non-redraw, non-hidden segments normally
            normal_segs_set = {i for i in range(len(segs)) if i not in in_redraw and i not in hidden}
            if normal_segs_set:
                # selection highlight for normal part
                if is_selected_stroke:
                    ctx.new_path()
                    for i in sorted(normal_segs_set):
                        p0, c1, c2, p3 = segs[i]
                        ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                    ctx.set_source_rgba(0.1, 0.45, 0.95, 0.35)
                    ctx.set_line_width(stroke_width + 4.0)
                    ctx.stroke()
                _draw_stroke_segments(ctx, stroke, normal_segs_set, stroke_color, stroke_width)

            # draw redrawn component as bright yellow low-opacity template
            if in_redraw:
                ctx.new_path()
                for i in sorted(in_redraw):
                    p0, c1, c2, p3 = segs[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                ctx.set_source_rgba(1.0, 1.0, 0.0, 0.35)
                ctx.set_line_width(max(stroke_width, 2.0))
                ctx.stroke()
            # hidden segments styled (except those being redrawn template)
            if show_hidden:
                _draw_hidden_segments(ctx, stroke, segs, hidden - in_redraw, stroke_width)
            continue

        # Selection highlight behind the stroke so the actual stroke color stays visible
        if is_selected_stroke and draw_stroke_path(ctx, stroke):
            ctx.set_source_rgba(0.1, 0.45, 0.95, 0.35)
            ctx.set_line_width(stroke_width + 4.0)
            ctx.stroke()

        visible_segs = [i for i in range(len(segs)) if i not in hidden]
        if fill_color is not None and draw_stroke_path(ctx, stroke):
            ctx.set_source_rgba(*color_rgba(fill_color, (0.0, 0.0, 0.0, 1.0)))
            if _stroke_needs_variable_width(stroke, visible_segs):
                ctx.fill()
                _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
            else:
                ctx.fill_preserve()
                if _stroke_has_component_styles(stroke):
                    ctx.new_path()
                _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
        else:
            _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)

        # Show hidden curves differently in edit curve/nodes modes for easier selection
        if show_hidden:
            _draw_hidden_segments(ctx, stroke, segs, hidden, stroke_width)

    # Draw selection overlays (nodes for single selection, combined bbox for transform)
    if edit_mode and sel_set:
        selected_in_range = [i for i in sel_set if 0 <= i < len(strokes)]
        # Highlight selected stroke/component in curve edit mode
        if selection_submode == "curve" and selected_curve is not None:
            si, comp_i = selected_curve
            if si in selected_in_range and 0 <= si < len(strokes):
                segs = segs_of(strokes[si])
                ranges = _component_ranges(strokes[si])
                if 0 <= comp_i < len(ranges):
                    s0, s1 = ranges[comp_i]
                    comp_range = range(s0, min(s1, len(segs)))
                    # highlight component curve (node editing moved to Nodes mode)
                    for seg_i in comp_range:
                        p0, c1, c2, p3 = segs[seg_i]
                        ctx.new_path()
                        ctx.move_to(p0[0], p0[1])
                        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                        ctx.set_source_rgba(1.0, 0.45, 0.1, 0.9)
                        w = strokes[si].get("stroke_width", 3.0) if isinstance(strokes[si], dict) else 3.0
                        ctx.set_line_width(max(4.0, w + 2.0))
                        ctx.stroke()
        if selection_submode == "nodes" and len(selected_in_range) == 1:
            idx = selected_in_range[0]
            segs = segs_of(strokes[idx])
            ctx.set_source_rgba(0.4, 0.5, 0.6, 0.8)
            ctx.set_line_width(1.0)
            for si, (p0, c1, c2, p3) in enumerate(segs):
                ctx.move_to(p0[0], p0[1]); ctx.line_to(c1[0], c1[1])
                ctx.move_to(p3[0], p3[1]); ctx.line_to(c2[0], c2[1])
            ctx.stroke()
            for si, (p0, c1, c2, p3) in enumerate(segs):
                if si == 0:
                    for pt in (p0,):
                        ctx.set_source_rgb(1, 1, 1); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.fill()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(2.0); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.stroke()
                for pt in (p3,):
                    ctx.set_source_rgb(1, 1, 1); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(2.0); ctx.arc(pt[0], pt[1], 4.5, 0, 2*math.pi); ctx.stroke()
                for pt in (c1, c2):
                    ctx.set_source_rgb(1, 1, 1); ctx.rectangle(pt[0]-3.5, pt[1]-3.5, 7, 7); ctx.fill_preserve()
                    ctx.set_source_rgb(0.85, 0.35, 0.2); ctx.set_line_width(1.5); ctx.stroke()
        elif selection_submode == "transform":
            bbox = combined_bbox(strokes, selected_in_range)
            if bbox:
                x1, y1, x2, y2 = bbox
                try:
                    ctx.set_dash([6, 4])
                except Exception:
                    pass
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.5)
                ctx.rectangle(x1, y1, x2 - x1, y2 - y1)
                ctx.stroke()
                try:
                    ctx.set_dash([])
                except Exception:
                    pass
                handles = bbox_handles(bbox)
                mx = (x1 + x2) / 2
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.0)
                ctx.move_to(mx, y1); ctx.line_to(handles["rot"][0], handles["rot"][1])
                ctx.stroke()
                for name, pt in handles.items():
                    if name == "rot":
                        ctx.set_source_rgb(1, 1, 1); ctx.arc(pt[0], pt[1], 5.0, 0, 2*math.pi); ctx.fill()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(1.5); ctx.arc(pt[0], pt[1], 5.0, 0, 2*math.pi); ctx.stroke()
                    else:
                        ctx.set_source_rgb(1, 1, 1); ctx.rectangle(pt[0]-4, pt[1]-4, 8, 8); ctx.fill_preserve()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(1.5); ctx.stroke()
        elif selection_submode == "nodes" and len(selected_in_range) > 1:
            # Multi-selection: show combined bbox (node editing requires single selection)
            bbox = combined_bbox(strokes, selected_in_range)
            if bbox:
                x1, y1, x2, y2 = bbox
                try:
                    ctx.set_dash([4, 4])
                except Exception:
                    pass
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.2)
                ctx.rectangle(x1, y1, x2 - x1, y2 - y1)
                ctx.stroke()
                try:
                    ctx.set_dash([])
                except Exception:
                    pass

    if active_stroke and len(active_stroke) >= 2:
        ctx.set_source_rgb(*ACTIVE_COLOR)
        ctx.set_line_width(2.0)
        ctx.new_path()
        ctx.move_to(active_stroke[0][0], active_stroke[0][1])
        for x, y in active_stroke[1:]:
            ctx.line_to(x, y)
        ctx.stroke()

    if snap_point is not None:
        x, y = snap_point
        if snap_kind == "assist":
            r = 10.0
            ctx.new_path()
            ctx.move_to(x, y - r); ctx.line_to(x + r, y); ctx.line_to(x, y + r); ctx.line_to(x - r, y); ctx.close_path()
            ctx.set_source_rgba(0.2, 0.6, 1.0, 0.22)
            ctx.fill_preserve()
            ctx.set_source_rgb(0.15, 0.45, 0.95)
            ctx.set_line_width(2.0)
            ctx.stroke()
            ctx.new_path()
            ctx.move_to(x, y - 2.5); ctx.line_to(x + 2.5, y); ctx.line_to(x, y + 2.5); ctx.line_to(x - 2.5, y); ctx.close_path()
            ctx.fill()
        else:
            ctx.set_source_rgba(0.2, 0.6, 1.0, 0.25)
            ctx.arc(x, y, 11.0, 0, 2 * math.pi); ctx.fill()
            ctx.set_source_rgb(0.15, 0.45, 0.95)
            ctx.set_line_width(2.0)
            ctx.arc(x, y, 11.0, 0, 2 * math.pi); ctx.stroke()
            ctx.arc(x, y, 2.5, 0, 2 * math.pi); ctx.fill()

    cairo_surface.flush()

def surface_to_pygame(cairo_surface):
    width = cairo_surface.get_width()
    height = cairo_surface.get_height()
    buf = cairo_surface.get_data()
    try:
        data = buf.tobytes()
    except Exception:
        data = bytes(buf)
    return pygame.image.frombuffer(data, (width, height), "BGRA")

def load_reference_image(path):
    """Load image file into a cairo ImageSurface (ARGB32) for reference drawing."""
    if not path:
        return None
    try:
        # Prefer cairo PNG loader when possible
        if str(path).lower().endswith(".png"):
            surf = cairo.ImageSurface.create_from_png(path)
            w, h = surf.get_width(), surf.get_height()
        else:
            img = pygame.image.load(path).convert_alpha()
            w, h = img.get_width(), img.get_height()
            data = pygame.image.tostring(img, "BGRA")
            buf = bytearray(data)
            surf = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, w, h)
            # keep buffer alive
            surf._buf = buf
        return {"surface": surf, "w": w, "h": h, "x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 0.5, "visible": True, "path": path}
    except Exception:
        return None

def pick_reference_image_path():
    if tk is None or tk_filedialog is None:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        path = tk_filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp"), ("All files", "*.*")],
        )
        root.destroy()
        return path or None
    except Exception:
        return None

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

def draw_left_toolbar(screen, mouse_pos, tool_mode, btn_draw, btn_select, btn_undo=None, btn_redo=None, can_undo=False, can_redo=False):
    bar = pygame.Rect(0, 0, LEFT_BAR_W, cfg.HEIGHT)
    pygame.draw.rect(screen, TOOLBAR_BG, bar)
    pygame.draw.line(screen, PANEL_BORDER, (LEFT_BAR_W - 1, 0), (LEFT_BAR_W - 1, cfg.HEIGHT), 2)
    items = []
    if btn_undo is not None:
        items.append(("undo", btn_undo, False, can_undo))
    if btn_redo is not None:
        items.append(("redo", btn_redo, False, can_redo))
    items.extend((
        ("draw", btn_draw, tool_mode == "draw", True),
        ("selection", btn_select, tool_mode == "selection", True),
    ))
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

def draw_panel(screen, fonts, mouse_pos, state):
    font, font_small, font_title = fonts
    panel_rect = pygame.Rect(cfg.PANEL_X, 0, PANEL_W, cfg.HEIGHT)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    pygame.draw.line(screen, PANEL_BORDER, (cfg.PANEL_X, 0), (cfg.PANEL_X, cfg.HEIGHT), 2)

    x = cfg.PANEL_X + 20
    y = 18 - int(state.get("panel_scroll", 0) or 0)
    title = font_title.render("Draw" if state["tool_mode"] == "draw" else "Selection", True, TEXT_COLOR)
    screen.blit(title, (x, y))
    y += 36

    if state["tool_mode"] == "draw":
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
        b.draw(screen, font, mouse_pos, active=state["boost_points"]); y += 44

        # Tracing algorithm (per new stroke)
        screen.blit(font.render("Tracing", True, TEXT_COLOR), (x, y)); y += 22
        algo = state.get("trace_algorithm", "fit")
        rects = {}
        bw = (PANEL_W - 40 - 8) // 3
        for i, (key, label) in enumerate(TRACE_ALGORITHMS):
            r = pygame.Rect(x + i * (bw + 4), y, bw, 28)
            rects[key] = r
            active = (algo == key)
            bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r, 2 if active else 1, border_radius=6)
            t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
        state["trace_algo_rects"] = rects
        y += 36

        # Tool: Pen / Eraser
        screen.blit(font.render("Tool", True, TEXT_COLOR), (x, y)); y += 22
        draw_tool = state.get("draw_tool", "pen")
        pen_r = pygame.Rect(x, y, (PANEL_W - 40 - 8) // 2, 28)
        er_r = pygame.Rect(x + (PANEL_W - 40 - 8) // 2 + 8, y, (PANEL_W - 40 - 8) - ((PANEL_W - 40 - 8) // 2 + 8), 28)
        state["draw_tool_pen_rect"] = pen_r
        state["draw_tool_eraser_rect"] = er_r
        for r, key, label in ((pen_r, "pen", "Pen"), (er_r, "eraser", "Eraser")):
            active_t = (draw_tool == key)
            bg = TOOL_ACTIVE if active_t else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, ACCENT if active_t else BUTTON_BORDER, r, 2 if active_t else 1, border_radius=6)
            t = font_small.render(label, True, ACCENT if active_t else TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
        y += 36

        # Shape target (doodle -> standard shape)
        screen.blit(font.render("Shape", True, TEXT_COLOR), (x, y)); y += 22
        draw_shape = state.get("draw_shape", "freehand")
        shape_rects = {}
        cols = 4
        gap = 6
        bw_s = (PANEL_W - 40 - gap * (cols - 1)) // cols
        for i, (key, label) in enumerate(DRAW_SHAPES):
            row, col = divmod(i, cols)
            r = pygame.Rect(x + col * (bw_s + gap), y + row * 30, bw_s, 26)
            shape_rects[key] = r
            active_s = (draw_shape == key)
            bg = TOOL_ACTIVE if active_s else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, ACCENT if active_s else BUTTON_BORDER, r, 2 if active_s else 1, border_radius=6)
            t = font_small.render(label, True, ACCENT if active_s else TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
        state["draw_shape_rects"] = shape_rects
        rows = (len(DRAW_SHAPES) + cols - 1) // cols
        y += rows * 30 + 8

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
        for r, label in ((load_r, "Load"), (vis_r, vis_label), (clear_r, "Clear")):
            bg = BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, BUTTON_BORDER, r, 1, border_radius=6)
            t = font_small.render(label, True, TEXT_COLOR)
            screen.blit(t, t.get_rect(center=r.center))
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
        y += 4

        label2 = font.render("Actions", True, TEXT_COLOR)
        screen.blit(label2, (x, y)); y += 28
        for i, b in enumerate(state["buttons"]["actions"]):
            b.rect.topleft = (x, y + i * 42)
            b.draw(screen, font, mouse_pos)
        y += len(state["buttons"]["actions"]) * 42 + 12

        stats = font_small.render(f"Strokes: {state['stroke_count']} | Backend: {CAIRO_BACKEND}", True, MUTED_COLOR)
        screen.blit(stats, (x, y)); y += 24
        if state.get("draw_tool", "pen") == "eraser":
            help_lines = [
                "Eraser: click curve/edge to remove.",
                "Switch to Pen to draw strokes/shapes.",
                "Shortcuts: Ctrl+Z/Ctrl+Y, C, Esc",
            ]
        else:
            help_lines = [
                "Pen: drag on canvas to draw.",
                "Pick a Shape to create standard shapes.",
                "Hover endpoints to snap / auto-merge.",
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
        y += 38

        sel_stroke = state.get("selected_obj")
        # Curve/stroke-edit controls (single selection in curve mode)
        state.setdefault("curve_hide_rect", pygame.Rect(0,0,0,0))
        state.setdefault("curve_redraw_rect", pygame.Rect(0,0,0,0))
        if submode == "curve" and sel_count == 1 and sel_stroke is not None:
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
                redraw_rect = pygame.Rect(x, y, PANEL_W - 40, 30)
                state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
                state["curve_redraw_rect"] = redraw_rect
                bg = BUTTON_HOVER if redraw_rect.collidepoint(mouse_pos) else BUTTON_BG
                pygame.draw.rect(screen, bg, redraw_rect, border_radius=6)
                pygame.draw.rect(screen, BUTTON_BORDER, redraw_rect, 1, border_radius=6)
                t = font_small.render("Redraw stroke", True, TEXT_COLOR)
                screen.blit(t, t.get_rect(center=redraw_rect.center))
                y += 38

                # Curve styles list (non-destructive). Styles are added to this curve.
                screen.blit(font_small.render("Curve styles", True, TEXT_COLOR), (x, y)); y += 20
                comp = comps[comp_i] if 0 <= comp_i < len(comps) else {}
                styles = _component_styles(comp)
                has_wave = any(isinstance(s, dict) and s.get("type") == "wave" for s in styles)
                state["wave_add_rect"] = pygame.Rect(0,0,0,0)
                state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
                state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
                state["wave_slider_rects"] = {}

                if has_wave:
                    waves_all = _get_wave_styles(comp)
                    n_waves = len(waves_all)
                    # active (expanded) wave index, clamped to the current stack
                    wi = int(state.get("wave_active_index", 0) or 0)
                    if not (0 <= wi < n_waves):
                        wi = max(0, n_waves - 1)
                    wave = waves_all[wi]
                    enabled = bool(wave.get("enabled"))
                    shape = str(wave.get("shape", "sine") or "sine").lower()

                    # ---- modifier stack rows: click a row to edit that wave ----
                    state["wave_row_rects"] = []
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
                            xbg = BUTTON_HOVER if rem_rect.collidepoint(mouse_pos) else BUTTON_BG
                            pygame.draw.rect(screen, xbg, rem_rect, border_radius=5)
                            pygame.draw.rect(screen, BUTTON_BORDER, rem_rect, 1, border_radius=5)
                            xt = font_small.render("\u00d7", True, (205, 115, 115))
                            screen.blit(xt, xt.get_rect(center=rem_rect.center))
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
                    at = font_small.render("+ Add Wave distortion", True, TEXT_COLOR)
                    screen.blit(at, at.get_rect(center=add_rect.center))
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
                    state["wave_shape_rects"] = {}
                    state["wave_row_rects"] = []
                    bg = BUTTON_HOVER if add_rect.collidepoint(mouse_pos) else BUTTON_BG
                    pygame.draw.rect(screen, bg, add_rect, border_radius=6)
                    pygame.draw.rect(screen, BUTTON_BORDER, add_rect, 1, border_radius=6)
                    t = font_small.render("+ Add Wave distortion", True, TEXT_COLOR)
                    screen.blit(t, t.get_rect(center=add_rect.center))
                    y += 34
                    screen.blit(font_small.render("No curve styles added", True, MUTED_COLOR), (x, y)); y += 18
            else:
                screen.blit(font_small.render("Click a stroke to edit separately", True, MUTED_COLOR), (x, y)); y += 24
                state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
                state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
                state["wave_toggle_rect"] = pygame.Rect(0,0,0,0)
                state["wave_add_rect"] = pygame.Rect(0,0,0,0)
                state["wave_remove_rect"] = pygame.Rect(0,0,0,0)
                state["wave_slider_rects"] = {}
                state["wave_shape_rects"] = {}
                state["wave_row_rects"] = []
        else:
            state["curve_hide_rect"] = pygame.Rect(0,0,0,0)
            state["curve_redraw_rect"] = pygame.Rect(0,0,0,0)
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
            if color_target == "stroke":
                cur_color = eff_sc if stroke_color_enabled else (stroke.get("stroke_color", (0.1, 0.1, 0.15)) if stroke else (0.1,0.1,0.15))
                cur_color = cur_color or (0.1, 0.1, 0.15)
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
            if color_target == "fill" and cur_color is None:
                pygame.draw.rect(screen, (250, 250, 250), inner, border_radius=4)
                pygame.draw.line(screen, (200, 60, 60), inner.topleft, inner.bottomright, 2)
                hex_txt = "None"
            else:
                rgb_show = tuple(int(c * 255) for c in display_color)
                pygame.draw.rect(screen, rgb_show, inner, border_radius=4)
                hex_txt = rgb_to_hex(display_color)
            pygame.draw.rect(screen, BUTTON_BORDER, preview, 1, border_radius=6)
            screen.blit(font_small.render(hex_txt, True, TEXT_COLOR), (x + 42, y + 9))
            # No fill button
            if color_target == "fill":
                nofill = pygame.Rect(x + 150, y + 4, 70, 26)
                state["nofill_rect"] = nofill
                nf_active = (cur_color is None)
                pygame.draw.rect(screen, TOOL_ACTIVE if nf_active else BUTTON_BG, nofill, border_radius=6)
                pygame.draw.rect(screen, ACCENT if nf_active else BUTTON_BORDER, nofill, 1, border_radius=6)
                nt = font_small.render("No fill", True, ACCENT if nf_active else TEXT_COLOR)
                screen.blit(nt, nt.get_rect(center=nofill.center))
            else:
                state["nofill_rect"] = pygame.Rect(0, 0, 0, 0)
            y += 40

            # SV square
            sv_w = PANEL_W - 40
            sv_h = 110
            sv_rect = pygame.Rect(x, y, sv_w, sv_h)
            state["sv_rect"] = sv_rect
            # draw SV gradient for current hue
            sv_surf = pygame.Surface((sv_w, sv_h))
            for ix in range(sv_w):
                s_val = ix / max(1, sv_w - 1)
                for iy in range(sv_h):
                    v_val = 1.0 - iy / max(1, sv_h - 1)
                    col = hsv_to_rgb(ph, s_val, v_val)
                    sv_surf.set_at((ix, iy), tuple(int(c * 255) for c in col))
            screen.blit(sv_surf, sv_rect.topleft)
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
            for ix in range(sv_w):
                hh = (ix / max(1, sv_w - 1)) * 360.0
                col = hsv_to_rgb(hh, 1.0, 1.0)
                pygame.draw.line(screen, tuple(int(c * 255) for c in col), (hue_rect.x + ix, hue_rect.y), (hue_rect.x + ix, hue_rect.y + hue_h - 1))
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
                if not stroke_color_enabled:
                    state["tab_stroke_rect"] = pygame.Rect(0,0,0,0)
            if not (stroke_color_enabled or fill_enabled):
                state["sv_rect"] = pygame.Rect(0,0,0,0)
                state["hue_rect"] = pygame.Rect(0,0,0,0)
                state["alpha_rect"] = pygame.Rect(0,0,0,0)
                state["stroke_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
                state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
            elif component_stroke_enabled and not fill_enabled:
                # only stroke color editable for selected curve; fill swatches/controls off
                state["fill_swatch_rects"] = [pygame.Rect(0,0,0,0) for _ in STROKE_SWATCHES]
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
                "Click a stroke/component to select.",
                "Drag its points/handles to edit separately.",
                "Redraw replaces selected stroke/component.",
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
        track = pygame.Rect(cfg.PANEL_X + PANEL_W - 7, 6, 5, cfg.HEIGHT - 12)
        pygame.draw.rect(screen, (58, 62, 74), track, border_radius=3)
        frac = min(1.0, (cfg.HEIGHT - 40) / max(1, content_bottom))
        thumb_h = max(30, int(track.h * frac))
        thumb_y = track.y + int((track.h - thumb_h) * (clamp(_scroll, 0, max_scroll) / max_scroll))
        pygame.draw.rect(screen, (148, 154, 168), pygame.Rect(track.x, thumb_y, track.w, thumb_h), border_radius=3)
