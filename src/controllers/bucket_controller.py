"""Controller: bucket/fill color picker helpers (extracted from app_controller for SRP)."""


def pick(ctx, rect, pos, kind):
    if rect.w <= 0 or rect.h <= 0:
        return
    if kind == "sv":
        ctx.bucket_picker_s = ctx.clamp((pos[0] - rect.x) / max(1, rect.w - 1), 0.0, 1.0)
        ctx.bucket_picker_v = ctx.clamp(1.0 - (pos[1] - rect.y) / max(1, rect.h - 1), 0.0, 1.0)
    else:
        ctx.bucket_picker_h = ctx.clamp((pos[0] - rect.x) / max(1, rect.w - 1), 0.0, 1.0) * 360.0
    ctx.bucket_fill_color = ctx.hsv_to_rgb(ctx.bucket_picker_h, ctx.bucket_picker_s, ctx.bucket_picker_v)
    ctx.state["bucket_fill_color"] = ctx.bucket_fill_color
    ctx.state["bucket_picker_h"] = ctx.bucket_picker_h
    ctx.state["bucket_picker_s"] = ctx.bucket_picker_s
    ctx.state["bucket_picker_v"] = ctx.bucket_picker_v
    ctx.state["bucket_picker_drag"] = kind


def set_color(ctx, col):
    ctx.bucket_fill_color = tuple(col)
    ctx.bucket_picker_h, ctx.bucket_picker_s, ctx.bucket_picker_v = ctx.rgb_to_hsv(*ctx.bucket_fill_color)
    ctx.state["bucket_fill_color"] = ctx.bucket_fill_color
    ctx.state["bucket_picker_h"] = ctx.bucket_picker_h
    ctx.state["bucket_picker_s"] = ctx.bucket_picker_s
    ctx.state["bucket_picker_v"] = ctx.bucket_picker_v
