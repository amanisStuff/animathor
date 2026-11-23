"""Event loop (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *


def _ev_keydown(ctx):
    import types as _types
    _ex_ctx = ctx._types.SimpleNamespace()
    _ex_ctx.__dict__.update({ctx.k:ctx.v for ctx.k,ctx.v in ctx.locals().items()})
    from controllers.key_down import handle_keydown as _hf
    _ex_r = _hf(_ex_ctx, ctx.event)
    for _k in ['_bezier_last_click', 'anchors', 'bezier_pen', 'bucket_fill_color', 'bucket_picker_drag', 'clock', 'color_target', 'comp_i', 'comps', 'current_points', 'curve_cut_mode', 'cut_points', 'cutting', 'drag_last', 'draw_shape', 'draw_tool', 'drawing', 'export_dialog_format', 'export_dialog_open', 'export_dpi', 'export_scale', 'eyedropper_pick', 'fill_stop_pos_drag', 'gradient_drag', 'guide_drag', 'guides', 'help_open', 'limit', 'marquee_select', 'max_points_per_curve', 'menu_open', 'obj_opacity_drag', 'pan_drag', 'panel_collapsed', 'pending_transform_toggle', 'picker_drag_alpha', 'picker_drag_hue', 'picker_drag_sv', 'picker_h', 'picker_s', 'picker_v', 'pivot_drag', 'pivot_pos', 'redrawing_curve', 'ref_drag', 'ref_opacity_drag', 'reference_error', 'reference_image', 'repeat_pick_mode', 'repeat_pick_target', 'running', 'screen', 'selected_curve', 'selected_curves', 'selected_point', 'selected_strokes', 'selection_submode', 'shape_menu_anchor', 'shape_menu_key', 'si', 'smart_snap_guides', 'snap', 'snap_enabled', 'space_panning', 'state', 'strokes', 'text_entry', 'tool_mode', 'transform_drag', 'w', 'wave_custom_drag', 'wave_formula_focus', 'wave_slider_drag', 'workspace', 'xform_field_buffer', 'xform_field_focus']:
        if hasattr(_ex_ctx, _k):
            setattr(ctx, _k, getattr(_ex_ctx, _k))
    if hasattr(_ex_ctx, 'mods'): mods = _ex_ctx.mods
    if hasattr(_ex_ctx, 'shift'): shift = _ex_ctx.shift
    if hasattr(_ex_ctx, 'step'): step = _ex_ctx.step
    if hasattr(_ex_ctx, 'wi'): wi = _ex_ctx.wi
    if _ex_r == 'continue':
        return 'continue'
    return None

def _ev_mbd1(ctx):
    import types as _types
    _mbd_ctx = ctx._types.SimpleNamespace()
    _mbd_ctx.__dict__.update({ctx.k:ctx.v for ctx.k,ctx.v in ctx.locals().items()})
    from controllers.mouse_button_down import handle_mousebuttondown1 as _hmbd
    _mbd_result = _hmbd(_mbd_ctx, ctx.event)
    for _k in ['_bezier_last_click', 'a', 'alpha', 'b', 'bar', 'base', 'bb', 'best_d', 'bezier_pen', 'boost_points', 'boxes', 'bucket_fill_color', 'bucket_picker_drag', 'c1', 'col', 'color_target', 'comp_i', 'comps', 'corner_radius', 'cpos', 'current_points', 'curve_cut_mode', 'cut_gap', 'cut_points', 'cutting', 'cx', 'cy', 'd', 'drag_last', 'draw_shape', 'draw_tool', 'drawing', 'dx', 'dy', 'ellipse_segments', 'ellipse_variant', 'end', 'export_dialog_format', 'export_dialog_open', 'export_dpi', 'export_scale', 'eyedropper_pick', 'field', 'fill_color', 'fill_stop_pos_drag', 'first', 'fixed_end', 'fixed_start', 'gradient_drag', 'guide_drag', 'guides', 'h', 'help_open', 'i', 'idxs', 'items', 'k', 'key', 'limit', 'line_arrow', 'line_constrain', 'marker_dropdown', 'marquee_select', 'max_points_per_curve', 'menu_open', 'mode', 'n', 'obj_opacity_drag', 'only', 'opacity', 'pan_drag', 'panel_collapsed', 'path', 'pending_transform_toggle', 'picker_drag_alpha', 'picker_drag_hue', 'picker_drag_sv', 'picker_h', 'picker_s', 'picker_v', 'pivot_drag', 'pivot_pos', 'polygon_sides', 'pos', 'primary', 'primary_i', 'r', 'rect_variant', 'redrawing_curve', 'ref_drag', 'ref_opacity_drag', 'reference_error', 'reference_image', 'repeat_pick_mode', 'repeat_pick_target', 'result', 'running', 's', 's1', 'scx', 'scy', 'segs', 'sel', 'sel_list', 'selected_curve', 'selected_curves', 'selected_point', 'selected_strokes', 'selection_submode', 'shadow', 'shape_menu_anchor', 'shape_menu_key', 'shift_held', 'si', 'smart_snap_guides', 'snap_enabled', 'sp', 'space_panning', 'st', 'star_inner_ratio', 'star_points', 'start_strokes', 'state', 'strokes', 'sv', 'sx1', 'sy1', 'tcx', 'tcy', 'text_entry', 'text_family', 'text_size', 'tool_mode', 'trace_algorithm', 'transform_drag', 'triangle_variant', 'tx1', 'ty1', 'val', 'w', 'wave_custom_drag', 'wave_formula_focus', 'wave_slider_drag', 'workspace', 'xform_field_buffer', 'xform_field_focus']:
        if hasattr(_mbd_ctx, _k):
            setattr(ctx, _k, getattr(_mbd_ctx, _k))
    if hasattr(_mbd_ctx, 'cfg'): cfg = _mbd_ctx.cfg
    if hasattr(_mbd_ctx, 'ci'): ci = _mbd_ctx.ci
    if hasattr(_mbd_ctx, 'comp'): comp = _mbd_ctx.comp
    if hasattr(_mbd_ctx, 'comp_style_target'): comp_style_target = _mbd_ctx.comp_style_target
    if hasattr(_mbd_ctx, 'handled'): handled = _mbd_ctx.handled
    if hasattr(_mbd_ctx, 'mods'): mods = _mbd_ctx.mods
    if hasattr(_mbd_ctx, 'picked'): picked = _mbd_ctx.picked
    if hasattr(_mbd_ctx, 'pname'): pname = _mbd_ctx.pname
    if hasattr(_mbd_ctx, 'rects'): rects = _mbd_ctx.rects
    if hasattr(_mbd_ctx, 'seg_i'): seg_i = _mbd_ctx.seg_i
    if hasattr(_mbd_ctx, 'shift'): shift = _mbd_ctx.shift
    if hasattr(_mbd_ctx, 'step'): step = _mbd_ctx.step
    if hasattr(_mbd_ctx, 't'): t = _mbd_ctx.t
    if hasattr(_mbd_ctx, 'wi'): wi = _mbd_ctx.wi
    if _mbd_result == 'continue':
        return 'continue'
    return None

def _ev_mbup1(ctx):
    import types as _types
    _ex_ctx = ctx._types.SimpleNamespace()
    _ex_ctx.__dict__.update({ctx.k:ctx.v for ctx.k,ctx.v in ctx.locals().items()})
    from controllers.mouse_button_up import handle_mousebuttonup1 as _hf
    _ex_r = _hf(_ex_ctx, ctx.event)
    for _k in ['_bezier_last_click', 'algo_name', 'base', 'bezier_pen', 'bucket_fill_color', 'bucket_picker_drag', 'c1', 'c2', 'clock', 'color_target', 'comp_i', 'cpos', 'current_points', 'curve_cut_mode', 'cut_points', 'cutting', 'drag_last', 'draw_shape', 'draw_tool', 'drawing', 'export_dialog_format', 'export_dialog_open', 'export_dpi', 'export_scale', 'eyedropper_pick', 'fill_stop_pos_drag', 'fixed_end', 'fixed_start', 'gradient_drag', 'guide_drag', 'guides', 'help_open', 'i', 'keys', 'marquee_select', 'max_points_per_curve', 'menu_open', 'obj_opacity_drag', 'only', 'p', 'p0', 'p3', 'pan_drag', 'panel_collapsed', 'pending_transform_toggle', 'picker_drag_alpha', 'picker_drag_hue', 'picker_drag_sv', 'picker_h', 'picker_s', 'picker_v', 'pivot_drag', 'pivot_pos', 'pts', 'r', 'redrawing_curve', 'ref_drag', 'ref_opacity_drag', 'reference_error', 'reference_image', 'repeat_pick_mode', 'repeat_pick_target', 'running', 's', 'screen', 'selected_curve', 'selected_curves', 'selected_point', 'selected_strokes', 'selection_submode', 'shape_menu_anchor', 'shape_menu_key', 'shift_held', 'si', 'smart_snap_guides', 'snap_enabled', 'space_panning', 'st', 'state', 'strokes', 'text_entry', 'tool_mode', 'transform_drag', 'transform_handle_mode', 'wave_custom_drag', 'wave_formula_focus', 'wave_slider_drag', 'workspace', 'xform_field_buffer', 'xform_field_focus']:
        if hasattr(_ex_ctx, _k):
            setattr(ctx, _k, getattr(_ex_ctx, _k))
    if hasattr(_ex_ctx, 'comp'): comp = _ex_ctx.comp
    if hasattr(_ex_ctx, 'picked'): picked = _ex_ctx.picked
    if _ex_r == 'continue':
        return 'continue'
    return None

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
            if _r == 'continue': continue
        elif ctx.event.type == pygame.MOUSEMOTION:
            import types as _types
            _mm_ctx = ctx._types.SimpleNamespace()
            _mm_ctx.__dict__.update({ctx.k:ctx.v for ctx.k,ctx.v in ctx.locals().items()})
            from controllers.mouse_motion import handle_mousemotion as _hmm
            _hmm(_mm_ctx, ctx.event)

        elif ctx.event.type == pygame.MOUSEBUTTONUP and ctx.event.button == 2:
            if ctx.pan_drag is not None and not ctx.space_panning:
                ctx.pan_drag = None
        elif ctx.event.type == pygame.MOUSEBUTTONUP and ctx.event.button == 1:
            _r = _ev_mbup1(ctx)
            if _r == 'continue': continue
