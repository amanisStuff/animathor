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



def _stroke_has_active_thickness(stroke):

    try:

        for comp in _stroke_components(stroke):

            for sv in _get_distortion_styles(comp):

                if isinstance(sv, dict) and sv.get("type") == "thickness" and _distortion_style_active(sv):

                    return True

    except Exception:

        pass

    return False

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

        is_thickness = False

        try:

            _styles = _get_distortion_styles(comp) if '_get_distortion_styles' in dir() else (comp.get("styles") or [])

            is_thickness = any(isinstance(sv, dict) and sv.get("type") == "thickness" and _distortion_style_active(sv) for sv in _styles)

        except Exception:

            is_thickness = False

        if _component_wave_enabled(comp) and len(idxs) == (min(s1, len(segs_all)) - s0):

            poly = sample_distorted_component(stroke, ci)

            if poly and len(poly) >= 2:

                if is_thickness:

                    # Ribbon: [bottom_start..bottom_end, top_end..top_start]

                    n = len(poly) // 2

                    if n >= 2:

                        # Fill closed ribbon

                        ctx.new_path()

                        ctx.move_to(poly[0][0], poly[0][1])

                        for pt in poly[1:]:

                            ctx.line_to(pt[0], pt[1])

                        ctx.close_path()

                        eff_sc = sc_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_color

                        eff_sw = sw_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_width

                        ctx.save()

                        ctx.set_source_rgba(*color_rgba(eff_sc, DEFAULT_STROKE_RGBA))

                        ctx.fill_preserve()

                        # Stroke only top edge + caps, not the bottom baseline

                        ctx.new_path()

                        ctx.move_to(poly[n - 1][0], poly[n - 1][1])  # bottom_end -> end cap

                        for pt in poly[n:]:

                            ctx.line_to(pt[0], pt[1])  # top_end..top_start

                        ctx.line_to(poly[0][0], poly[0][1])  # start cap

                        if eff_sw is not None and float(eff_sw) > 0.0 and color_alpha(eff_sc, 1.0) > 0.0:

                            ctx.set_line_width(float(eff_sw))

                            apply_stroke_style(ctx, stroke, float(eff_sw))

                            ctx.stroke()

                        else:

                            ctx.new_path()

                        ctx.restore()

                        drew_c = True

                    else:

                        drew_c = _draw_polyline(poly)

                else:

                    drew_c = _draw_polyline(poly)

        if not drew_c:

            for i in idxs:

                p0, c1, c2, p3 = segs_all[i]

                ctx.move_to(p0[0], p0[1]); ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])

                drew_c = True

        if drew_c and not is_thickness:

            eff_sc = sc_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_color

            eff_sw = sw_i if _stroke_has_component_styles(stroke) or _component_wave_enabled(comp) else stroke_width

            if eff_sw is not None and float(eff_sw) > 0.0 and color_alpha(eff_sc, 1.0) > 0.0:

                ctx.save()

                ctx.set_source_rgba(*color_rgba(eff_sc, DEFAULT_STROKE_RGBA))

                ctx.set_line_width(float(eff_sw))

                apply_stroke_style(ctx, stroke, float(eff_sw))

                ctx.stroke()

                ctx.restore()

            else:

                ctx.new_path()

        elif drew_c and is_thickness:

            pass

def _draw_canvas_overlays(ctx, for_export, view_zoom, view_pan, guides, smart_guides, artboards, active_artboard):
    if for_export or not (getattr(cfg, "SHOW_GRID", False) or guides or smart_guides or artboards):
        return
    try:
        zoom = float(view_zoom) or 1.0
        wx0 = (0.0 - float(view_pan[0])) / zoom
        wy0 = (0.0 - float(view_pan[1])) / zoom
        wx1 = (float(cfg.CANVAS_W) - float(view_pan[0])) / zoom
        wy1 = (float(cfg.canvas_viewport_height()) - float(view_pan[1])) / zoom
        thin = 1.0 / zoom
        if getattr(cfg, "SHOW_GRID", False):
            spacing = float(getattr(cfg, "GRID_SIZE", 20.0) or 20.0)
            major_every = int(getattr(cfg, "GRID_MAJOR_EVERY", 5) or 5)
            minor, major_c = cfg.GRID_MINOR_RGB, cfg.GRID_MAJOR_RGB
            for x in grid_positions(wx0, wx1, spacing):
                is_major = (round(x / spacing) % major_every == 0)
                ctx.set_source_rgba(*(cairo_rgb(major_c if is_major else minor, 0.85)))
                ctx.set_line_width(thin)
                ctx.move_to(x, wy0); ctx.line_to(x, wy1); ctx.stroke()
            for y in grid_positions(wy0, wy1, spacing):
                is_major = (round(y / spacing) % major_every == 0)
                ctx.set_source_rgba(*(cairo_rgb(major_c if is_major else minor, 0.85)))
                ctx.set_line_width(thin)
                ctx.move_to(wx0, y); ctx.line_to(wx1, y); ctx.stroke()
        if artboards:
            for _ai, _ab in enumerate(artboards or ()):
                if not isinstance(_ab, dict):
                    continue
                try:
                    ax = float(_ab.get("x", 0.0)); ay = float(_ab.get("y", 0.0))
                    aw = float(_ab.get("w", 0.0)); ah = float(_ab.get("h", 0.0))
                except Exception:
                    continue
                if aw <= 0 or ah <= 0:
                    continue
                is_active = (_ai == active_artboard)
                ctx.save()
                try:
                    ctx.set_dash([])
                except Exception:
                    pass
                if is_active:
                    ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "ACCENT_RGB", (59, 130, 246)), 0.95)))
                    ctx.set_line_width(max(thin * 1.5, 2.0 / zoom))
                else:
                    ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "BORDER_RGB", (203, 213, 225)), 0.9)))
                    ctx.set_line_width(max(thin, 1.0 / zoom))
                ctx.rectangle(ax, ay, aw, ah)
                ctx.stroke()
                try:
                    name = str(_ab.get("name") or f"Artboard {_ai + 1}")
                    ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "MUTED_RGB", (100, 116, 139)), 0.95 if is_active else 0.75)))
                    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                    ctx.set_font_size(max(10.0 / zoom, 8.0 / zoom))
                    ctx.move_to(ax, ay - 4.0 / zoom)
                    ctx.show_text(name)
                except Exception:
                    pass
                ctx.restore()
        for g in guides or ():
            try:
                pos = float(g.get("pos", 0.0))
            except (TypeError, ValueError):
                continue
            ctx.set_source_rgba(*(cairo_rgb(cfg.GUIDE_RGB, 0.9)))
            ctx.set_line_width(thin)
            try:
                ctx.set_dash([6.0 / zoom, 4.0 / zoom])
            except Exception:
                pass
            if g.get("axis") == "x":
                ctx.move_to(pos, wy0); ctx.line_to(pos, wy1)
            else:
                ctx.move_to(wx0, pos); ctx.line_to(wx1, pos)
            ctx.stroke()
            try:
                ctx.set_dash([])
            except Exception:
                pass
        if smart_guides:
            ctx.set_source_rgba(*(cairo_rgb(getattr(cfg, "SMART_GUIDE_RGB", (236, 72, 153)), 0.95)))
            ctx.set_line_width(max(thin, 1.0 / zoom))
            try:
                ctx.set_dash([])
            except Exception:
                pass
            for sg in smart_guides:
                try:
                    if sg.get("axis") == "x":
                        pos = float(sg["pos"])
                        ctx.move_to(pos, float(sg.get("y0", wy0))); ctx.line_to(pos, float(sg.get("y1", wy1))); ctx.stroke()
                    elif sg.get("axis") == "y":
                        pos = float(sg["pos"])
                        ctx.move_to(float(sg.get("x0", wx0)), pos); ctx.line_to(float(sg.get("x1", wx1)), pos); ctx.stroke()
                except Exception:
                    continue
    except Exception:
        pass

def _draw_bezier_pen_preview(ctx, for_export, bezier_pen):
    if for_export or not (bezier_pen and isinstance(bezier_pen, dict)):
        return
    try:
        anchors = list(bezier_pen.get("anchors") or [])
        if not anchors:
            return
        preview_pt = bezier_pen.get("preview_pt")
        if len(anchors) >= 2:
            ctx.set_source_rgb(*EDITOR_SELECTION)
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.new_path()
            ctx.move_to(anchors[0]["pt"][0], anchors[0]["pt"][1])
            for i in range(len(anchors) - 1):
                a, b = anchors[i], anchors[i + 1]
                p0, p3 = a["pt"], b["pt"]
                c1 = a.get("h_out") or p0
                c2 = b.get("h_in") or p3
                ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
            ctx.stroke()
        if preview_pt is not None and not bezier_pen.get("mouse_down", False):
            last = anchors[-1]
            lp = last["pt"]
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.7)
            ctx.set_line_width(EDITOR_LINE_WIDTH)
            try:
                ctx.set_dash([6, 4])
            except Exception:
                pass
            ctx.new_path(); ctx.move_to(lp[0], lp[1]); ctx.line_to(preview_pt[0], preview_pt[1]); ctx.stroke()
            try:
                ctx.set_dash([])
            except Exception:
                pass
        ctx.set_source_rgba(*EDITOR_ACCENT, 0.7)
        ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
        for a in anchors:
            pt = a["pt"]
            for hk in ("h_in", "h_out"):
                hp = a.get(hk) or pt
                if abs(hp[0] - pt[0]) > 0.5 or abs(hp[1] - pt[1]) > 0.5:
                    ctx.new_path(); ctx.move_to(pt[0], pt[1]); ctx.line_to(hp[0], hp[1]); ctx.stroke()
        for a in anchors:
            pt = a["pt"]
            for hk in ("h_in", "h_out"):
                hp = a.get(hk) or pt
                if abs(hp[0] - pt[0]) > 0.5 or abs(hp[1] - pt[1]) > 0.5:
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(hp[0], hp[1], EDITOR_HANDLE_HALF, 0, 2 * math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(hp[0], hp[1], EDITOR_HANDLE_HALF, 0, 2 * math.pi); ctx.stroke()
        for idx, a in enumerate(anchors):
            pt = a["pt"]; s = EDITOR_HANDLE_HALF + 1
            ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0] - s, pt[1] - s, 2 * s, 2 * s); ctx.fill_preserve()
            ctx.set_source_rgb(*(EDITOR_ACCENT if idx == len(anchors) - 1 else EDITOR_SELECTION))
            ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD if idx == len(anchors) - 1 else EDITOR_LINE_WIDTH)
            ctx.stroke()
        if preview_pt is not None and not bezier_pen.get("mouse_down", False):
            px, py = preview_pt; s = EDITOR_HANDLE_HALF
            ctx.set_source_rgba(*EDITOR_HANDLE_FILL, 0.8); ctx.rectangle(px - s, py - s, 2 * s, 2 * s); ctx.fill_preserve()
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.8); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
        if len(anchors) >= 3 and preview_pt is not None and not bezier_pen.get("mouse_down", False):
            try:
                fp = anchors[0]["pt"]
                if math.hypot(preview_pt[0] - fp[0], preview_pt[1] - fp[1]) <= 10.0:
                    ctx.set_source_rgba(*EDITOR_ACCENT, 0.25); ctx.arc(fp[0], fp[1], EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD); ctx.arc(fp[0], fp[1], EDITOR_SNAP_RADIUS, 0, 2 * math.pi); ctx.stroke()
            except Exception:
                pass
    except Exception:
        pass

def _draw_gradient_edit_handles(ctx, edit_mode, gradient_edit_info):
    if not (edit_mode and gradient_edit_info and isinstance(gradient_edit_info, dict)):
        return
    try:
        gtype = gradient_edit_info.get("type")
        hs = gradient_edit_info.get("handles") or {}
        if gtype == "linear" and "p1" in hs and "p2" in hs:
            p1, p2 = hs["p1"], hs["p2"]
            ctx.set_source_rgba(*EDITOR_SELECTION, 0.95); ctx.set_line_width(EDITOR_LINE_WIDTH_BOLD)
            ctx.move_to(p1[0], p1[1]); ctx.line_to(p2[0], p2[1]); ctx.stroke()
            for name in ("p1", "p2"):
                pt = hs.get(name)
                if pt is None: continue
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
            cpt = hs.get("center")
            if cpt is not None:
                ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(cpt[0], cpt[1], EDITOR_HANDLE_HALF, 0, 2*math.pi); ctx.fill()
                ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(cpt[0], cpt[1], EDITOR_HANDLE_HALF, 0, 2*math.pi); ctx.stroke()
        elif gtype in ("radial", "conic", "spiral", "diamond", "square"):
            cpt, rx_pt, ry_pt, rot_pt = hs.get("center"), hs.get("rx"), hs.get("ry"), hs.get("rot")
            if cpt is not None:
                gcx, gcy = cpt
                rpx = float(gradient_edit_info.get("radii_px", (0.0, 0.0))[0] or 0.0)
                rpy = float(gradient_edit_info.get("radii_px", (0.0, 0.0))[1] or 0.0)
                ang = float(gradient_edit_info.get("angle", 0.0) or 0.0)
                if rpx > 0.5 and rpy > 0.5:
                    ctx.save(); ctx.translate(gcx, gcy); ctx.rotate(ang); ctx.scale(rpx, rpy); ctx.new_sub_path()
                    if gtype == "square": ctx.rectangle(-1.0, -1.0, 2.0, 2.0)
                    elif gtype == "diamond": ctx.move_to(0.0, -1.0); ctx.line_to(1.0, 0.0); ctx.line_to(0.0, 1.0); ctx.line_to(-1.0, 0.0); ctx.close_path()
                    else: ctx.arc(0.0, 0.0, 1.0, 0, 2*math.pi)
                    ctx.restore(); ctx.set_source_rgba(*EDITOR_SELECTION, 0.9); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
                    if rx_pt is not None: ctx.move_to(gcx, gcy); ctx.line_to(rx_pt[0], rx_pt[1])
                    if ry_pt is not None: ctx.move_to(gcx, gcy); ctx.line_to(ry_pt[0], ry_pt[1])
                    ctx.set_source_rgba(*EDITOR_SELECTION, 0.7); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE); ctx.stroke()
                if rot_pt is not None and rx_pt is not None:
                    ctx.set_source_rgba(*EDITOR_ROTATION, 0.8); ctx.set_line_width(EDITOR_LINE_WIDTH_SUBTLE)
                    ctx.move_to(rx_pt[0], rx_pt[1]); ctx.line_to(rot_pt[0], rot_pt[1]); ctx.stroke()
                    ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(rot_pt[0], rot_pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                    ctx.set_source_rgb(*EDITOR_ROTATION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(rot_pt[0], rot_pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
                for name, pt in hs.items():
                    if pt is None: continue
                    if name == "center":
                        ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.fill()
                        ctx.set_source_rgb(*EDITOR_ACCENT); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.arc(pt[0], pt[1], EDITOR_HANDLE_RADIUS, 0, 2*math.pi); ctx.stroke()
                    elif name in ("rx", "ry", "edge"):
                        ctx.set_source_rgb(*EDITOR_HANDLE_FILL); ctx.rectangle(pt[0]-EDITOR_HANDLE_HALF, pt[1]-EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF, 2*EDITOR_HANDLE_HALF); ctx.fill_preserve()
                        ctx.set_source_rgb(*EDITOR_SELECTION); ctx.set_line_width(EDITOR_LINE_WIDTH); ctx.stroke()
    except Exception:
        pass




















from views.canvas_extra2 import *

from views.canvas_extra3 import *
