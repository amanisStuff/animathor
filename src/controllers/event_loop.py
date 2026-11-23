"""Event loop (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

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
            import types as _types
            _ex_ctx = ctx._types.SimpleNamespace()
            _ex_ctx.__dict__.update({ctx.k:ctx.v for ctx.k,ctx.v in ctx.locals().items()})
            from controllers.key_down import handle_keydown as _hf
            _ex_r = _hf(_ex_ctx, ctx.event)
            if hasattr(_ex_ctx, '_bezier_last_click'): ctx._bezier_last_click = _ex_ctx._bezier_last_click
            if hasattr(_ex_ctx, 'anchors'): ctx.anchors = _ex_ctx.anchors
            if hasattr(_ex_ctx, 'bezier_pen'): ctx.bezier_pen = _ex_ctx.bezier_pen
            if hasattr(_ex_ctx, 'bucket_fill_color'): ctx.bucket_fill_color = _ex_ctx.bucket_fill_color
            if hasattr(_ex_ctx, 'bucket_picker_drag'): ctx.bucket_picker_drag = _ex_ctx.bucket_picker_drag
            if hasattr(_ex_ctx, 'clock'): ctx.clock = _ex_ctx.clock
            if hasattr(_ex_ctx, 'color_target'): ctx.color_target = _ex_ctx.color_target
            if hasattr(_ex_ctx, 'comp_i'): ctx.comp_i = _ex_ctx.comp_i
            if hasattr(_ex_ctx, 'comps'): ctx.comps = _ex_ctx.comps
            if hasattr(_ex_ctx, 'current_points'): ctx.current_points = _ex_ctx.current_points
            if hasattr(_ex_ctx, 'curve_cut_mode'): ctx.curve_cut_mode = _ex_ctx.curve_cut_mode
            if hasattr(_ex_ctx, 'cut_points'): ctx.cut_points = _ex_ctx.cut_points
            if hasattr(_ex_ctx, 'cutting'): ctx.cutting = _ex_ctx.cutting
            if hasattr(_ex_ctx, 'drag_last'): ctx.drag_last = _ex_ctx.drag_last
            if hasattr(_ex_ctx, 'draw_shape'): ctx.draw_shape = _ex_ctx.draw_shape
            if hasattr(_ex_ctx, 'draw_tool'): ctx.draw_tool = _ex_ctx.draw_tool
            if hasattr(_ex_ctx, 'drawing'): ctx.drawing = _ex_ctx.drawing
            if hasattr(_ex_ctx, 'export_dialog_format'): ctx.export_dialog_format = _ex_ctx.export_dialog_format
            if hasattr(_ex_ctx, 'export_dialog_open'): ctx.export_dialog_open = _ex_ctx.export_dialog_open
            if hasattr(_ex_ctx, 'export_dpi'): ctx.export_dpi = _ex_ctx.export_dpi
            if hasattr(_ex_ctx, 'export_scale'): ctx.export_scale = _ex_ctx.export_scale
            if hasattr(_ex_ctx, 'eyedropper_pick'): ctx.eyedropper_pick = _ex_ctx.eyedropper_pick
            if hasattr(_ex_ctx, 'fill_stop_pos_drag'): ctx.fill_stop_pos_drag = _ex_ctx.fill_stop_pos_drag
            if hasattr(_ex_ctx, 'gradient_drag'): ctx.gradient_drag = _ex_ctx.gradient_drag
            if hasattr(_ex_ctx, 'guide_drag'): ctx.guide_drag = _ex_ctx.guide_drag
            if hasattr(_ex_ctx, 'guides'): ctx.guides = _ex_ctx.guides
            if hasattr(_ex_ctx, 'help_open'): ctx.help_open = _ex_ctx.help_open
            if hasattr(_ex_ctx, 'limit'): ctx.limit = _ex_ctx.limit
            if hasattr(_ex_ctx, 'marquee_select'): ctx.marquee_select = _ex_ctx.marquee_select
            if hasattr(_ex_ctx, 'max_points_per_curve'): ctx.max_points_per_curve = _ex_ctx.max_points_per_curve
            if hasattr(_ex_ctx, 'menu_open'): ctx.menu_open = _ex_ctx.menu_open
            if hasattr(_ex_ctx, 'mods'): mods = _ex_ctx.mods
            if hasattr(_ex_ctx, 'obj_opacity_drag'): ctx.obj_opacity_drag = _ex_ctx.obj_opacity_drag
            if hasattr(_ex_ctx, 'pan_drag'): ctx.pan_drag = _ex_ctx.pan_drag
            if hasattr(_ex_ctx, 'panel_collapsed'): ctx.panel_collapsed = _ex_ctx.panel_collapsed
            if hasattr(_ex_ctx, 'pending_transform_toggle'): ctx.pending_transform_toggle = _ex_ctx.pending_transform_toggle
            if hasattr(_ex_ctx, 'picker_drag_alpha'): ctx.picker_drag_alpha = _ex_ctx.picker_drag_alpha
            if hasattr(_ex_ctx, 'picker_drag_hue'): ctx.picker_drag_hue = _ex_ctx.picker_drag_hue
            if hasattr(_ex_ctx, 'picker_drag_sv'): ctx.picker_drag_sv = _ex_ctx.picker_drag_sv
            if hasattr(_ex_ctx, 'picker_h'): ctx.picker_h = _ex_ctx.picker_h
            if hasattr(_ex_ctx, 'picker_s'): ctx.picker_s = _ex_ctx.picker_s
            if hasattr(_ex_ctx, 'picker_v'): ctx.picker_v = _ex_ctx.picker_v
            if hasattr(_ex_ctx, 'pivot_drag'): ctx.pivot_drag = _ex_ctx.pivot_drag
            if hasattr(_ex_ctx, 'pivot_pos'): ctx.pivot_pos = _ex_ctx.pivot_pos
            if hasattr(_ex_ctx, 'redrawing_curve'): ctx.redrawing_curve = _ex_ctx.redrawing_curve
            if hasattr(_ex_ctx, 'ref_drag'): ctx.ref_drag = _ex_ctx.ref_drag
            if hasattr(_ex_ctx, 'ref_opacity_drag'): ctx.ref_opacity_drag = _ex_ctx.ref_opacity_drag
            if hasattr(_ex_ctx, 'reference_error'): ctx.reference_error = _ex_ctx.reference_error
            if hasattr(_ex_ctx, 'reference_image'): ctx.reference_image = _ex_ctx.reference_image
            if hasattr(_ex_ctx, 'repeat_pick_mode'): ctx.repeat_pick_mode = _ex_ctx.repeat_pick_mode
            if hasattr(_ex_ctx, 'repeat_pick_target'): ctx.repeat_pick_target = _ex_ctx.repeat_pick_target
            if hasattr(_ex_ctx, 'running'): ctx.running = _ex_ctx.running
            if hasattr(_ex_ctx, 'screen'): ctx.screen = _ex_ctx.screen
            if hasattr(_ex_ctx, 'selected_curve'): ctx.selected_curve = _ex_ctx.selected_curve
            if hasattr(_ex_ctx, 'selected_curves'): ctx.selected_curves = _ex_ctx.selected_curves
            if hasattr(_ex_ctx, 'selected_point'): ctx.selected_point = _ex_ctx.selected_point
            if hasattr(_ex_ctx, 'selected_strokes'): ctx.selected_strokes = _ex_ctx.selected_strokes
            if hasattr(_ex_ctx, 'selection_submode'): ctx.selection_submode = _ex_ctx.selection_submode
            if hasattr(_ex_ctx, 'shape_menu_anchor'): ctx.shape_menu_anchor = _ex_ctx.shape_menu_anchor
            if hasattr(_ex_ctx, 'shape_menu_key'): ctx.shape_menu_key = _ex_ctx.shape_menu_key
            if hasattr(_ex_ctx, 'shift'): shift = _ex_ctx.shift
            if hasattr(_ex_ctx, 'si'): ctx.si = _ex_ctx.si
            if hasattr(_ex_ctx, 'smart_snap_guides'): ctx.smart_snap_guides = _ex_ctx.smart_snap_guides
            if hasattr(_ex_ctx, 'snap'): ctx.snap = _ex_ctx.snap
            if hasattr(_ex_ctx, 'snap_enabled'): ctx.snap_enabled = _ex_ctx.snap_enabled
            if hasattr(_ex_ctx, 'space_panning'): ctx.space_panning = _ex_ctx.space_panning
            if hasattr(_ex_ctx, 'state'): ctx.state = _ex_ctx.state
            if hasattr(_ex_ctx, 'step'): step = _ex_ctx.step
            if hasattr(_ex_ctx, 'strokes'): ctx.strokes = _ex_ctx.strokes
            if hasattr(_ex_ctx, 'text_entry'): ctx.text_entry = _ex_ctx.text_entry
            if hasattr(_ex_ctx, 'tool_mode'): ctx.tool_mode = _ex_ctx.tool_mode
            if hasattr(_ex_ctx, 'transform_drag'): ctx.transform_drag = _ex_ctx.transform_drag
            if hasattr(_ex_ctx, 'w'): ctx.w = _ex_ctx.w
            if hasattr(_ex_ctx, 'wave_custom_drag'): ctx.wave_custom_drag = _ex_ctx.wave_custom_drag
            if hasattr(_ex_ctx, 'wave_formula_focus'): ctx.wave_formula_focus = _ex_ctx.wave_formula_focus
            if hasattr(_ex_ctx, 'wave_slider_drag'): ctx.wave_slider_drag = _ex_ctx.wave_slider_drag
            if hasattr(_ex_ctx, 'wi'): wi = _ex_ctx.wi
            if hasattr(_ex_ctx, 'workspace'): ctx.workspace = _ex_ctx.workspace
            if hasattr(_ex_ctx, 'xform_field_buffer'): ctx.xform_field_buffer = _ex_ctx.xform_field_buffer
            if hasattr(_ex_ctx, 'xform_field_focus'): ctx.xform_field_focus = _ex_ctx.xform_field_focus
            if _ex_r == 'continue':
                continue
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
            import types as _types
            _mbd_ctx = ctx._types.SimpleNamespace()
            _mbd_ctx.__dict__.update({ctx.k:ctx.v for ctx.k,ctx.v in ctx.locals().items()})
            from controllers.mouse_button_down import handle_mousebuttondown1 as _hmbd
            _mbd_result = _hmbd(_mbd_ctx, ctx.event)
            if hasattr(_mbd_ctx, '_bezier_last_click'): ctx._bezier_last_click = _mbd_ctx._bezier_last_click
            if hasattr(_mbd_ctx, 'a'): ctx.a = _mbd_ctx.a
            if hasattr(_mbd_ctx, 'alpha'): ctx.alpha = _mbd_ctx.alpha
            if hasattr(_mbd_ctx, 'b'): ctx.b = _mbd_ctx.b
            if hasattr(_mbd_ctx, 'bar'): ctx.bar = _mbd_ctx.bar
            if hasattr(_mbd_ctx, 'base'): ctx.base = _mbd_ctx.base
            if hasattr(_mbd_ctx, 'bb'): ctx.bb = _mbd_ctx.bb
            if hasattr(_mbd_ctx, 'best_d'): ctx.best_d = _mbd_ctx.best_d
            if hasattr(_mbd_ctx, 'bezier_pen'): ctx.bezier_pen = _mbd_ctx.bezier_pen
            if hasattr(_mbd_ctx, 'boost_points'): ctx.boost_points = _mbd_ctx.boost_points
            if hasattr(_mbd_ctx, 'boxes'): ctx.boxes = _mbd_ctx.boxes
            if hasattr(_mbd_ctx, 'bucket_fill_color'): ctx.bucket_fill_color = _mbd_ctx.bucket_fill_color
            if hasattr(_mbd_ctx, 'bucket_picker_drag'): ctx.bucket_picker_drag = _mbd_ctx.bucket_picker_drag
            if hasattr(_mbd_ctx, 'c1'): ctx.c1 = _mbd_ctx.c1
            if hasattr(_mbd_ctx, 'cfg'): cfg = _mbd_ctx.cfg
            if hasattr(_mbd_ctx, 'ci'): ci = _mbd_ctx.ci
            if hasattr(_mbd_ctx, 'col'): ctx.col = _mbd_ctx.col
            if hasattr(_mbd_ctx, 'color_target'): ctx.color_target = _mbd_ctx.color_target
            if hasattr(_mbd_ctx, 'comp'): comp = _mbd_ctx.comp
            if hasattr(_mbd_ctx, 'comp_i'): ctx.comp_i = _mbd_ctx.comp_i
            if hasattr(_mbd_ctx, 'comp_style_target'): comp_style_target = _mbd_ctx.comp_style_target
            if hasattr(_mbd_ctx, 'comps'): ctx.comps = _mbd_ctx.comps
            if hasattr(_mbd_ctx, 'corner_radius'): ctx.corner_radius = _mbd_ctx.corner_radius
            if hasattr(_mbd_ctx, 'cpos'): ctx.cpos = _mbd_ctx.cpos
            if hasattr(_mbd_ctx, 'current_points'): ctx.current_points = _mbd_ctx.current_points
            if hasattr(_mbd_ctx, 'curve_cut_mode'): ctx.curve_cut_mode = _mbd_ctx.curve_cut_mode
            if hasattr(_mbd_ctx, 'cut_gap'): ctx.cut_gap = _mbd_ctx.cut_gap
            if hasattr(_mbd_ctx, 'cut_points'): ctx.cut_points = _mbd_ctx.cut_points
            if hasattr(_mbd_ctx, 'cutting'): ctx.cutting = _mbd_ctx.cutting
            if hasattr(_mbd_ctx, 'cx'): ctx.cx = _mbd_ctx.cx
            if hasattr(_mbd_ctx, 'cy'): ctx.cy = _mbd_ctx.cy
            if hasattr(_mbd_ctx, 'd'): ctx.d = _mbd_ctx.d
            if hasattr(_mbd_ctx, 'drag_last'): ctx.drag_last = _mbd_ctx.drag_last
            if hasattr(_mbd_ctx, 'draw_shape'): ctx.draw_shape = _mbd_ctx.draw_shape
            if hasattr(_mbd_ctx, 'draw_tool'): ctx.draw_tool = _mbd_ctx.draw_tool
            if hasattr(_mbd_ctx, 'drawing'): ctx.drawing = _mbd_ctx.drawing
            if hasattr(_mbd_ctx, 'dx'): ctx.dx = _mbd_ctx.dx
            if hasattr(_mbd_ctx, 'dy'): ctx.dy = _mbd_ctx.dy
            if hasattr(_mbd_ctx, 'ellipse_segments'): ctx.ellipse_segments = _mbd_ctx.ellipse_segments
            if hasattr(_mbd_ctx, 'ellipse_variant'): ctx.ellipse_variant = _mbd_ctx.ellipse_variant
            if hasattr(_mbd_ctx, 'end'): ctx.end = _mbd_ctx.end
            if hasattr(_mbd_ctx, 'export_dialog_format'): ctx.export_dialog_format = _mbd_ctx.export_dialog_format
            if hasattr(_mbd_ctx, 'export_dialog_open'): ctx.export_dialog_open = _mbd_ctx.export_dialog_open
            if hasattr(_mbd_ctx, 'export_dpi'): ctx.export_dpi = _mbd_ctx.export_dpi
            if hasattr(_mbd_ctx, 'export_scale'): ctx.export_scale = _mbd_ctx.export_scale
            if hasattr(_mbd_ctx, 'eyedropper_pick'): ctx.eyedropper_pick = _mbd_ctx.eyedropper_pick
            if hasattr(_mbd_ctx, 'field'): ctx.field = _mbd_ctx.field
            if hasattr(_mbd_ctx, 'fill_color'): ctx.fill_color = _mbd_ctx.fill_color
            if hasattr(_mbd_ctx, 'fill_stop_pos_drag'): ctx.fill_stop_pos_drag = _mbd_ctx.fill_stop_pos_drag
            if hasattr(_mbd_ctx, 'first'): ctx.first = _mbd_ctx.first
            if hasattr(_mbd_ctx, 'fixed_end'): ctx.fixed_end = _mbd_ctx.fixed_end
            if hasattr(_mbd_ctx, 'fixed_start'): ctx.fixed_start = _mbd_ctx.fixed_start
            if hasattr(_mbd_ctx, 'gradient_drag'): ctx.gradient_drag = _mbd_ctx.gradient_drag
            if hasattr(_mbd_ctx, 'guide_drag'): ctx.guide_drag = _mbd_ctx.guide_drag
            if hasattr(_mbd_ctx, 'guides'): ctx.guides = _mbd_ctx.guides
            if hasattr(_mbd_ctx, 'h'): ctx.h = _mbd_ctx.h
            if hasattr(_mbd_ctx, 'handled'): handled = _mbd_ctx.handled
            if hasattr(_mbd_ctx, 'help_open'): ctx.help_open = _mbd_ctx.help_open
            if hasattr(_mbd_ctx, 'i'): ctx.i = _mbd_ctx.i
            if hasattr(_mbd_ctx, 'idxs'): ctx.idxs = _mbd_ctx.idxs
            if hasattr(_mbd_ctx, 'items'): ctx.items = _mbd_ctx.items
            if hasattr(_mbd_ctx, 'k'): ctx.k = _mbd_ctx.k
            if hasattr(_mbd_ctx, 'key'): ctx.key = _mbd_ctx.key
            if hasattr(_mbd_ctx, 'limit'): ctx.limit = _mbd_ctx.limit
            if hasattr(_mbd_ctx, 'line_arrow'): ctx.line_arrow = _mbd_ctx.line_arrow
            if hasattr(_mbd_ctx, 'line_constrain'): ctx.line_constrain = _mbd_ctx.line_constrain
            if hasattr(_mbd_ctx, 'marker_dropdown'): ctx.marker_dropdown = _mbd_ctx.marker_dropdown
            if hasattr(_mbd_ctx, 'marquee_select'): ctx.marquee_select = _mbd_ctx.marquee_select
            if hasattr(_mbd_ctx, 'max_points_per_curve'): ctx.max_points_per_curve = _mbd_ctx.max_points_per_curve
            if hasattr(_mbd_ctx, 'menu_open'): ctx.menu_open = _mbd_ctx.menu_open
            if hasattr(_mbd_ctx, 'mode'): ctx.mode = _mbd_ctx.mode
            if hasattr(_mbd_ctx, 'mods'): mods = _mbd_ctx.mods
            if hasattr(_mbd_ctx, 'n'): ctx.n = _mbd_ctx.n
            if hasattr(_mbd_ctx, 'obj_opacity_drag'): ctx.obj_opacity_drag = _mbd_ctx.obj_opacity_drag
            if hasattr(_mbd_ctx, 'only'): ctx.only = _mbd_ctx.only
            if hasattr(_mbd_ctx, 'opacity'): ctx.opacity = _mbd_ctx.opacity
            if hasattr(_mbd_ctx, 'pan_drag'): ctx.pan_drag = _mbd_ctx.pan_drag
            if hasattr(_mbd_ctx, 'panel_collapsed'): ctx.panel_collapsed = _mbd_ctx.panel_collapsed
            if hasattr(_mbd_ctx, 'path'): ctx.path = _mbd_ctx.path
            if hasattr(_mbd_ctx, 'pending_transform_toggle'): ctx.pending_transform_toggle = _mbd_ctx.pending_transform_toggle
            if hasattr(_mbd_ctx, 'picked'): picked = _mbd_ctx.picked
            if hasattr(_mbd_ctx, 'picker_drag_alpha'): ctx.picker_drag_alpha = _mbd_ctx.picker_drag_alpha
            if hasattr(_mbd_ctx, 'picker_drag_hue'): ctx.picker_drag_hue = _mbd_ctx.picker_drag_hue
            if hasattr(_mbd_ctx, 'picker_drag_sv'): ctx.picker_drag_sv = _mbd_ctx.picker_drag_sv
            if hasattr(_mbd_ctx, 'picker_h'): ctx.picker_h = _mbd_ctx.picker_h
            if hasattr(_mbd_ctx, 'picker_s'): ctx.picker_s = _mbd_ctx.picker_s
            if hasattr(_mbd_ctx, 'picker_v'): ctx.picker_v = _mbd_ctx.picker_v
            if hasattr(_mbd_ctx, 'pivot_drag'): ctx.pivot_drag = _mbd_ctx.pivot_drag
            if hasattr(_mbd_ctx, 'pivot_pos'): ctx.pivot_pos = _mbd_ctx.pivot_pos
            if hasattr(_mbd_ctx, 'pname'): pname = _mbd_ctx.pname
            if hasattr(_mbd_ctx, 'polygon_sides'): ctx.polygon_sides = _mbd_ctx.polygon_sides
            if hasattr(_mbd_ctx, 'pos'): ctx.pos = _mbd_ctx.pos
            if hasattr(_mbd_ctx, 'primary'): ctx.primary = _mbd_ctx.primary
            if hasattr(_mbd_ctx, 'primary_i'): ctx.primary_i = _mbd_ctx.primary_i
            if hasattr(_mbd_ctx, 'r'): ctx.r = _mbd_ctx.r
            if hasattr(_mbd_ctx, 'rect_variant'): ctx.rect_variant = _mbd_ctx.rect_variant
            if hasattr(_mbd_ctx, 'rects'): rects = _mbd_ctx.rects
            if hasattr(_mbd_ctx, 'redrawing_curve'): ctx.redrawing_curve = _mbd_ctx.redrawing_curve
            if hasattr(_mbd_ctx, 'ref_drag'): ctx.ref_drag = _mbd_ctx.ref_drag
            if hasattr(_mbd_ctx, 'ref_opacity_drag'): ctx.ref_opacity_drag = _mbd_ctx.ref_opacity_drag
            if hasattr(_mbd_ctx, 'reference_error'): ctx.reference_error = _mbd_ctx.reference_error
            if hasattr(_mbd_ctx, 'reference_image'): ctx.reference_image = _mbd_ctx.reference_image
            if hasattr(_mbd_ctx, 'repeat_pick_mode'): ctx.repeat_pick_mode = _mbd_ctx.repeat_pick_mode
            if hasattr(_mbd_ctx, 'repeat_pick_target'): ctx.repeat_pick_target = _mbd_ctx.repeat_pick_target
            if hasattr(_mbd_ctx, 'result'): ctx.result = _mbd_ctx.result
            if hasattr(_mbd_ctx, 'running'): ctx.running = _mbd_ctx.running
            if hasattr(_mbd_ctx, 's'): ctx.s = _mbd_ctx.s
            if hasattr(_mbd_ctx, 's1'): ctx.s1 = _mbd_ctx.s1
            if hasattr(_mbd_ctx, 'scx'): ctx.scx = _mbd_ctx.scx
            if hasattr(_mbd_ctx, 'scy'): ctx.scy = _mbd_ctx.scy
            if hasattr(_mbd_ctx, 'seg_i'): seg_i = _mbd_ctx.seg_i
            if hasattr(_mbd_ctx, 'segs'): ctx.segs = _mbd_ctx.segs
            if hasattr(_mbd_ctx, 'sel'): ctx.sel = _mbd_ctx.sel
            if hasattr(_mbd_ctx, 'sel_list'): ctx.sel_list = _mbd_ctx.sel_list
            if hasattr(_mbd_ctx, 'selected_curve'): ctx.selected_curve = _mbd_ctx.selected_curve
            if hasattr(_mbd_ctx, 'selected_curves'): ctx.selected_curves = _mbd_ctx.selected_curves
            if hasattr(_mbd_ctx, 'selected_point'): ctx.selected_point = _mbd_ctx.selected_point
            if hasattr(_mbd_ctx, 'selected_strokes'): ctx.selected_strokes = _mbd_ctx.selected_strokes
            if hasattr(_mbd_ctx, 'selection_submode'): ctx.selection_submode = _mbd_ctx.selection_submode
            if hasattr(_mbd_ctx, 'shadow'): ctx.shadow = _mbd_ctx.shadow
            if hasattr(_mbd_ctx, 'shape_menu_anchor'): ctx.shape_menu_anchor = _mbd_ctx.shape_menu_anchor
            if hasattr(_mbd_ctx, 'shape_menu_key'): ctx.shape_menu_key = _mbd_ctx.shape_menu_key
            if hasattr(_mbd_ctx, 'shift'): shift = _mbd_ctx.shift
            if hasattr(_mbd_ctx, 'shift_held'): ctx.shift_held = _mbd_ctx.shift_held
            if hasattr(_mbd_ctx, 'si'): ctx.si = _mbd_ctx.si
            if hasattr(_mbd_ctx, 'smart_snap_guides'): ctx.smart_snap_guides = _mbd_ctx.smart_snap_guides
            if hasattr(_mbd_ctx, 'snap_enabled'): ctx.snap_enabled = _mbd_ctx.snap_enabled
            if hasattr(_mbd_ctx, 'sp'): ctx.sp = _mbd_ctx.sp
            if hasattr(_mbd_ctx, 'space_panning'): ctx.space_panning = _mbd_ctx.space_panning
            if hasattr(_mbd_ctx, 'st'): ctx.st = _mbd_ctx.st
            if hasattr(_mbd_ctx, 'star_inner_ratio'): ctx.star_inner_ratio = _mbd_ctx.star_inner_ratio
            if hasattr(_mbd_ctx, 'star_points'): ctx.star_points = _mbd_ctx.star_points
            if hasattr(_mbd_ctx, 'start_strokes'): ctx.start_strokes = _mbd_ctx.start_strokes
            if hasattr(_mbd_ctx, 'state'): ctx.state = _mbd_ctx.state
            if hasattr(_mbd_ctx, 'step'): step = _mbd_ctx.step
            if hasattr(_mbd_ctx, 'strokes'): ctx.strokes = _mbd_ctx.strokes
            if hasattr(_mbd_ctx, 'sv'): ctx.sv = _mbd_ctx.sv
            if hasattr(_mbd_ctx, 'sx1'): ctx.sx1 = _mbd_ctx.sx1
            if hasattr(_mbd_ctx, 'sy1'): ctx.sy1 = _mbd_ctx.sy1
            if hasattr(_mbd_ctx, 't'): t = _mbd_ctx.t
            if hasattr(_mbd_ctx, 'tcx'): ctx.tcx = _mbd_ctx.tcx
            if hasattr(_mbd_ctx, 'tcy'): ctx.tcy = _mbd_ctx.tcy
            if hasattr(_mbd_ctx, 'text_entry'): ctx.text_entry = _mbd_ctx.text_entry
            if hasattr(_mbd_ctx, 'text_family'): ctx.text_family = _mbd_ctx.text_family
            if hasattr(_mbd_ctx, 'text_size'): ctx.text_size = _mbd_ctx.text_size
            if hasattr(_mbd_ctx, 'tool_mode'): ctx.tool_mode = _mbd_ctx.tool_mode
            if hasattr(_mbd_ctx, 'trace_algorithm'): ctx.trace_algorithm = _mbd_ctx.trace_algorithm
            if hasattr(_mbd_ctx, 'transform_drag'): ctx.transform_drag = _mbd_ctx.transform_drag
            if hasattr(_mbd_ctx, 'triangle_variant'): ctx.triangle_variant = _mbd_ctx.triangle_variant
            if hasattr(_mbd_ctx, 'tx1'): ctx.tx1 = _mbd_ctx.tx1
            if hasattr(_mbd_ctx, 'ty1'): ctx.ty1 = _mbd_ctx.ty1
            if hasattr(_mbd_ctx, 'val'): ctx.val = _mbd_ctx.val
            if hasattr(_mbd_ctx, 'w'): ctx.w = _mbd_ctx.w
            if hasattr(_mbd_ctx, 'wave_custom_drag'): ctx.wave_custom_drag = _mbd_ctx.wave_custom_drag
            if hasattr(_mbd_ctx, 'wave_formula_focus'): ctx.wave_formula_focus = _mbd_ctx.wave_formula_focus
            if hasattr(_mbd_ctx, 'wave_slider_drag'): ctx.wave_slider_drag = _mbd_ctx.wave_slider_drag
            if hasattr(_mbd_ctx, 'wi'): wi = _mbd_ctx.wi
            if hasattr(_mbd_ctx, 'workspace'): ctx.workspace = _mbd_ctx.workspace
            if hasattr(_mbd_ctx, 'xform_field_buffer'): ctx.xform_field_buffer = _mbd_ctx.xform_field_buffer
            if hasattr(_mbd_ctx, 'xform_field_focus'): ctx.xform_field_focus = _mbd_ctx.xform_field_focus
            if _mbd_result == 'continue':
                continue
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
            import types as _types
            _ex_ctx = ctx._types.SimpleNamespace()
            _ex_ctx.__dict__.update({ctx.k:ctx.v for ctx.k,ctx.v in ctx.locals().items()})
            from controllers.mouse_button_up import handle_mousebuttonup1 as _hf
            _ex_r = _hf(_ex_ctx, ctx.event)
            if hasattr(_ex_ctx, '_bezier_last_click'): ctx._bezier_last_click = _ex_ctx._bezier_last_click
            if hasattr(_ex_ctx, 'algo_name'): ctx.algo_name = _ex_ctx.algo_name
            if hasattr(_ex_ctx, 'base'): ctx.base = _ex_ctx.base
            if hasattr(_ex_ctx, 'bezier_pen'): ctx.bezier_pen = _ex_ctx.bezier_pen
            if hasattr(_ex_ctx, 'bucket_fill_color'): ctx.bucket_fill_color = _ex_ctx.bucket_fill_color
            if hasattr(_ex_ctx, 'bucket_picker_drag'): ctx.bucket_picker_drag = _ex_ctx.bucket_picker_drag
            if hasattr(_ex_ctx, 'c1'): ctx.c1 = _ex_ctx.c1
            if hasattr(_ex_ctx, 'c2'): ctx.c2 = _ex_ctx.c2
            if hasattr(_ex_ctx, 'clock'): ctx.clock = _ex_ctx.clock
            if hasattr(_ex_ctx, 'color_target'): ctx.color_target = _ex_ctx.color_target
            if hasattr(_ex_ctx, 'comp'): comp = _ex_ctx.comp
            if hasattr(_ex_ctx, 'comp_i'): ctx.comp_i = _ex_ctx.comp_i
            if hasattr(_ex_ctx, 'cpos'): ctx.cpos = _ex_ctx.cpos
            if hasattr(_ex_ctx, 'current_points'): ctx.current_points = _ex_ctx.current_points
            if hasattr(_ex_ctx, 'curve_cut_mode'): ctx.curve_cut_mode = _ex_ctx.curve_cut_mode
            if hasattr(_ex_ctx, 'cut_points'): ctx.cut_points = _ex_ctx.cut_points
            if hasattr(_ex_ctx, 'cutting'): ctx.cutting = _ex_ctx.cutting
            if hasattr(_ex_ctx, 'drag_last'): ctx.drag_last = _ex_ctx.drag_last
            if hasattr(_ex_ctx, 'draw_shape'): ctx.draw_shape = _ex_ctx.draw_shape
            if hasattr(_ex_ctx, 'draw_tool'): ctx.draw_tool = _ex_ctx.draw_tool
            if hasattr(_ex_ctx, 'drawing'): ctx.drawing = _ex_ctx.drawing
            if hasattr(_ex_ctx, 'export_dialog_format'): ctx.export_dialog_format = _ex_ctx.export_dialog_format
            if hasattr(_ex_ctx, 'export_dialog_open'): ctx.export_dialog_open = _ex_ctx.export_dialog_open
            if hasattr(_ex_ctx, 'export_dpi'): ctx.export_dpi = _ex_ctx.export_dpi
            if hasattr(_ex_ctx, 'export_scale'): ctx.export_scale = _ex_ctx.export_scale
            if hasattr(_ex_ctx, 'eyedropper_pick'): ctx.eyedropper_pick = _ex_ctx.eyedropper_pick
            if hasattr(_ex_ctx, 'fill_stop_pos_drag'): ctx.fill_stop_pos_drag = _ex_ctx.fill_stop_pos_drag
            if hasattr(_ex_ctx, 'fixed_end'): ctx.fixed_end = _ex_ctx.fixed_end
            if hasattr(_ex_ctx, 'fixed_start'): ctx.fixed_start = _ex_ctx.fixed_start
            if hasattr(_ex_ctx, 'gradient_drag'): ctx.gradient_drag = _ex_ctx.gradient_drag
            if hasattr(_ex_ctx, 'guide_drag'): ctx.guide_drag = _ex_ctx.guide_drag
            if hasattr(_ex_ctx, 'guides'): ctx.guides = _ex_ctx.guides
            if hasattr(_ex_ctx, 'help_open'): ctx.help_open = _ex_ctx.help_open
            if hasattr(_ex_ctx, 'i'): ctx.i = _ex_ctx.i
            if hasattr(_ex_ctx, 'keys'): ctx.keys = _ex_ctx.keys
            if hasattr(_ex_ctx, 'marquee_select'): ctx.marquee_select = _ex_ctx.marquee_select
            if hasattr(_ex_ctx, 'max_points_per_curve'): ctx.max_points_per_curve = _ex_ctx.max_points_per_curve
            if hasattr(_ex_ctx, 'menu_open'): ctx.menu_open = _ex_ctx.menu_open
            if hasattr(_ex_ctx, 'obj_opacity_drag'): ctx.obj_opacity_drag = _ex_ctx.obj_opacity_drag
            if hasattr(_ex_ctx, 'only'): ctx.only = _ex_ctx.only
            if hasattr(_ex_ctx, 'p'): ctx.p = _ex_ctx.p
            if hasattr(_ex_ctx, 'p0'): ctx.p0 = _ex_ctx.p0
            if hasattr(_ex_ctx, 'p3'): ctx.p3 = _ex_ctx.p3
            if hasattr(_ex_ctx, 'pan_drag'): ctx.pan_drag = _ex_ctx.pan_drag
            if hasattr(_ex_ctx, 'panel_collapsed'): ctx.panel_collapsed = _ex_ctx.panel_collapsed
            if hasattr(_ex_ctx, 'pending_transform_toggle'): ctx.pending_transform_toggle = _ex_ctx.pending_transform_toggle
            if hasattr(_ex_ctx, 'picked'): picked = _ex_ctx.picked
            if hasattr(_ex_ctx, 'picker_drag_alpha'): ctx.picker_drag_alpha = _ex_ctx.picker_drag_alpha
            if hasattr(_ex_ctx, 'picker_drag_hue'): ctx.picker_drag_hue = _ex_ctx.picker_drag_hue
            if hasattr(_ex_ctx, 'picker_drag_sv'): ctx.picker_drag_sv = _ex_ctx.picker_drag_sv
            if hasattr(_ex_ctx, 'picker_h'): ctx.picker_h = _ex_ctx.picker_h
            if hasattr(_ex_ctx, 'picker_s'): ctx.picker_s = _ex_ctx.picker_s
            if hasattr(_ex_ctx, 'picker_v'): ctx.picker_v = _ex_ctx.picker_v
            if hasattr(_ex_ctx, 'pivot_drag'): ctx.pivot_drag = _ex_ctx.pivot_drag
            if hasattr(_ex_ctx, 'pivot_pos'): ctx.pivot_pos = _ex_ctx.pivot_pos
            if hasattr(_ex_ctx, 'pts'): ctx.pts = _ex_ctx.pts
            if hasattr(_ex_ctx, 'r'): ctx.r = _ex_ctx.r
            if hasattr(_ex_ctx, 'redrawing_curve'): ctx.redrawing_curve = _ex_ctx.redrawing_curve
            if hasattr(_ex_ctx, 'ref_drag'): ctx.ref_drag = _ex_ctx.ref_drag
            if hasattr(_ex_ctx, 'ref_opacity_drag'): ctx.ref_opacity_drag = _ex_ctx.ref_opacity_drag
            if hasattr(_ex_ctx, 'reference_error'): ctx.reference_error = _ex_ctx.reference_error
            if hasattr(_ex_ctx, 'reference_image'): ctx.reference_image = _ex_ctx.reference_image
            if hasattr(_ex_ctx, 'repeat_pick_mode'): ctx.repeat_pick_mode = _ex_ctx.repeat_pick_mode
            if hasattr(_ex_ctx, 'repeat_pick_target'): ctx.repeat_pick_target = _ex_ctx.repeat_pick_target
            if hasattr(_ex_ctx, 'running'): ctx.running = _ex_ctx.running
            if hasattr(_ex_ctx, 's'): ctx.s = _ex_ctx.s
            if hasattr(_ex_ctx, 'screen'): ctx.screen = _ex_ctx.screen
            if hasattr(_ex_ctx, 'selected_curve'): ctx.selected_curve = _ex_ctx.selected_curve
            if hasattr(_ex_ctx, 'selected_curves'): ctx.selected_curves = _ex_ctx.selected_curves
            if hasattr(_ex_ctx, 'selected_point'): ctx.selected_point = _ex_ctx.selected_point
            if hasattr(_ex_ctx, 'selected_strokes'): ctx.selected_strokes = _ex_ctx.selected_strokes
            if hasattr(_ex_ctx, 'selection_submode'): ctx.selection_submode = _ex_ctx.selection_submode
            if hasattr(_ex_ctx, 'shape_menu_anchor'): ctx.shape_menu_anchor = _ex_ctx.shape_menu_anchor
            if hasattr(_ex_ctx, 'shape_menu_key'): ctx.shape_menu_key = _ex_ctx.shape_menu_key
            if hasattr(_ex_ctx, 'shift_held'): ctx.shift_held = _ex_ctx.shift_held
            if hasattr(_ex_ctx, 'si'): ctx.si = _ex_ctx.si
            if hasattr(_ex_ctx, 'smart_snap_guides'): ctx.smart_snap_guides = _ex_ctx.smart_snap_guides
            if hasattr(_ex_ctx, 'snap_enabled'): ctx.snap_enabled = _ex_ctx.snap_enabled
            if hasattr(_ex_ctx, 'space_panning'): ctx.space_panning = _ex_ctx.space_panning
            if hasattr(_ex_ctx, 'st'): ctx.st = _ex_ctx.st
            if hasattr(_ex_ctx, 'state'): ctx.state = _ex_ctx.state
            if hasattr(_ex_ctx, 'strokes'): ctx.strokes = _ex_ctx.strokes
            if hasattr(_ex_ctx, 'text_entry'): ctx.text_entry = _ex_ctx.text_entry
            if hasattr(_ex_ctx, 'tool_mode'): ctx.tool_mode = _ex_ctx.tool_mode
            if hasattr(_ex_ctx, 'transform_drag'): ctx.transform_drag = _ex_ctx.transform_drag
            if hasattr(_ex_ctx, 'transform_handle_mode'): ctx.transform_handle_mode = _ex_ctx.transform_handle_mode
            if hasattr(_ex_ctx, 'wave_custom_drag'): ctx.wave_custom_drag = _ex_ctx.wave_custom_drag
            if hasattr(_ex_ctx, 'wave_formula_focus'): ctx.wave_formula_focus = _ex_ctx.wave_formula_focus
            if hasattr(_ex_ctx, 'wave_slider_drag'): ctx.wave_slider_drag = _ex_ctx.wave_slider_drag
            if hasattr(_ex_ctx, 'workspace'): ctx.workspace = _ex_ctx.workspace
            if hasattr(_ex_ctx, 'xform_field_buffer'): ctx.xform_field_buffer = _ex_ctx.xform_field_buffer
            if hasattr(_ex_ctx, 'xform_field_focus'): ctx.xform_field_focus = _ex_ctx.xform_field_focus
            if _ex_r == 'continue':
                continue
    return None
