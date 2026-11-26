"""guide cut motion."""
import copy, math, pygame
import config as cfg
from models.interaction import scrub_value
from views.widgets import drag_modifiers


def _scrub_opacity(ctx, key, bar, fallback_value, event):
    """Scrub an opacity field from its click snapshot (legacy fallback included)."""
    start = ctx.state.get(key)
    if not isinstance(start, (tuple, list)) or len(start) != 2:
        start = (bar.x, ctx.clamp(fallback_value, 0.0, 1.0))
        ctx.state[key] = start
    fine, coarse = drag_modifiers(event)
    return scrub_value(start[1], 0.0, 1.0, bar.w,
                       start[0], event.pos[0], fine=fine, coarse=coarse)


def mm_part1(ctx, event):
    if ctx.guide_drag is not None:
        _gp = ctx.to_canvas(event.pos)
        _gval = _gp[0] if ctx.guide_drag.get("axis") == "x" else _gp[1]
        ctx.guides = ctx.move_guide(ctx.guides, ctx.guide_drag.get("index", 0), _gval)
        return True
    if ctx.cutting:
        cpos = ctx.clamp_to_canvas(event.pos)
        if not ctx.cut_points or math.hypot(cpos[0] - ctx.cut_points[-1][0],
                                        cpos[1] - ctx.cut_points[-1][1]) >= 1.0:
            ctx.cut_points.append(cpos)
        return True
    if ctx.pan_drag is not None:
        sm = ctx.pan_drag["start_mouse"]; sp = ctx.pan_drag["start_pan"]
        cfg.VIEW_PAN_X = sp[0] + (event.pos[0] - sm[0])
        cfg.VIEW_PAN_Y = sp[1] + (event.pos[1] - sm[1])
        return True
    if ctx.pivot_drag is not None and pygame.mouse.get_pressed()[0]:
        cpos = ctx.clamp_to_canvas(event.pos)
        sp0 = ctx.pivot_drag.get("start_pivot", cpos)
        sm = ctx.pivot_drag.get("start", cpos)
        ctx.pivot_pos = (sp0[0] + cpos[0] - sm[0], sp0[1] + cpos[1] - sm[1])
        return True
    if ctx.ref_opacity_drag and ctx.reference_image is not None:
        bar = ctx.state.get("ref_opacity_rect", pygame.Rect(0,0,0,0))
        if bar.w > 0:
            ctx.reference_image["opacity"] = _scrub_opacity(
                ctx, "ref_opacity_drag_start", bar,
                float(ctx.reference_image.get("opacity", 0.5)), event)
    elif ctx.obj_opacity_drag and ctx.selected_strokes:
        bar = ctx.state.get("obj_opacity_rect", pygame.Rect(0,0,0,0))
        if bar.w > 0:
            opacity = _scrub_opacity(ctx, "obj_opacity_drag_start", bar, 0.5, event)
            for si in sorted(ctx.selected_strokes):
                if 0 <= si < len(ctx.strokes) and isinstance(ctx.strokes[si], dict):
                    ctx.strokes[si] = ctx.set_appearance(ctx.strokes[si], opacity=opacity)
    elif ctx.bucket_picker_drag is not None:
        if ctx.bucket_picker_drag == "sv":
            ctx.bucket_pick(ctx.state.get("bucket_sv_rect", pygame.Rect(0,0,0,0)), event.pos, "sv")
        else:
            ctx.bucket_pick(ctx.state.get("bucket_hue_rect", pygame.Rect(0,0,0,0)), event.pos, "hue")
    elif ctx.ref_drag is not None and ctx.reference_image is not None and (pygame.mouse.get_pressed()[0]):
        cpos = ctx.clamp_to_canvas(event.pos)
        off = ctx.ref_drag.get("offset", (0, 0))
        ctx.reference_image["x"] = cpos[0] - off[0]
        ctx.reference_image["y"] = cpos[1] - off[1]
    return False
