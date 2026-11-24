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
        # Own the full UI-drag cleanup: mirror cleared flags into state, then
        # clear the ctx flags (idempotent, safe to call from mouse-up cleanup
        # even when DragManager never began a session this frame).
        for k in ('obj_opacity_drag', 'picker_drag_sv', 'picker_drag_hue',
                  'picker_drag_alpha', 'fill_stop_pos_drag'):
            if hasattr(ctx, k):
                ctx.state[k] = False
        for k in _UI_DRAG_FLAGS:
            if not hasattr(ctx, k):
                continue
            if k == 'bucket_picker_drag':
                ctx.bucket_picker_drag = None
            elif k == 'wave_slider_drag':
                ctx.wave_slider_drag = None
            else:
                setattr(ctx, k, False)
        return True