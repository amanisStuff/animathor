"""Wave formula/custom-draw input mode key handling."""

import pygame
from models.waves import _get_distortion_style, _set_distortion_style  # noqa: F401


def handle_wave_keys(ctx, event):
    if (ctx.wave_formula_focus and ctx.tool_mode == "selection"
            and ctx.selection_submode == "curve" and ctx.selected_curve
            and ctx.selected_curve[0] in ctx.selected_strokes):
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                ctx.comps[ctx.comp_i] = dict(ctx.comps[ctx.comp_i])
                ctx.wi = int(ctx.state.get("wave_active_index", 0) or 0)
                ctx.w = _get_distortion_style(ctx.comps[ctx.comp_i], ctx.wi)
                if ctx.w.get("type") == "wave":
                    formula = str(ctx.w.get("formula", "sin(x)") or "")
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        ctx.wave_formula_focus = False
                        ctx.state["wave_formula_focus"] = False
                    elif event.key == pygame.K_BACKSPACE:
                        formula = formula[:-1]
                        ctx.w["formula"] = formula
                        _set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
                    elif event.unicode and event.unicode.isprintable():
                        formula += event.unicode
                        ctx.w["formula"] = formula
                        _set_distortion_style(ctx.comps[ctx.comp_i], ctx.w, ctx.wi)
                        ctx.strokes[ctx.si]["components"] = ctx.comps
                else:
                    ctx.wave_formula_focus = False
                    ctx.state["wave_formula_focus"] = False
        # consume key while editing formula (except we already handled)
        if ctx.wave_formula_focus or event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE) or (event.unicode and event.unicode.isprintable()):
            pass
        return 'continue'

    if (ctx.state.get("wave_custom_draw") and ctx.tool_mode == "selection"
            and ctx.selection_submode == "curve" and ctx.selected_curve
            and ctx.selected_curve[0] in ctx.selected_strokes):
        # custom wave draw mode key handling: Esc/Enter finishes
        ctx.si, ctx.comp_i = ctx.selected_curve
        if 0 <= ctx.si < len(ctx.strokes):
            ctx.comps = ctx._stroke_components(ctx.strokes[ctx.si])
            if 0 <= ctx.comp_i < len(ctx.comps):
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    ctx.state["wave_custom_draw"] = False
                    ctx.state["wave_custom_finished"] = True
        return 'continue'

    return None
