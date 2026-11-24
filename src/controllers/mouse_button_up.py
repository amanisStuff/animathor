"""Mouse button up dispatch split semantically by commit responsibility."""

from controllers.commit.guide_commit import commit_guide_drag
from controllers.commit.bezier_pen_commit import commit_bezier_pen_mouseup
from controllers.commit.cutter_commit import commit_cutter
from controllers.commit.selection_commit import commit_transform_toggle_and_marquee
from controllers.commit.redraw_commit import commit_redraw_curve
from controllers.commit.draw_commit import commit_draw


def _cleanup_mouseup(ctx):
    ctx.drag_last = None; ctx.selected_point = None; ctx.transform_drag = None; ctx.gradient_drag = None; ctx.pivot_drag = None
    ctx.picker_drag_sv = False; ctx.picker_drag_hue = False; ctx.picker_drag_alpha = False; ctx.ref_opacity_drag = False; ctx.fill_stop_pos_drag = False
    ctx.obj_opacity_drag = False
    ctx.state["obj_opacity_drag"] = False
    ctx.bucket_picker_drag = None
    ctx.wave_slider_drag = None
    ctx.wave_custom_drag = None
    ctx.state["wave_custom_drag"] = None
    ctx.state["picker_drag_sv"] = False; ctx.state["picker_drag_hue"] = False; ctx.state["picker_drag_alpha"] = False; ctx.state["fill_stop_pos_drag"] = False
    ctx.ref_drag = None
    ctx.max_points_per_curve = ctx.slider.value


def handle_mousebuttonup1(ctx, event=None):
    """Dispatch MOUSEBUTTONUP to semantic commit handlers, then cleanup."""
    guide_result = commit_guide_drag(ctx, event)
    if guide_result == 'continue':
        return 'continue'
    ctx.smart_snap_guides = []

    for handler in (commit_bezier_pen_mouseup, commit_cutter):
        result = handler(ctx, event)
        if result == 'continue':
            return 'continue'

    # Selection/transform/marquee commits may handle marquee; others fall through.
    sel_result = commit_transform_toggle_and_marquee(ctx, event)
    if sel_result != 'handled':
        for handler in (commit_redraw_curve, commit_draw):
            result = handler(ctx, event)
            if result == 'handled':
                break

    _cleanup_mouseup(ctx)
    return None
