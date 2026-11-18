"""View: cairo canvas rendering and reference image handling."""

import math

try:
    import cairo  # pycairo (often bundles Cairo on Windows)
    CAIRO_BACKEND = "pycairo"
except Exception:
    import cairocffi as cairo  # type: ignore
    CAIRO_BACKEND = "cairocffi"

import pygame

import config as cfg
from config import *
from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))


def make_cairo_surface(width, height):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    return surface

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

def draw_scene(cairo_surface, strokes, active_stroke=None, snap_point=None, selected_index=None, selected_indices=None, edit_mode=False, selection_submode="transform", selected_curve=None, selected_curves=None, snap_kind="connect", redrawing_curve=None, ref_img=None, view_zoom=None, view_pan=None, pivot_pos=None, for_export=False, transform_handle_mode="scale"):
    # Backward compat: selected_index (single) or selected_indices (collection)
    if selected_indices is None and selected_index is not None:
        selected_indices = selected_index
    sel_set = _selection_set(selected_indices)

    if view_zoom is None:
        view_zoom = getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0
    if view_pan is None:
        view_pan = (getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0))

    ctx = cairo.Context(cairo_surface)
    try:
        ctx.set_antialias(cairo.ANTIALIAS_BEST)
    except Exception:
        pass
    # background in screen/viewport space (skip for export: keep transparent/no background)
    if not for_export:
        ctx.save()
        ctx.identity_matrix()
        ctx.set_source_rgb(*BG_COLOR)
        ctx.paint()
        ctx.restore()

    # world/view transform
    ctx.save()
    ctx.translate(float(view_pan[0]), float(view_pan[1]))
    ctx.scale(float(view_zoom), float(view_zoom))

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

    def _draw_arrowhead(ctx, segs, color, width):
        """Draw an arrowhead at the end of the last segment (line shapes)."""
        if not segs:
            return
        try:
            p2, p3 = segs[-1][2], segs[-1][3]
        except Exception:
            return
        dx, dy = p3[0] - p2[0], p3[1] - p2[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            try:
                p2, p3 = segs[-1][0], segs[-1][3]
                dx, dy = p3[0] - p2[0], p3[1] - p2[1]
                length = math.hypot(dx, dy)
            except Exception:
                return
        if length < 1e-6:
            return
        ux, uy = dx / length, dy / length
        size = max(9.0, float(width or 3.0) * 3.5)
        ang = math.radians(26.0)
        ca, sa = math.cos(ang), math.sin(ang)
        ctx.new_path()
        for sign in (-1.0, 1.0):
            rx = -ux * ca + uy * sa * sign
            ry = -ux * sa * sign - uy * ca
            ctx.move_to(p3[0], p3[1])
            ctx.line_to(p3[0] + rx * size, p3[1] + ry * size)
        ctx.set_source_rgba(*color_rgba(color, (0.1, 0.1, 0.15, 1.0)))
        ctx.set_line_width(max(1.0, float(width or 3.0)))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()


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
                eff_sc = sc_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_color
                eff_sw = sw_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_width
                if eff_sw is not None and float(eff_sw) > 0.0 and color_alpha(eff_sc, 1.0) > 0.0:
                    ctx.set_source_rgba(*color_rgba(eff_sc, (0.1, 0.1, 0.15, 1.0)))
                    ctx.set_line_width(float(eff_sw))
                    ctx.stroke()
                else:
                    ctx.new_path()


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
        if (not for_export) and _stroke_has_wave(stroke):
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
        has_stroke = (stroke_width is not None and float(stroke_width) > 0.0 and color_alpha(stroke_color, 1.0) > 0.0)
        if fill_color is not None and draw_stroke_path(ctx, stroke):
            ctx.set_source_rgba(*color_rgba(fill_color, (0.0, 0.0, 0.0, 1.0)))
            if _stroke_needs_variable_width(stroke, visible_segs):
                ctx.fill()
                if has_stroke or _stroke_has_component_styles(stroke):
                    _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
            else:
                if has_stroke or _stroke_has_component_styles(stroke):
                    ctx.fill_preserve()
                    if _stroke_has_component_styles(stroke):
                        ctx.new_path()
                    _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
                else:
                    ctx.fill()
        else:
            _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)

        if isinstance(stroke, dict) and stroke.get("arrow_end") and has_stroke:
            _draw_arrowhead(ctx, segs, stroke_color, stroke_width)

        # Show hidden curves differently in edit curve/nodes modes for easier selection
        if show_hidden:
            _draw_hidden_segments(ctx, stroke, segs, hidden, stroke_width)

    # Draw selection overlays (nodes for single selection, combined bbox for transform)
    if edit_mode and sel_set:
        selected_in_range = [i for i in sel_set if 0 <= i < len(strokes)]
        # Highlight selected stroke/component(s) in curve edit mode
        if selection_submode == "curve":
            sel_curves = selected_curves if selected_curves else (([selected_curve] if selected_curve is not None else []))
            for scv in sel_curves:
                try:
                    si, comp_i = scv
                except Exception:
                    continue
                if si not in selected_in_range or not (0 <= si < len(strokes)):
                    continue
                segs = segs_of(strokes[si])
                ranges = _component_ranges(strokes[si])
                if not (0 <= comp_i < len(ranges)):
                    continue
                s0, s1 = ranges[comp_i]
                comp_range = range(s0, min(s1, len(segs)))
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
            obb = combined_obb(strokes, selected_in_range)
            if obb:
                corners = obb.get("corners", [])
                handles = bbox_handles(obb, mode=transform_handle_mode)
                try:
                    ctx.set_dash([6, 4])
                except Exception:
                    pass
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.5)
                if corners:
                    ctx.move_to(corners[0][0], corners[0][1])
                    for cpt in corners[1:]:
                        ctx.line_to(cpt[0], cpt[1])
                    ctx.close_path()
                    ctx.stroke()
                try:
                    ctx.set_dash([])
                except Exception:
                    pass
                # rotation stem only in legacy-style scale mode separate rot handle
                if transform_handle_mode == "scale" and "n" in handles and "rot" in handles:
                    npt = handles["n"]; rpt = handles["rot"]
                    ctx.set_source_rgb(0.1, 0.45, 0.95)
                    ctx.set_line_width(1.0)
                    ctx.move_to(npt[0], npt[1]); ctx.line_to(rpt[0], rpt[1])
                    ctx.stroke()
                for name, pt in handles.items():
                    if name == "rot" or name.startswith("rot_"):
                        ctx.set_source_rgb(1, 1, 1); ctx.arc(pt[0], pt[1], 5.0, 0, 2*math.pi); ctx.fill()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(1.5); ctx.arc(pt[0], pt[1], 5.0, 0, 2*math.pi); ctx.stroke()
                    elif name.startswith("skew_"):
                        # skew handles as diamonds
                        d = 4.5
                        ctx.move_to(pt[0], pt[1]-d); ctx.line_to(pt[0]+d, pt[1]); ctx.line_to(pt[0], pt[1]+d); ctx.line_to(pt[0]-d, pt[1]); ctx.close_path()
                        ctx.set_source_rgb(1, 1, 1); ctx.fill_preserve()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(1.5); ctx.stroke()
                    else:
                        ctx.set_source_rgb(1, 1, 1); ctx.rectangle(pt[0]-4, pt[1]-4, 8, 8); ctx.fill_preserve()
                        ctx.set_source_rgb(0.1, 0.45, 0.95); ctx.set_line_width(1.5); ctx.stroke()
                # Pivot point (rotation/scale center) - draggable
                pv = pivot_pos if pivot_pos is not None else (obb["cx"], obb["cy"])
                if pv is not None:
                    px, py = pv
                    r_out, r_in = 7.0, 2.5
                    ctx.set_source_rgba(1.0, 1.0, 1.0, 0.95)
                    ctx.arc(px, py, r_out, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(0.95, 0.45, 0.1)
                    ctx.set_line_width(1.6)
                    ctx.arc(px, py, r_out, 0, 2*math.pi); ctx.stroke()
                    ctx.move_to(px - r_out, py); ctx.line_to(px - r_in, py)
                    ctx.move_to(px + r_in, py); ctx.line_to(px + r_out, py)
                    ctx.move_to(px, py - r_out); ctx.line_to(px, py - r_in)
                    ctx.move_to(px, py + r_in); ctx.line_to(px, py + r_out)
                    ctx.stroke()
                    ctx.arc(px, py, r_in, 0, 2*math.pi); ctx.fill()
        elif selection_submode == "nodes" and len(selected_in_range) > 1:
            # Multi-selection: show combined oriented bbox (node editing requires single selection)
            obb = combined_obb(strokes, selected_in_range)
            if obb:
                corners = obb.get("corners", [])
                try:
                    ctx.set_dash([4, 4])
                except Exception:
                    pass
                ctx.set_source_rgb(0.1, 0.45, 0.95)
                ctx.set_line_width(1.2)
                if corners:
                    ctx.move_to(corners[0][0], corners[0][1])
                    for cpt in corners[1:]:
                        ctx.line_to(cpt[0], cpt[1])
                    ctx.close_path()
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

    ctx.restore()  # view transform
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


def export_scene_png(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0), size=None):
    """Export the current scene to a PNG file (viewport-sized)."""
    w, h = (int(size[0]), int(size[1])) if size else (int(cfg.CANVAS_W), int(cfg.canvas_viewport_height()))
    surf = make_cairo_surface(w, h)
    draw_scene(surf, strokes, ref_img=ref_img, view_zoom=view_zoom, view_pan=view_pan, for_export=True)
    surf.write_to_png(path)


def export_scene_svg(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0), size=None):
    """Export the current scene to an SVG file (viewport-sized)."""
    w, h = (int(size[0]), int(size[1])) if size else (int(cfg.CANVAS_W), int(cfg.canvas_viewport_height()))
    surf = cairo.SVGSurface(str(path), w, h)
    try:
        draw_scene(surf, strokes, ref_img=ref_img, view_zoom=view_zoom, view_pan=view_pan, for_export=True)
        try:
            surf.flush()
        except Exception:
            pass
    finally:
        try:
            surf.finish()
        except Exception:
            pass


def export_scene_image(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0), size=None):
    """Export the current scene to PNG or SVG based on file extension."""
    if str(path).lower().endswith(".svg"):
        export_scene_svg(path, strokes, ref_img=ref_img, view_zoom=view_zoom, view_pan=view_pan, size=size)
    else:
        export_scene_png(path, strokes, ref_img=ref_img, view_zoom=view_zoom, view_pan=view_pan, size=size)

def _pygame_image_to_cairo_surface(path):
    """Load any pygame-supported image and copy its pixels into a cairo surface.

    Returns a cairo.ImageSurface (ARGB32) or None. The pixels are copied into
    the surface's own buffer, so there is no external buffer whose lifetime we
    have to track. (pycairo surfaces are C objects and cannot hold a reference
    to a Python buffer as an attribute, which previously made every non-PNG
    load fail silently.)
    """
    try:
        img = pygame.image.load(path)
    except Exception:
        return None
    try:
        img = img.convert_alpha()
    except Exception:
        # No display / conversion unavailable: use the loaded surface as-is.
        pass
    w, h = img.get_size()
    if w <= 0 or h <= 0:
        return None
    try:
        data = pygame.image.tobytes(img, "BGRA")
    except AttributeError:  # older pygame
        data = pygame.image.tostring(img, "BGRA")
    try:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        view = surf.get_data()
        view[:len(data)] = data
        # We wrote straight into the surface's buffer, so tell cairo the pixels
        # changed. Without this it can keep painting a stale (blank) snapshot.
        try:
            surf.mark_dirty()
        except Exception:
            pass
        return surf
    except Exception:
        return None


def load_reference_image(path):
    """Load image file into a cairo ImageSurface (ARGB32) for reference drawing.

    PNG uses cairo's native loader (fast and exact). Everything else — and any
    PNG cairo cannot decode — goes through pygame, so JPG/JPEG/BMP/GIF/WEBP all
    work consistently. Returns None only if the file genuinely cannot be read.
    """
    if not path:
        return None
    surf = None
    # Prefer cairo's PNG loader when possible.
    if str(path).lower().endswith(".png"):
        try:
            surf = cairo.ImageSurface.create_from_png(path)
        except Exception:
            surf = None
    # Fall back to pygame for other formats and unreadable PNGs.
    if surf is None:
        surf = _pygame_image_to_cairo_surface(path)
        if surf is None:
            return None
    w, h = surf.get_width(), surf.get_height()
    return {"surface": surf, "w": w, "h": h, "x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 0.5, "visible": True, "path": path}
