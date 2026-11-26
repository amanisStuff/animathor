"""Pre-menu click handling (dialogs, export, workspace)."""
import copy, math, pygame
import config as cfg
from models import add_guide, hit_guide, mirror_stroke, set_marker  # noqa: F401
from views import TRACE_ALGORITHMS, TRIANGLE_VARIANTS, export_scene_image, pick_export_image_path  # noqa: F401
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
            _hit = next((ctx.k for ctx.k, ctx.r in _edr.items()
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
        _holder = getattr(ctx, "cairo_surface_holder", None)
        if _holder is not None:
            ctx.cairo_surface = _holder.surface
        return 'continue'
    if ctx.wave_formula_focus and not ctx.state.get("wave_formula_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
        ctx.wave_formula_focus = False
        ctx.state["wave_formula_focus"] = False
    # Top menu bar interactions
    return None
