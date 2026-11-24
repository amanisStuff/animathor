"""Controller: MOUSEBUTTONDOWN button 1 handler (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *
from controllers.mouse_button_down_panel import _handle_panel_click
from controllers.mouse_button_down_canvas import _handle_canvas_click









def _handle_pre_menu(ctx, event):
    # Library workspace is view/browse-only: no drawing input.
    if ctx.workspace == "library":
        ctx.drawing = False; ctx.current_points = []
    if ctx.export_dialog_open:
        _edr = ctx.state.get("export_dialog_rects", {}) or {}
        _card = _edr.get("card", pygame.Rect(0, 0, 0, 0))
        if isinstance(_card, pygame.Rect) and _card.collidepoint(event.pos):
            _hit = ctx.next((ctx.k for ctx.k, ctx.r in _edr.items()
                         if ctx.k != "card" and isinstance(ctx.r, pygame.Rect) and ctx.r.collidepoint(event.pos)), None)
            if _hit in ("cancel", "close"):
                ctx.export_dialog_open = False
            elif _hit == "export":
                ctx.export_dialog_open = False
                try:
                    ctx.path = pick_export_image_path(ctx.export_dialog_format)
                    if ctx.path:
                        _exp_ab = ctx.artboards[ctx.active_artboard] if (0 <= ctx.active_artboard < len(ctx.artboards)) else None
                        export_scene_image(ctx.path, ctx.strokes, ref_img=ctx.reference_image,
                                           view_zoom=getattr(cfg, "VIEW_ZOOM", 1.0),
                                           view_pan=(getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0)),
                                           size=(cfg.CANVAS_W, cfg.canvas_viewport_height()),
                                           scale=float(ctx.export_scale), dpi=int(ctx.export_dpi),
                                           artboard=_exp_ab)
                except Exception:
                    pass
            elif _hit in ("format", "format_prev", "format_next"):
                _fmts = ["png", "svg", "pdf", "eps", "jpg", "webp"]
                try:
                    _fi = _fmts.index(str(ctx.export_dialog_format))
                except ValueError:
                    _fi = 0
                _fi = (_fi + (-1 if _hit == "format_prev" else 1)) % len(_fmts)
                ctx.export_dialog_format = _fmts[_fi]
            elif _hit in ("scale", "scale_prev", "scale_next"):
                _scales = [1.0, 2.0, 3.0, 4.0]
                try:
                    ctx._si = _scales.index(float(ctx.export_scale))
                except ValueError:
                    ctx._si = 0
                ctx._si = (ctx._si + (-1 if _hit == "scale_prev" else 1)) % len(_scales)
                ctx.export_scale = _scales[ctx._si]
            elif _hit in ("dpi", "dpi_prev", "dpi_next"):
                _dpis = [72, 96, 150, 300, 600]
                try:
                    _di = _dpis.index(int(ctx.export_dpi))
                except ValueError:
                    _di = 3
                _di = (_di + (-1 if _hit == "dpi_prev" else 1)) % len(_dpis)
                ctx.export_dpi = _dpis[_di]
        else:
            ctx.export_dialog_open = False
        ctx.menu_open = None
        return 'continue'
    if ctx.help_open:
        ctx.help_open = False
        ctx.menu_open = None
        return 'continue'
    ctx.color_target = ctx.state.get("color_target", ctx.color_target)
    # Rulers & guides: drag from a ruler to create a guide, or grab
    # an existing guide to move it. Dropping on a ruler removes it.
    if getattr(cfg, "SHOW_RULERS", False):
        ctx._rs = int(ctx.RULER_SIZE)
        _top_r = pygame.Rect(cfg.CANVAS_X, ctx.TOP_BAR_H, cfg.CANVAS_W, ctx._rs)
        _left_r = pygame.Rect(cfg.CANVAS_X, ctx.TOP_BAR_H, ctx._rs, cfg.canvas_viewport_height())
        if _top_r.collidepoint(event.pos):
            ctx.guides = add_guide(ctx.guides, "x", ctx.to_canvas(event.pos)[0])
            ctx.guide_drag = {"axis": "x", "index": len(ctx.guides) - 1}
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None:
                from controllers.drag.guide_session import GuideDragSession
                dm.begin(GuideDragSession(), ctx, event)
            return 'continue'
        if _left_r.collidepoint(event.pos):
            ctx.guides = add_guide(ctx.guides, "y", ctx.to_canvas(event.pos)[1])
            ctx.guide_drag = {"axis": "y", "index": len(ctx.guides) - 1}
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None:
                from controllers.drag.guide_session import GuideDragSession
                dm.begin(GuideDragSession(), ctx, event)
            return 'continue'
        if ctx.in_canvas(event.pos):
            _gh = hit_guide(ctx.to_canvas(event.pos), ctx.guides,
                            5.0 / (float(getattr(cfg, "VIEW_ZOOM", 1.0)) or 1.0))
            if _gh is not None:
                ctx.guide_drag = {"axis": ctx.guides[_gh]["axis"], "index": _gh}
                dm = getattr(ctx, 'drag_manager', None)
                if dm is not None:
                    from controllers.drag.guide_session import GuideDragSession
                    dm.begin(GuideDragSession(), ctx, event)
                return 'continue'
    # space+LMB -> pan
    if ctx.space_panning and ctx.in_canvas(event.pos):
        ctx.pan_drag = {"start_mouse": event.pos, "start_pan": (getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0))}
        dm = getattr(ctx, 'drag_manager', None)
        if dm is not None:
            from controllers.drag.pan_session import PanDragSession
            dm.begin(PanDragSession(), ctx, event)
        return 'continue'
    # Collapse/expand the right sidebar.
    if ctx.state.get("panel_toggle_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
        ctx.panel_collapsed = not ctx.panel_collapsed
        ctx.state["panel_collapsed"] = ctx.panel_collapsed
        ctx.relayout()
        return 'continue'
    if ctx.wave_formula_focus and not ctx.state.get("wave_formula_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
    # Top menu bar interactions
    return None

def _handle_menus(ctx, event):
    menu_handled = False
    if event.pos[1] < ctx.TOP_BAR_H:
        ctx.shape_menu_key = None
        # Workspace switcher (Draw <-> Library) lives in the top bar.
        if (isinstance(ctx.state.get("workspace_rect"), pygame.Rect)
                and ctx.state["workspace_rect"].collidepoint(event.pos)):
            ctx.workspace = "library" if ctx.workspace == "draw" else "draw"
            ctx.state["workspace"] = ctx.workspace
            ctx.menu_open = None
            menu_handled = True
        hit = ctx.next((ctx.k for ctx.k, ctx.r in ctx.menu_bar_rects.items()
                    if ctx.r.collidepoint(event.pos)), None)
        ctx.menu_open = None if hit is None or ctx.menu_open == hit else hit
        ctx.help_open = False
        menu_handled = True
    elif ctx.menu_open is not None:
        hit = ctx.next((ctx.k for ctx.k, ctx.r in ctx.menu_item_rects.items()
                    if ctx.r.collidepoint(event.pos)), None)
        if hit is not None:
            ctx.run_menu_action(hit)
        # A click outside the dropdown only dismisses it.
        ctx.menu_open = None
        menu_handled = True
    if ctx.marker_dropdown is not None:
        _mk_items = ctx.state.get("marker_dropdown_item_rects", {}) or {}
        _mk_hit = ctx.next((ctx.k for ctx.k, ctx.r in _mk_items.items()
                        if isinstance(ctx.r, pygame.Rect) and ctx.r.collidepoint(event.pos)), None)
        _mk_anchor = ctx.state.get("marker_start_rect" if ctx.marker_dropdown == "start" else "marker_end_rect", pygame.Rect(0, 0, 0, 0))
        if _mk_hit is not None:
            ctx.push_undo()
            for ctx.si in sorted(ctx.selected_strokes):
                if 0 <= ctx.si < len(ctx.strokes) and isinstance(ctx.strokes[ctx.si], dict):
                    ctx.strokes[ctx.si] = set_marker(ctx.strokes[ctx.si], ctx.marker_dropdown, _mk_hit)
            ctx.marker_dropdown = None
            menu_handled = True
        elif ctx.state.get("marker_dropdown_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
            menu_handled = True
        elif isinstance(_mk_anchor, pygame.Rect) and _mk_anchor.collidepoint(event.pos):
            # Let the marker button handler toggle it.
            pass
        else:
            ctx.marker_dropdown = None
        ctx.state["marker_dropdown"] = ctx.marker_dropdown
    if ctx.shape_menu_key is not None:
        _menu_items = ctx.state.get("shape_menu_item_rects", {})
        _menu_hit = ctx.next((ctx.k for ctx.k, ctx.r in _menu_items.items() if ctx.r.collidepoint(event.pos)), None)
        if _menu_hit is not None:
            if _menu_hit == "snap":
                ctx.snap_enabled = not ctx.snap_enabled
            elif _menu_hit.startswith("bucket_color_"):
                try:
                    _bi = int(_menu_hit.rsplit("_", 1)[1])
                    if 0 <= _bi < len(ctx.BUCKET_SWATCHES):
                        ctx.set_bucket_color(ctx.BUCKET_SWATCHES[_bi])
                except ValueError:
                    pass
                # Keep the popup open so several colors can be tried.
            elif _menu_hit == "boost":
                ctx.boost_points = not ctx.boost_points
                ctx.slider.max_v = ctx.BOOST_MAX_POINTS if ctx.boost_points else ctx.NORMAL_MAX_POINTS
                if not ctx.boost_points:
                    ctx.max_points_per_curve = min(ctx.max_points_per_curve, ctx.NORMAL_MAX_POINTS)
                ctx.slider.value = ctx.max_points_per_curve
            elif _menu_hit.startswith("choice_prev:") or _menu_hit.startswith("choice_next:"):
                _cdir = -1 if _menu_hit.startswith("choice_prev:") else 1
                _ckey = _menu_hit.split(":", 1)[1]
                _choices = {
                    "trace_algorithm": [ctx.k for ctx.k, _ in TRACE_ALGORITHMS],
                    "triangle_variant": [ctx.k for ctx.k, _ in TRIANGLE_VARIANTS],
                    "rect_variant": ["rect", "square"],
                    "ellipse_variant": ["ellipse", "circle"],
                }
                _opts = _choices.get(_ckey, [])
                if _opts:
                    if _ckey == "trace_algorithm":
                        _cur = ctx.trace_algorithm if ctx.trace_algorithm in _opts else _opts[0]
                    elif _ckey == "triangle_variant":
                        _cur = ctx.triangle_variant if ctx.triangle_variant in _opts else _opts[0]
                    elif _ckey == "rect_variant":
                        _cur = ctx.rect_variant if ctx.rect_variant in _opts else _opts[0]
                    else:
                        _cur = ctx.ellipse_variant if ctx.ellipse_variant in _opts else _opts[0]
                    _ni = (_opts.index(_cur) + _cdir) % len(_opts)
                    _nv = _opts[_ni]
                    if _ckey == "trace_algorithm":
                        ctx.trace_algorithm = _nv
                    elif _ckey == "triangle_variant":
                        ctx.triangle_variant = _nv
                        if ctx.bezier_pen is not None:
                            ctx._bezier_pen_commit_or_cancel()
                        ctx.draw_shape = "triangle"
                        ctx.draw_tool = "pen"
                        ctx.tool_mode = "draw"
                    elif _ckey == "rect_variant":
                        ctx.rect_variant = _nv
                        if ctx.bezier_pen is not None:
                            ctx._bezier_pen_commit_or_cancel()
                        ctx.draw_shape = _nv
                        ctx.draw_tool = "pen"
                        ctx.tool_mode = "draw"
                    elif _ckey == "ellipse_variant":
                        ctx.ellipse_variant = _nv
                        if ctx.bezier_pen is not None:
                            ctx._bezier_pen_commit_or_cancel()
                        ctx.draw_shape = _nv
                        ctx.draw_tool = "pen"
                        ctx.tool_mode = "draw"
            elif _menu_hit in ("fit", "catmull-rom", "single"):
                ctx.trace_algorithm = _menu_hit
                ctx.shape_menu_key = None
            elif _menu_hit in ("isosceles", "right", "equilateral"):
                ctx.triangle_variant = _menu_hit
                # Picking a type implies the triangle tool.
                if ctx.bezier_pen is not None:
                    ctx._bezier_pen_commit_or_cancel()
                ctx.draw_shape = "triangle"
                ctx.tool_mode = "draw"
                ctx.shape_menu_key = None
            elif _menu_hit in ("rect", "square"):
                ctx.rect_variant = _menu_hit
                if ctx.bezier_pen is not None:
                    ctx._bezier_pen_commit_or_cancel()
                ctx.draw_shape = _menu_hit
                ctx.draw_tool = "pen"
                ctx.tool_mode = "draw"
                ctx.shape_menu_key = None
            elif _menu_hit in ("ellipse", "circle"):
                ctx.ellipse_variant = _menu_hit
                if ctx.bezier_pen is not None:
                    ctx._bezier_pen_commit_or_cancel()
                ctx.draw_shape = _menu_hit
                ctx.draw_tool = "pen"
                ctx.tool_mode = "draw"
                ctx.shape_menu_key = None
            elif _menu_hit == "line_constrain":
                ctx.line_constrain = not ctx.line_constrain
            elif _menu_hit == "line_arrow":
                ctx.line_arrow = not ctx.line_arrow
            elif _menu_hit == "points_minus":
                ctx.max_points_per_curve = max(2, ctx.max_points_per_curve - 1)
                ctx.slider.value = ctx.max_points_per_curve
            elif _menu_hit == "points_plus":
                ctx.limit = ctx.BOOST_MAX_POINTS if ctx.boost_points else ctx.NORMAL_MAX_POINTS
                ctx.max_points_per_curve = min(ctx.limit, ctx.max_points_per_curve + 1)
                ctx.slider.value = ctx.max_points_per_curve
            elif _menu_hit == "corner_minus":
                ctx.corner_radius = max(0, ctx.corner_radius - 5)
            elif _menu_hit == "corner_plus":
                ctx.corner_radius = min(50, ctx.corner_radius + 5)
            elif _menu_hit == "segments_minus":
                ctx.ellipse_segments = max(4, ctx.ellipse_segments - 2)
            elif _menu_hit == "segments_plus":
                ctx.ellipse_segments = min(16, ctx.ellipse_segments + 2)
            elif _menu_hit == "sides_minus":
                ctx.polygon_sides = max(3, ctx.polygon_sides - 1)
            elif _menu_hit == "sides_plus":
                ctx.polygon_sides = min(24, ctx.polygon_sides + 1)
            elif _menu_hit == "spokes_minus":
                ctx.star_points = max(3, ctx.star_points - 1)
            elif _menu_hit == "spokes_plus":
                ctx.star_points = min(24, ctx.star_points + 1)
            elif _menu_hit == "inner_minus":
                ctx.star_inner_ratio = max(0.1, round(ctx.star_inner_ratio - 0.05, 2))
            elif _menu_hit == "inner_plus":
                ctx.star_inner_ratio = min(0.9, round(ctx.star_inner_ratio + 0.05, 2))
            elif _menu_hit == "gap_minus":
                ctx.cut_gap = max(0, ctx.cut_gap - 2)
                ctx.cut_gap_slider.value = ctx.cut_gap
                ctx.state["cut_gap"] = ctx.cut_gap
            elif _menu_hit == "gap_plus":
                ctx.cut_gap = min(20, ctx.cut_gap + 2)
                ctx.cut_gap_slider.value = ctx.cut_gap
                ctx.state["cut_gap"] = ctx.cut_gap
            menu_handled = True
        elif ctx.state.get("shape_menu_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
            menu_handled = True
        else:
            ctx.shape_menu_key = None
    ctx.state["shape_menu_key"] = ctx.shape_menu_key
    ctx.state["shape_menu_anchor"] = ctx.shape_menu_anchor
    if menu_handled:
        return 'continue'
    return None

def _handle_toolbar(ctx, event):
    if ctx.btn_undo.hit(event.pos):
        if ctx.do_undo():
            ctx.selected_strokes = {ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes)}
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
    elif ctx.btn_redo.hit(event.pos):
        if ctx.do_redo():
            ctx.selected_strokes = {ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes)}
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
    elif ctx.btn_draw.hit(event.pos):
        ctx.tool_mode = "draw"; ctx.draw_tool = "pen"; ctx.drawing = False; ctx.current_points = []; ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None
    elif ctx.btn_select.hit(event.pos):
        ctx._bezier_pen_commit_or_cancel()
        ctx.tool_mode = "selection"; ctx.drawing = False; ctx.current_points = []; ctx.selected_point = None; ctx.drag_last = None; ctx.transform_drag = None; ctx.selection_submode = "transform"
        ctx.curve_cut_mode = False
    elif any(ctx.r.collidepoint(event.pos) for ctx.r in ctx.state.get("draw_shape_rects", {}).values()):
        _hit_key = ctx.next((ctx.k for ctx.k, ctx.r in ctx.state.get("draw_shape_rects", {}).items() if ctx.r.collidepoint(event.pos)), None)
        if _hit_key is not None:
            _mirror_align = {"mirror_h", "mirror_v", "align_left", "align_hcenter", "align_right", "align_top", "align_vmiddle", "align_bottom"}
            ctx._draw_keys = {ctx.k for ctx.k, _ in ctx.DRAW_SHAPES} | {ctx.k for ctx.k, _ in ctx.BOTTOM_TOOLS}
            if ctx.tool_mode == "selection" and ctx.selection_submode == "transform" and _hit_key in _mirror_align and ctx.selected_strokes:
                ctx.sel = sorted(ctx.i for ctx.i in ctx.selected_strokes if 0 <= ctx.i < len(ctx.strokes))
                if ctx.sel:
                    obb = ctx.combined_obb(ctx.strokes, ctx.sel)
                    ctx.bb = ctx.combined_bbox(ctx.strokes, ctx.sel)
                    if obb and ctx.bb:
                        if ctx.pivot_pos is not None:
                            ctx.cx, ctx.cy = ctx.pivot_pos
                        else:
                            ctx.cx, ctx.cy = (ctx.bb[0] + ctx.bb[2]) / 2.0, (ctx.bb[1] + ctx.bb[3]) / 2.0
                        ctx.push_undo()
                        if _hit_key == "mirror_h":
                            for ctx.si in ctx.sel:
                                ctx.strokes[ctx.si] = mirror_stroke(ctx.strokes[ctx.si], ctx.cx, ctx.cy, "h")
                        elif _hit_key == "mirror_v":
                            for ctx.si in ctx.sel:
                                ctx.strokes[ctx.si] = mirror_stroke(ctx.strokes[ctx.si], ctx.cx, ctx.cy, "v")
                        else:
                            ctx.tx1, ctx.ty1, tx2, ty2 = ctx.bb
                            ctx.tcx, ctx.tcy = (ctx.tx1 + tx2) / 2.0, (ctx.ty1 + ty2) / 2.0
                            for ctx.si in ctx.sel:
                                sbb = ctx.stroke_bbox(ctx.strokes[ctx.si])
                                if not sbb:
                                    continue
                                ctx.sx1, ctx.sy1, sx2, sy2 = sbb
                                ctx.scx, ctx.scy = (ctx.sx1 + sx2) / 2.0, (ctx.sy1 + sy2) / 2.0
                                ctx.dx = ctx.dy = 0.0
                                if _hit_key == "align_left":
                                    ctx.dx = ctx.tx1 - ctx.sx1
                                elif _hit_key == "align_hcenter":
                                    ctx.dx = ctx.tcx - ctx.scx
                                elif _hit_key == "align_right":
                                    ctx.dx = tx2 - sx2
                                elif _hit_key == "align_top":
                                    ctx.dy = ctx.ty1 - ctx.sy1
                                elif _hit_key == "align_vmiddle":
                                    ctx.dy = ctx.tcy - ctx.scy
                                elif _hit_key == "align_bottom":
                                    ctx.dy = ty2 - sy2
                                if ctx.dx != 0.0 or ctx.dy != 0.0:
                                    ctx.strokes[ctx.si] = ctx.translate_stroke(ctx.strokes[ctx.si], ctx.dx, ctx.dy)
                ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None; ctx.pending_transform_toggle = None
            elif ctx.tool_mode == "draw" or _hit_key in ctx._draw_keys:
                # Bottom toolbar: pick a shape or a drawing tool.
                _new_tool = ctx.draw_tool
                _new_shape = ctx.draw_shape
                if _hit_key in ("eraser", "bucket", "cutter"):
                    _new_tool = _hit_key
                elif _hit_key not in _mirror_align:
                    if _hit_key == "rect":
                        _new_shape = ctx.rect_variant
                    elif _hit_key == "ellipse":
                        _new_shape = ctx.ellipse_variant
                    else:
                        _new_shape = _hit_key
                    _new_tool = "pen"
                # Commit active Bezier path when leaving Bezier pen context.
                if ctx.bezier_pen is not None and not (_new_tool == "pen" and _new_shape == "pen"):
                    ctx._bezier_pen_commit_or_cancel()
                ctx.draw_tool = _new_tool
                ctx.draw_shape = _new_shape
                ctx.tool_mode = "draw"
                ctx.drawing = False
                ctx.current_points = []
                ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None
            # else: unhandled bottom-bar action for this view; ignore

    return None

def handle_mousebuttondown1(ctx, event):
    r = _handle_pre_menu(ctx, event)
    if r == 'continue': return 'continue'
    r = _handle_menus(ctx, event)
    if r == 'continue': return 'continue'
    r = _handle_toolbar(ctx, event)
    if r == 'continue': return 'continue'
    if event.pos[0] >= cfg.PANEL_X:
        _r = _handle_panel_click(ctx, event)
        if _r == 'continue': return 'continue'
    elif ctx.in_canvas(event.pos):
        _r = _handle_canvas_click(ctx, event)
        if _r == 'continue': return 'continue'
    return None
