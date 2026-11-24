"""Transform selection submode handler."""

import copy
import math
import pygame
from models import group_id_of, group_members, hit_test_bbox_handle, hit_test_stroke, point_in_bbox  # noqa: F401


def handle_transform_mode(ctx, event):
    ctx.cpos = ctx.to_canvas(event.pos)
    ctx.handled = False
    ctx.pending_transform_toggle = None
    if ctx.selected_strokes:
        ctx.bb = ctx.combined_obb(ctx.strokes, ctx.selected_strokes)
        # Gradient on-canvas handle hit-test (when editing fill gradient)
        if not ctx.handled and ctx.state.get("color_target", ctx.color_target) == "fill":
            _g_primary = None
            _g_grad = None
            for ctx._gsi in sorted(ctx.selected_strokes):
                if 0 <= ctx._gsi < len(ctx.strokes):
                    ctx._gst = ctx.strokes[ctx._gsi]
                    ctx._gfg = ctx._gst.get("fill_gradient") if isinstance(ctx._gst, dict) else None
                    try:
                        ctx._gfg = ctx.get_fill_gradient(ctx._gst) or ctx._gfg
                    except Exception:
                        pass
                    if isinstance(ctx._gfg, dict) and str(ctx._gfg.get("type")) in ("linear", "radial", "conic", "spiral", "diamond", "square"):
                        _g_primary = ctx._gsi
                        _g_grad = ctx._gfg
                        break
            if _g_primary is not None and _g_grad is not None:
                _ghit, _ginfo = ctx.hit_test_gradient_handle(ctx.strokes[_g_primary], _g_grad, ctx.cpos)
                if _ghit is not None:
                    ctx.push_undo()
                    _gtype = str(_g_grad.get("type", "linear"))
                    _edit_strokes = []
                    for ctx._gsi in sorted(ctx.selected_strokes):
                        if 0 <= ctx._gsi < len(ctx.strokes):
                            ctx._gst = ctx.strokes[ctx._gsi]
                            _fg2 = ctx._gst.get("fill_gradient") if isinstance(ctx._gst, dict) else None
                            try:
                                _fg2 = ctx.get_fill_gradient(ctx._gst) or _fg2
                            except Exception:
                                pass
                            if isinstance(_fg2, dict) and str(_fg2.get("type")) == _gtype:
                                _edit_strokes.append(ctx._gsi)
                    if not _edit_strokes:
                        _edit_strokes = [_g_primary]
                    ctx.gradient_drag = {
                        "handle": _ghit,
                        "stroke_is": _edit_strokes,
                        "grad_type": _gtype,
                        "primary_i": _g_primary,
                        "bbox": (_ginfo or {}).get("bbox"),
                    }
                    dm = getattr(ctx, 'drag_manager', None)
                    if dm is not None:
                        from controllers.drag.gradient_session import GradientDragSession
                        dm.begin(GradientDragSession(), ctx, event)
                    ctx.handled = True
        if ctx.bb:
            eff_pivot = ctx.pivot_pos if ctx.pivot_pos is not None else (ctx.bb["cx"], ctx.bb["cy"])
            # hit pivot marker first (draggable rotation/scale center)
            if not ctx.handled and math.hypot(ctx.cpos[0] - eff_pivot[0], ctx.cpos[1] - eff_pivot[1]) <= 10.0:
                ctx.pivot_drag = {"start": ctx.cpos, "start_pivot": eff_pivot}
                dm = getattr(ctx, 'drag_manager', None)
                if dm is not None:
                    from controllers.drag.pivot_session import PivotDragSession
                    dm.begin(PivotDragSession(), ctx, event)
                ctx.handled = True
            if not ctx.handled:
                ctx.h = hit_test_bbox_handle(ctx.bb, ctx.cpos, mode=ctx.transform_handle_mode)
                if ctx.h is not None:
                    ctx.cx, ctx.cy = eff_pivot
                    ctx.push_undo()
                    ctx.start_strokes = {ctx.i: copy.deepcopy(ctx.strokes[ctx.i]) for ctx.i in sorted(ctx.selected_strokes) if 0 <= ctx.i < len(ctx.strokes)}
                    ctx.transform_drag = {
                        "handle": ctx.h,
                        "start_mouse": ctx.cpos,
                        "start_strokes": ctx.start_strokes,
                        "center": (ctx.cx, ctx.cy),
                        "start_bbox": ctx.bb,
                        "mode": ctx.transform_handle_mode,
                    }
                    dm = getattr(ctx, 'drag_manager', None)
                    if dm is not None:
                        from controllers.drag.transform_session import TransformDragSession
                        dm.begin(TransformDragSession(), ctx, event)
                    ctx.handled = True
                elif point_in_bbox(ctx.bb, ctx.cpos):
                    # click on selected body: move on drag, toggle scale/rotate mode on click-without-drag
                    ctx.pending_transform_toggle = {
                        "start": ctx.cpos,
                        "moved": False,
                        "primed": True,
                    }
                    ctx.handled = True
        elif not ctx.handled and hit_test_stroke(ctx.cpos, ctx.strokes) in ctx.selected_strokes:
            ctx.pending_transform_toggle = {"start": ctx.cpos, "moved": False, "primed": True}
            ctx.handled = True
    if not ctx.handled:
        hit = hit_test_stroke(ctx.cpos, ctx.strokes)
        if hit is not None:
            _gid = group_id_of(ctx.strokes[hit]) if 0 <= hit < len(ctx.strokes) else None
            _members = set(group_members(ctx.strokes, _gid)) if _gid else {hit}
            if ctx.shift:
                if hit in ctx.selected_strokes:
                    ctx.selected_strokes -= _members
                else:
                    ctx.selected_strokes |= _members
                ctx.drag_last = None
            else:
                ctx.selected_strokes = set(_members)
            if ctx.selected_strokes:
                ctx.primary_i = sorted(ctx.selected_strokes)[0]
                if 0 <= ctx.primary_i < len(ctx.strokes):
                    ctx.width_slider.value = int(round(ctx.strokes[ctx.primary_i].get("stroke_width", 3)))
                # allow immediate drag-move of newly selected (no toggle)
                ctx.drag_last = ctx.cpos
            else:
                ctx.drag_last = None
        else:
            # start marquee selection on empty area
            ctx.marquee_select = {"start": ctx.cpos, "current": ctx.cpos, "add": ctx.shift}
            dm = getattr(ctx, 'drag_manager', None)
            if dm is not None:
                from controllers.drag.marquee_session import MarqueeDragSession
                dm.begin(MarqueeDragSession(), ctx, event)
            ctx.drag_last = None
    return 'handled'
