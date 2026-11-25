"""Gradient stops/tabs panel click dispatch.

Core logic is a typed contract over AppState substates; ``_handle_panel_click_c``
is a compat wrapper for the extracted ctx-based caller.
"""


def gradient_panel_hit(tools, selection, document, ui, state, event, ctx,
                       stroke_components, handlers):
    """Dispatch gradient/fill handlers for an active stroke selection."""
    if (tools.tool_mode == "selection" and selection.selected_strokes
            and selection.selection_submode == "transform"):
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

            ctx._c_comp_style_target = comp_target
            ctx._c_sel_list = sel_list
            ctx._c_primary_i = primary_i
            ctx._c_primary_obj = primary_obj
            ctx._c_set_comp_stroke_color = set_comp_stroke_color
            ctx.color_target = ui.color_target
            if primary_obj is not None:
                from controllers.panel.fill_picker import fill_picker_hit
                fill_picker_hit(
                    tools, document, selection, ui, state, event, ctx, handlers,
                )
    return None


def _handle_panel_click_c(ctx, event):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        # Legacy ctx callers: project their fields into typed substates.
        from controllers.app_state import AppState
        app_state = AppState()
        app_state.tools.tool_mode = getattr(ctx, "tool_mode", "draw")
        app_state.selection.selection_submode = getattr(ctx, "selection_submode", "transform")
        app_state.selection.selected_strokes = getattr(ctx, "selected_strokes", set())
        app_state.selection.selected_curve = getattr(ctx, "selected_curve", None)
        app_state.document.strokes = getattr(ctx, "strokes", [])
        app_state.ui.color_target = getattr(ctx, "color_target", "stroke")
    from controllers.panel.gradient_stops import (
        gradient_stops_hit,
        handle_fill_tabs_and_type, handle_gradient_stops, handle_fill_picker,
    )
    gradient_stops_hit(
        app_state.tools, app_state.selection, app_state.document, app_state.ui,
        ctx.state, event, ctx,
        (handle_fill_tabs_and_type, handle_gradient_stops, handle_fill_picker),
    )
