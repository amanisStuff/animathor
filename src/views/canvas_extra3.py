"""View: cairo canvas rendering and reference image handling."""

import math
import os

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




def _draw_selection_overlays(ctx, strokes, sel_set, edit_mode, selection_submode, selected_curve, selected_curves, transform_handle_mode, pivot_pos):
    if not (edit_mode and sel_set):
        return
    selected_in_range = [i for i in sel_set if 0 <= i < len(strokes)]
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
            dsegs = component_display_segs(strokes[si], comp_i) if 'component_display_segs' in globals() else None
            draw_segs = list(dsegs) if dsegs is not None and len(dsegs) == (min(s1, len(segs)) - s0) else list(segs[s0:min(s1, len(segs))])
            for p0, c1, c2, p3 in draw_segs:
                ctx.new_path(); ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                ctx.set_source_rgba(*EDITOR_ACCENT, 0.9)
                w = strokes[si].get("stroke_width", 3.0) if isinstance(strokes[si], dict) else 3.0
                ctx.set_line_width(max(4.0, w + 2.0)); ctx.stroke()
    if selection_submode == "nodes" and len(selected_in_range) == 1:
        idx = selected_in_range[0]
        segs = stroke_display_segs(strokes[idx]) if 'stroke_display_segs' in globals() else segs_of(strokes[idx])
        ctx.set_source_rgba(*EDITOR_GUIDE, 0.8); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
        for si, (p0, c1, c2, p3) in enumerate(segs):
            ctx.move_to(p0[0], p0[1]); ctx.line_to(c1[0], c1[1]); ctx.move_to(p3[0], p3[1]); ctx.line_to(c2[0], c2[1])
        ctx.stroke()
        for si, (p0, c1, c2, p3) in enumerate(segs):
            hr, hhalf = EDITOR_HANDLE_RADIUS, EDITOR_HANDLE_HALF
            if si == 0:
                for pt in (p0,):
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.stroke()
            for pt in (p3,):
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(pt[0], pt[1], hr, 0, 2*math.pi); ctx.stroke()
            for pt in (c1, c2):
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0]-hhalf, pt[1]-hhalf, 2*hhalf, 2*hhalf); ctx.fill_preserve()
                ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
    elif selection_submode == "transform":
        obb = combined_obb(strokes, selected_in_range)
        if obb:
            corners = obb.get("corners", [])
            handles = bbox_handles(obb, mode=transform_handle_mode)
            try: ctx.set_dash([6, 4])
            except Exception: pass
            ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH)
            if corners:
                ctx.move_to(corners[0][0], corners[0][1])
                for cpt in corners[1:]: ctx.line_to(cpt[0], cpt[1])
                ctx.close_path(); ctx.stroke()
            try: ctx.set_dash([])
            except Exception: pass
            if transform_handle_mode == "scale" and "n" in handles and "rot" in handles:
                npt, rpt = handles["n"], handles["rot"]
                ctx.set_source_rgb(*EDITOR_ROTATION); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
                ctx.move_to(npt[0], npt[1]); ctx.line_to(rpt[0], rpt[1]); ctx.stroke()
            for name, pt in handles.items():
                if name == "rot" or name.startswith("rot_"):
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ROTATION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
                elif name.startswith("skew_"):
                    d = EDITOR_SKEW_RADIUS
                    ctx.move_to(pt[0], pt[1]-d); ctx.line_to(pt[0]+d, pt[1]); ctx.line_to(pt[0], pt[1]+d); ctx.line_to(pt[0]-d, pt[1]); ctx.close_path()
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.fill_preserve()
                    ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
                else:
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0]-EDITOR_HANDLE_HALF, pt[1]-EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF); ctx.fill_preserve()
                    ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
            pv = pivot_pos if pivot_pos is not None else (obb["cx"], obb["cy"])
            if pv is not None:
                px, py = pv; r_out, r_in = EDITOR_PIVOT_RADIUS, EDITOR_PIVOT_INNER_RADIUS
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(px, py, r_out, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(px, py, r_out, 0, 2*math.pi); ctx.stroke()
                ctx.move_to(px-r_out, py); ctx.line_to(px-r_in, py); ctx.move_to(px+r_in, py); ctx.line_to(px+r_out, py)
                ctx.move_to(px, py-r_out); ctx.line_to(px, py-r_in); ctx.move_to(px, py+r_in); ctx.line_to(px, py+r_out); ctx.stroke()
                ctx.arc(px, py, r_in, 0, 2*math.pi); ctx.fill()
    elif selection_submode == "nodes" and len(selected_in_range) > 1:
        obb = combined_obb(strokes, selected_in_range)
        if obb:
            corners = obb.get("corners", [])
            try: ctx.set_dash([4, 4])
            except Exception: pass
            ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
            if corners:
                ctx.move_to(corners[0][0], corners[0][1])
                for cpt in corners[1:]: ctx.line_to(cpt[0], cpt[1])
                ctx.close_path(); ctx.stroke()
            try: ctx.set_dash([])
            except Exception: pass

def draw_scene(cairo_surface, strokes, active_stroke=None, snap_point=None, selected_index=None, selected_indices=None, edit_mode=False, selection_submode="transform", selected_curve=None, selected_curves=None, snap_kind="connect", redrawing_curve=None, ref_img=None, view_zoom=None, view_pan=None, pivot_pos=None, for_export=False, transform_handle_mode="scale", gradient_edit_info=None, export_scale=1.0, guides=None, smart_guides=None, bezier_pen=None, artboards=None, active_artboard=-1):

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
    if export_scale and float(export_scale) != 1.0:
        ctx.scale(float(export_scale), float(export_scale))

    # Grid + ruler guides + artboards overlay (view-only; never part of an export).
    _draw_canvas_overlays(ctx, for_export, view_zoom, view_pan, guides, smart_guides, artboards, active_artboard)

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


    for idx, stroke in enumerate(strokes):
        # Hidden objects (organization/layers) are excluded from all rendering.
        if isinstance(stroke, dict) and stroke.get("hidden", False):
            continue
        segs = segs_of(stroke)
        if not segs:
            continue
        stroke_color = stroke.get("stroke_color", (0.1, 0.1, 0.15)) if isinstance(stroke, dict) else (0.1, 0.1, 0.15)
        stroke_width = stroke.get("stroke_width", 3.0) if isinstance(stroke, dict) else 3.0
        fill_color = stroke.get("fill_color") if isinstance(stroke, dict) else None
        fill_gradient = stroke.get("fill_gradient") if isinstance(stroke, dict) else None
        fill_pattern = stroke.get("fill_pattern") if isinstance(stroke, dict) else None
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
                # Thickness replaces the curve with a filled ribbon; don't draw original-path guide.
                try:
                    _is_thick_guide = any(isinstance(sv, dict) and sv.get("type") == "thickness" and _distortion_style_active(sv) for sv in _get_distortion_styles(comp))
                except Exception:
                    _is_thick_guide = False
                if _is_thick_guide:
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
                    ctx.set_source_rgba(*EDITOR_SELECTION, 0.35)
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
                    ctx.set_source_rgba(*EDITOR_SELECTION, 0.35)
                    ctx.set_line_width(stroke_width + 4.0)
                    ctx.stroke()
                _draw_stroke_segments(ctx, stroke, normal_segs_set, stroke_color, stroke_width)

            # draw redrawn component as bright yellow low-opacity template
            if in_redraw:
                ctx.new_path()
                for i in sorted(in_redraw):
                    p0, c1, c2, p3 = segs[i]
                    ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
                ctx.set_source_rgba(*EDITOR_TEMPLATE, 0.35)
                ctx.set_line_width(max(stroke_width, 2.0))
                ctx.stroke()
            # hidden segments styled (except those being redrawn template)
            if show_hidden:
                _draw_hidden_segments(ctx, stroke, segs, hidden - in_redraw, stroke_width)
            continue

        # Selection highlight behind the stroke so the actual stroke color stays visible
        if is_selected_stroke and (not _stroke_has_active_thickness(stroke)) and draw_stroke_path(ctx, stroke):
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.35)
            ctx.set_line_width(stroke_width + 4.0)
            ctx.stroke()

        visible_segs = [i for i in range(len(segs)) if i not in hidden]
        has_stroke = (stroke_width is not None and float(stroke_width) > 0.0 and color_alpha(stroke_color, 1.0) > 0.0)
        fill_spec = fill_pattern if fill_pattern is not None else (fill_gradient if fill_gradient is not None else fill_color)

        # Appearance: object opacity + blend mode are composited as a single
        # unit via a temporary group; drop shadows are painted behind the art.
        _app = get_appearance(stroke) if isinstance(stroke, dict) else dict(DEFAULT_APPEARANCE)
        _grouped = (_app["opacity"] < 1.0 or _app["blend_mode"] != "normal")
        if _app["shadow"] is not None:
            draw_drop_shadow(ctx, stroke, _app["shadow"], stroke_color,
                             stroke_width, fill_spec)
        if _grouped:
            ctx.save()
            ctx.push_group()

        if _stroke_has_active_thickness(stroke):
            # Thickness draws its own filled ribbon; avoid original-path fill/stroke artifacts.
            _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
        elif fill_spec is not None and draw_stroke_path(ctx, stroke):
            if not _apply_fill_source(ctx, stroke, fill_spec):
                fill_spec = None
            if fill_spec is not None:
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
                ctx.new_path()
                _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)
        else:
            _draw_stroke_segments(ctx, stroke, visible_segs, stroke_color, stroke_width)

        if isinstance(stroke, dict) and has_stroke:
            _draw_markers(ctx, stroke, stroke_color, stroke_width)

        if _grouped:
            # Composite the isolated art with the object's blend mode and
            # opacity as one unit (so overlapping fill+stroke don't double-blend).
            _pat = ctx.pop_group()
            ctx.set_operator(blend_operator(_app["blend_mode"]))
            ctx.set_source(_pat)
            ctx.paint_with_alpha(_app["opacity"])
            ctx.restore()

        # Show hidden curves differently in edit curve/nodes modes for easier selection
        if show_hidden:
            _draw_hidden_segments(ctx, stroke, segs, hidden, stroke_width)

    # Live drawing preview: in-progress Bezier pen path or freehand stroke.
    if not for_export and redrawing_curve is None:
        try:
            if bezier_pen is not None and isinstance(bezier_pen, dict) and (bezier_pen.get("anchors") or bezier_pen.get("dragging") or bezier_pen.get("preview_pt") is not None):
                _draw_bezier_pen_preview(ctx, for_export, bezier_pen)
            elif active_stroke and not edit_mode:
                _prev_pts = [tuple(p) for p in (active_stroke or [])]
                if len(_prev_pts) >= 2:
                    ctx.set_source_rgb(0.1, 0.1, 0.15)
                    ctx.set_line_width(3.0)
                    ctx.new_path()
                    ctx.move_to(_prev_pts[0][0], _prev_pts[0][1])
                    for _pt in _prev_pts[1:]:
                        ctx.line_to(_pt[0], _pt[1])
                    ctx.stroke()
        except Exception:
            pass

    _draw_selection_overlays(ctx, strokes, sel_set, edit_mode, selection_submode, selected_curve, selected_curves, transform_handle_mode, pivot_pos)

    _draw_gradient_edit_handles(ctx, edit_mode, gradient_edit_info)

    if snap_point is not None:
        x, y = snap_point
        if snap_kind == "assist":
            r = 10.0
            ctx.new_path()
            ctx.move_to(x, y - r); ctx.line_to(x + r, y); ctx.line_to(x, y + r); ctx.line_to(x - r, y); ctx.close_path()
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.22)
            ctx.fill_preserve()
            ctx.set_source_rgb(*EDITOR_SELECTION)
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.stroke()
            ctx.new_path()
            ctx.move_to(x, y - EDITOR_SNAP_INNER); ctx.line_to(x + EDITOR_SNAP_INNER, y); ctx.line_to(x, y + EDITOR_SNAP_INNER); ctx.line_to(x - EDITOR_SNAP_INNER, y); ctx.close_path()
            ctx.fill()
        else:
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.25)
            ctx.arc(x, y, EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.fill()
            ctx.set_source_rgb(*EDITOR_SELECTION)
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.arc(x, y, EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.stroke()
            ctx.arc(x, y, EDITOR_SNAP_INNER, 0, 2 * math.pi); ctx.fill()

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

def export_format_for(path):
    """Return the export format name for ``path``, or ``None`` if unknown."""
    try:
        from views.canvas import EXPORT_FORMATS as _fmts
    except Exception:
        _fmts = EXPORT_FORMATS
    if isinstance(_fmts, dict):
        return _fmts.get(os.path.splitext(str(path))[1].lower())
    # fallback for tuple/list form
    ext = os.path.splitext(str(path))[1].lower().lstrip('.')
    return ext.upper() if ext in [str(x).lower() for x in _fmts] else None

def normalize_export_scale(scale):
    """Clamp an export scale factor to a sane range (1x default)."""
    try:
        value = float(scale)
    except (TypeError, ValueError):
        return 1.0
    if value <= 0.0 or not math.isfinite(value):
        return 1.0
    return max(0.1, min(10.0, value))

def _export_base_size(size):
    if size:
        return max(1, int(size[0])), max(1, int(size[1]))
    return max(1, int(cfg.CANVAS_W)), max(1, int(cfg.canvas_viewport_height()))

