"""Menu popup click handling."""
import copy, math, pygame
import config as cfg
from models import add_guide, hit_guide, mirror_stroke, set_marker  # noqa: F401
from views import TRACE_ALGORITHMS, TRIANGLE_VARIANTS, export_scene_image, pick_export_image_path  # noqa: F401
from controllers.mouse_button_down_panel import _handle_panel_click
from controllers.mouse_button_down_canvas import _handle_canvas_click









def _handle_menu_bar_click(ctx, event):
    handled = False
    if event.pos[1] < ctx.TOP_BAR_H:
        ctx.shape_menu_key = None
        # Workspace switcher (Draw <-> Library) lives in the top bar.
        if (isinstance(ctx.state.get("workspace_rect"), pygame.Rect)
                and ctx.state["workspace_rect"].collidepoint(event.pos)):
            ctx.workspace = "library" if ctx.workspace == "draw" else "draw"
            ctx.state["workspace"] = ctx.workspace
            ctx.menu_open = None
            handled = True
        hit = next((ctx.k for ctx.k, ctx.r in ctx.menu_bar_rects.items()
                    if ctx.r.collidepoint(event.pos)), None)
        ctx.menu_open = None if hit is None or ctx.menu_open == hit else hit
        ctx.help_open = False
        handled = True
    elif ctx.menu_open is not None:
        hit = next((ctx.k for ctx.k, ctx.r in ctx.menu_item_rects.items()
                    if ctx.r.collidepoint(event.pos)), None)
        if hit is not None:
            ctx.run_menu_action(hit)
        # A click outside the dropdown only dismisses it.
        ctx.menu_open = None
        handled = True
    return handled


def _handle_marker_dropdown_click(ctx, event):
    handled = False
    if ctx.marker_dropdown is not None:
        _mk_items = ctx.state.get("marker_dropdown_item_rects", {}) or {}
        _mk_hit = next((ctx.k for ctx.k, ctx.r in _mk_items.items()
                        if isinstance(ctx.r, pygame.Rect) and ctx.r.collidepoint(event.pos)), None)
        _mk_anchor = ctx.state.get("marker_start_rect" if ctx.marker_dropdown == "start" else "marker_end_rect", pygame.Rect(0, 0, 0, 0))
        if _mk_hit is not None:
            ctx.push_undo()
            for ctx.si in sorted(ctx.selected_strokes):
                if 0 <= ctx.si < len(ctx.strokes) and isinstance(ctx.strokes[ctx.si], dict):
                    ctx.strokes[ctx.si] = set_marker(ctx.strokes[ctx.si], ctx.marker_dropdown, _mk_hit)
            ctx.marker_dropdown = None
            handled = True
        elif ctx.state.get("marker_dropdown_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
            handled = True
        elif isinstance(_mk_anchor, pygame.Rect) and _mk_anchor.collidepoint(event.pos):
            # Let the marker button handler toggle it.
            pass
        else:
            ctx.marker_dropdown = None
        ctx.state["marker_dropdown"] = ctx.marker_dropdown
    return handled


def _handle_shape_menu_click(ctx, event):
    handled = False
    if ctx.shape_menu_key is not None:
        _menu_items = ctx.state.get("shape_menu_item_rects", {})
        _menu_hit = next((ctx.k for ctx.k, ctx.r in _menu_items.items() if ctx.r.collidepoint(event.pos)), None)
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
            handled = True
        elif ctx.state.get("shape_menu_rect", pygame.Rect(0, 0, 0, 0)).collidepoint(event.pos):
            handled = True
        else:
            ctx.shape_menu_key = None
    ctx.state["shape_menu_key"] = ctx.shape_menu_key
    ctx.state["shape_menu_anchor"] = ctx.shape_menu_anchor
    return handled


def _handle_menus(ctx, event):

    for handler in (_handle_menu_bar_click, _handle_marker_dropdown_click,

                    _handle_shape_menu_click):

        if handler(ctx, event):

            return 'continue'

    return None
