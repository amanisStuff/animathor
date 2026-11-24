"""Event loop (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *


def _sync_all(ctx, src):
    """Sync all attributes from handler ctx back to event ctx.

    Replaces hardcoded per-handler sync field lists. This keeps the extraction
    boundary behavior-preserving while eliminating sync-plumbing maintenance.
    """
    ctx.__dict__.update(src.__dict__)


def _call_handler(ctx, handler_fn):
    import types as _types
    ex = _types.SimpleNamespace(**ctx.__dict__)
    result = handler_fn(ex, ctx.event)
    _sync_all(ctx, ex)
    return result


def _ev_keydown(ctx):
    from controllers.key_down import handle_keydown
    r = _call_handler(ctx, handle_keydown)
    return 'continue' if r == 'continue' else None


def _ev_mbd1(ctx):
    from controllers.mouse_button_down import handle_mousebuttondown1
    r = _call_handler(ctx, handle_mousebuttondown1)
    return 'continue' if r == 'continue' else None


def _ev_mbup1(ctx):
    from controllers.mouse_button_up import handle_mousebuttonup1
    r = _call_handler(ctx, handle_mousebuttonup1)
    return 'continue' if r == 'continue' else None

def process_events(ctx):
    for ctx.event in pygame.event.get():
        if ctx.event.type == pygame.QUIT:
            ctx.running = False
            break
        if ctx.event.type == pygame.VIDEORESIZE:
            # Handle window resize - maintain layout
            ctx.new_w = max(800, ctx.event.w)
            ctx.new_h = max(400, ctx.event.h)
            # Recreate screen surface with new size
            ctx.screen = pygame.display.set_mode((ctx.new_w, ctx.new_h), pygame.RESIZABLE)
            cfg.WIDTH = ctx.new_w
            cfg.HEIGHT = ctx.new_h
            ctx.relayout()

        if ctx.event.type == pygame.MOUSEWHEEL:
            _mx, _my = pygame.mouse.get_pos()
            if _mx >= cfg.PANEL_X:
                # scroll the right panel when the pointer is over it
                ctx.panel_scroll = max(0, int(ctx.panel_scroll - ctx.event.y * 48))
                ctx.state["panel_scroll"] = ctx.panel_scroll
            elif ctx.in_canvas((_mx, _my)):
                # zoom canvas toward cursor
                old_z = float(getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0)
                factor = 1.1 if ctx.event.y > 0 else (1 / 1.1)
                new_z = max(0.1, min(20.0, old_z * (factor ** abs(ctx.event.y))))
                if new_z != old_z:
                    wx, wy = ctx.to_canvas((_mx, _my))
                    cfg.VIEW_ZOOM = new_z
                    cfg.VIEW_PAN_X = _mx - cfg.CANVAS_X - wx * new_z
                    cfg.VIEW_PAN_Y = _my - wy * new_z

        if ctx.slider.handle_event(ctx.event):
            ctx.max_points_per_curve = ctx.slider.value
        _cut_gap_active = ((ctx.tool_mode == "draw" and ctx.draw_tool == "cutter")
                           or (ctx.tool_mode == "selection" and ctx.curve_cut_mode))
        if (_cut_gap_active and ctx.cut_gap_slider.track.width > 0
                and ctx.cut_gap_slider.handle_event(ctx.event)):
            ctx.cut_gap = ctx.cut_gap_slider.value
            ctx.state["cut_gap"] = ctx.cut_gap
        comp_style_target = None
        if ctx.tool_mode == "selection" and ctx.selection_submode == "curve" and ctx.selected_curve and len(ctx.selected_strokes) == 1:
            scv = ctx.selected_curve
            if scv and scv[0] in ctx.selected_strokes:
                comp_style_target = (scv[0], scv[1])
        point_style_target = None
        if ctx.tool_mode == "selection" and ctx.selection_submode == "nodes" and ctx.selected_point and len(ctx.selected_strokes) == 1:
            ctx.si = ctx.next(iter(ctx.selected_strokes))
            seg_i, pname = ctx.selected_point
            if pname in ("p0", "p3") and 0 <= ctx.si < len(ctx.strokes):
                point_style_target = (ctx.si, seg_i, pname)
        if ctx.tool_mode == "selection" and ctx.selected_strokes and ctx.width_slider.handle_event(ctx.event):
            if ctx.selection_submode == "transform":
                for ctx.si in ctx.selected_strokes:
                    if 0 <= ctx.si < len(ctx.strokes):
                        ctx.strokes[ctx.si]["stroke_width"] = float(ctx.width_slider.value)
            elif comp_style_target is not None:
                ctx.si, ci = comp_style_target
                if 0 <= ctx.si < len(ctx.strokes):
                    ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
                    if 0 <= ci < len(ctx.comps):
                        ctx.comps[ci]["stroke_width"] = float(ctx.width_slider.value)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
            elif point_style_target is not None:
                ctx.si, seg_i, pname = point_style_target
                if 0 <= ctx.si < len(ctx.strokes):
                    set_point_width(ctx.strokes[ctx.si], seg_i, pname, float(ctx.width_slider.value))

        if ctx.event.type == pygame.KEYDOWN:
            _r = _ev_keydown(ctx)
            if _r == 'continue': continue
        elif ctx.event.type == pygame.KEYUP:
            if ctx.event.key == pygame.K_SPACE:
                ctx.space_panning = False
                ctx.pan_drag = None
            if ctx.event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                if ctx.drawing and ctx.tool_mode == "draw" and ctx.current_points:
                    ctx.snap = ctx.nearest_snap_point(ctx.current_points[-1], ctx.strokes, ctx.snap_radius())
                    if ctx.snap is not None:
                        ctx.current_points[-1] = ctx.snap
                elif ctx.redrawing_curve is not None and ctx.redrawing_curve.get("started") and ctx.redrawing_curve.get("points"):
                    if ctx.redrawing_curve.get("fixed_end") is None:
                        ctx.snap = ctx.nearest_snap_point(ctx.redrawing_curve["points"][-1], ctx.strokes, ctx.snap_radius())
                        if ctx.snap is not None:
                            ctx.redrawing_curve["points"][-1] = ctx.snap

        elif ctx.event.type == pygame.MOUSEBUTTONDOWN and ctx.event.button == 2:
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None:
                from controllers.drag.pan_session import PanDragSession
                dm.begin(PanDragSession(), ctx, ctx.event)
            else:
                ctx.pan_drag = {"start_mouse": ctx.event.pos, "start_pan": (getattr(cfg, "VIEW_PAN_X", 0.0), getattr(cfg, "VIEW_PAN_Y", 0.0))}
        elif ctx.event.type == pygame.MOUSEBUTTONDOWN and ctx.event.button == 3:
            if ctx.export_dialog_open:
                continue
            # Right-click a bottom-bar shape tool: its options popup above the button.
            _shape_rects = ctx.state.get("draw_shape_rects", {})
            _rc_hit = ctx.next((ctx.k for ctx.k, ctx.r in _shape_rects.items() if ctx.r.collidepoint(ctx.event.pos)), None)
            _draw_keys = {ctx.k for ctx.k, ctx._ in ctx.DRAW_SHAPES} | {ctx.k for ctx.k, ctx._ in ctx.BOTTOM_TOOLS}
            if _rc_hit is not None and ctx.tool_mode == "draw" and _rc_hit in _draw_keys:
                if ctx.shape_menu_key == _rc_hit:
                    ctx.shape_menu_key = None
                else:
                    ctx.shape_menu_key = _rc_hit
                    ctx.shape_menu_anchor = _shape_rects[_rc_hit].copy()
                    ctx.menu_open = None
            else:
                ctx.shape_menu_key = None
            ctx.state["shape_menu_key"] = ctx.shape_menu_key
            ctx.state["shape_menu_anchor"] = ctx.shape_menu_anchor
        elif ctx.event.type == pygame.MOUSEBUTTONDOWN and ctx.event.button == 1:
            _r = _ev_mbd1(ctx)
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None and dm.active is None:
                if (ctx.tool_mode == 'draw' and ctx.draw_tool == 'pen'
                        and ctx.draw_shape == 'pen' and ctx.bezier_pen is not None):
                    from controllers.drag.bezier_session import BezierPenSession
                    dm.begin(BezierPenSession(), ctx, ctx.event)
            if _r == 'continue': continue
        elif ctx.event.type == pygame.MOUSEMOTION:
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None:
                from controllers.drag.ui_session import ui_drag_active, UiDragSession
                if dm.active is None and ui_drag_active(ctx):
                    dm.begin(UiDragSession(), ctx, ctx.event)
                if dm.active is not None and dm.active.name == 'ui':
                    if dm.move(ctx, ctx.event):
                        continue
                    dm.end(ctx, ctx.event)
            if dm is not None and dm.active is not None and dm.active.name in ('pan', 'guide', 'marquee', 'pivot', 'ref', 'transform', 'gradient', 'cutter', 'draw', 'redraw'):
                if dm.move(ctx, ctx.event):
                    continue
            if dm is not None:
                from controllers.drag.bezier_session import BezierPenSession
                if dm.modal_motion(BezierPenSession(), ctx, ctx.event):
                    continue
            import types as _types
            _mm_ctx = _types.SimpleNamespace(**ctx.__dict__)
            from controllers.mouse_motion import handle_mousemotion as _hmm
            _hmm(_mm_ctx, ctx.event)
            _sync_all(ctx, _mm_ctx)

        elif ctx.event.type == pygame.MOUSEBUTTONUP and ctx.event.button == 2:
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None and dm.active is not None and dm.active.name == 'pan':
                dm.end(ctx, ctx.event)
            elif ctx.pan_drag is not None and not ctx.space_panning:
                ctx.pan_drag = None
        elif ctx.event.type == pygame.MOUSEBUTTONUP and ctx.event.button == 1:
            _r = _ev_mbup1(ctx)
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None and dm.active is not None and dm.active.name in ('guide', 'pan', 'marquee', 'pivot', 'ref', 'transform', 'gradient', 'cutter', 'draw', 'redraw', 'bezier', 'ui'):
                dm.end(ctx, ctx.event)
            if _r == 'continue': continue
