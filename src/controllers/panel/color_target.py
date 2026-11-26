"""Color-target hit dispatch for the panel fill/color domain.

Core logic is a typed contract over AppState substates; ``_b3_color`` is a
compat wrapper for the extracted ctx-based caller.
"""


def color_target_hit(ui, selection, document, state, event, was_hit,
                     ctx, stroke_components, handlers):
    """Dispatch downstream color handlers when a stroke selection is active."""
    if (not was_hit and selection.selected_strokes
            and (selection.selection_submode == "transform"
                 or (selection.selection_submode == "curve" and selection.selected_curve))):
        comp_target = None
        if (selection.selection_submode == "curve" and selection.selected_curve
                and len(selection.selected_strokes) == 1
                and selection.selected_curve[0] in selection.selected_strokes):
            comp_target = selection.selected_curve
        if comp_target is not None:
            ui.color_target = "stroke"
            state["color_target"] = "stroke"
        if not (selection.selection_submode == "curve" and comp_target is None):
            sel_list = sorted(selection.selected_strokes)
            primary_i = sel_list[0]
            primary_obj = document.strokes[primary_i] if 0 <= primary_i < len(document.strokes) else None

            def set_comp_stroke_color(si, ci, rgb, alpha):
                comps = stroke_components(document.strokes[si])
                if 0 <= ci < len(comps):
                    comps[ci]["stroke_color"] = (rgb[0], rgb[1], rgb[2], alpha)
                    document.strokes[si]["components"] = comps

            # Downstream fill-picker handlers still take a ctx; expose the
            # typed state plus this domain's bridge attrs through the live
            # typed dispatch context supplied by the caller.
            ctx._c_comp_style_target = comp_target
            ctx._c_sel_list = sel_list
            ctx._c_primary_i = primary_i
            ctx._c_primary_obj = primary_obj
            ctx._c_set_comp_stroke_color = set_comp_stroke_color
            ctx.color_target = ui.color_target
            if primary_obj is not None:
                from controllers.panel.fill_picker import fill_picker_hit
                # ``tools`` is part of the typed panel boundary even though the
                # current fill-picker handlers only consume it through ctx.
                tools = getattr(ctx, "tools", None)
                if tools is None:
                    app_state = getattr(ctx, "_app_state", None)
                    tools = getattr(app_state, "tools", None)
                fill_picker_hit(
                    tools, document, selection, ui, state, event, ctx, handlers,
                )
    return was_hit


def _b3_color(ctx, event, _w_hit):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        from controllers.app_state import AppState
        app_state = AppState()
        app_state.selection.selection_submode = getattr(ctx, "selection_submode", "transform")
        app_state.selection.selected_strokes = getattr(ctx, "selected_strokes", set())
        app_state.selection.selected_curve = getattr(ctx, "selected_curve", None)
        app_state.document.strokes = getattr(ctx, "strokes", [])
        app_state.ui.color_target = getattr(ctx, "color_target", "stroke")
    from controllers.panel.fill_picker import (
        handle_color_targets, handle_fill_stops, handle_color_picker,
    )
    return color_target_hit(
        app_state.ui, app_state.selection, app_state.document,
        ctx.state, event, _w_hit, ctx, ctx._stroke_components,
        (handle_color_targets, handle_fill_stops, handle_color_picker),
    )
