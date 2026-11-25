"""Toolbar click handling for MOUSEBUTTONDOWN."""
import copy, math, pygame
import config as cfg
from models import add_guide, hit_guide, mirror_stroke, set_marker  # noqa: F401
from views import TRACE_ALGORITHMS, TRIANGLE_VARIANTS, export_scene_image, pick_export_image_path  # noqa: F401
from controllers.mouse_button_down_panel import _handle_panel_click
from controllers.mouse_button_down_canvas import _handle_canvas_click









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
        _hit_key = next((ctx.k for ctx.k, ctx.r in ctx.state.get("draw_shape_rects", {}).items() if ctx.r.collidepoint(event.pos)), None)
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
