"""Generic UI drag session (pickers, sliders, opacity, etc.)."""

from controllers.drag.session import DragSession

_UI_DRAG_FLAGS = (
    'ref_opacity_drag', 'obj_opacity_drag', 'bucket_picker_drag',
    'wave_slider_drag', 'picker_drag_sv', 'picker_drag_hue',
    'picker_drag_alpha', 'fill_stop_pos_drag',
)


def ui_drag_active(ctx):
    return any(bool(getattr(ctx, k, False)) for k in _UI_DRAG_FLAGS)


class UiDragSession(DragSession):
    name = "ui"

    def begin(self, ctx, event):
        self._active = ui_drag_active(ctx)

    def move(self, ctx, event):
        if not ui_drag_active(ctx):
            return False
        # Delegate to existing mouse motion parts that own UI drag logic.
        from controllers.mouse_motion_parts import mm_part1, mm_part2
        if mm_part1(ctx, event):
            return True
        if mm_part2(ctx, event):
            return True
        return False

    def end(self, ctx, event):
        # Cleanup is handled by mouse_button_up/_cleanup_mouseup; keep idempotent.
        for k in _UI_DRAG_FLAGS:
            if hasattr(ctx, k):
                if k == 'bucket_picker_drag':
                    ctx.bucket_picker_drag = None
                elif k == 'wave_slider_drag':
                    ctx.wave_slider_drag = None
                else:
                    setattr(ctx, k, False)
        ctx.state["obj_opacity_drag"] = bool(getattr(ctx, 'obj_opacity_drag', False))
        ctx.state["picker_drag_sv"] = bool(getattr(ctx, 'picker_drag_sv', False))
        ctx.state["picker_drag_hue"] = bool(getattr(ctx, 'picker_drag_hue', False))
        ctx.state["picker_drag_alpha"] = bool(getattr(ctx, 'picker_drag_alpha', False))
        ctx.state["fill_stop_pos_drag"] = bool(getattr(ctx, 'fill_stop_pos_drag', False))
        return True