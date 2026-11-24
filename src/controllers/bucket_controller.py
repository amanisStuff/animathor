"""Controller: bucket/fill color picker helpers (extracted from app_controller for SRP).

Accepts a typed ``ToolState`` substate directly (Phase 1: no ctx bag). The
``state`` view dict and pure config helpers are passed explicitly.
"""


def pick(tools, rect, pos, kind, state, clamp, hsv_to_rgb):
    if rect.w <= 0 or rect.h <= 0:
        return
    if kind == "sv":
        tools.bucket_picker_s = clamp((pos[0] - rect.x) / max(1, rect.w - 1), 0.0, 1.0)
        tools.bucket_picker_v = clamp(1.0 - (pos[1] - rect.y) / max(1, rect.h - 1), 0.0, 1.0)
    else:
        tools.bucket_picker_h = clamp((pos[0] - rect.x) / max(1, rect.w - 1), 0.0, 1.0) * 360.0
    tools.bucket_fill_color = hsv_to_rgb(tools.bucket_picker_h, tools.bucket_picker_s, tools.bucket_picker_v)
    state["bucket_fill_color"] = tools.bucket_fill_color
    state["bucket_picker_h"] = tools.bucket_picker_h
    state["bucket_picker_s"] = tools.bucket_picker_s
    state["bucket_picker_v"] = tools.bucket_picker_v
    state["bucket_picker_drag"] = kind


def set_color(tools, col, state, rgb_to_hsv):
    tools.bucket_fill_color = tuple(col)
    tools.bucket_picker_h, tools.bucket_picker_s, tools.bucket_picker_v = rgb_to_hsv(*tools.bucket_fill_color)
    state["bucket_fill_color"] = tools.bucket_fill_color
    state["bucket_picker_h"] = tools.bucket_picker_h
    state["bucket_picker_s"] = tools.bucket_picker_s
    state["bucket_picker_v"] = tools.bucket_picker_v
