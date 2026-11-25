"""Color/fill panel click dispatch.

Core is a typed contract; ``_handle_panel_click_b`` is a compat wrapper that
supports both typed dispatch contexts and legacy plain ctx callers.
"""


def color_panel_hit(tools, document, selection, ui, state, event, ctx, handlers):
    """Run wave/effect panel handlers in priority order."""
    for handler in handlers:
        if handler(ctx, event):
            return "handled"
    return None


def _handle_panel_click_b(ctx, event):
    """Compat wrapper: extract typed substates from the dispatch context."""
    app_state = getattr(ctx, "_app_state", None)
    if app_state is None:
        from controllers.app_state import AppState
        app_state = AppState()
        app_state.tools.tool_mode = getattr(ctx, "tool_mode", "draw")
        app_state.selection.selected_strokes = getattr(ctx, "selected_strokes", set())
        app_state.selection.selection_submode = getattr(ctx, "selection_submode", "transform")
        app_state.document.strokes = getattr(ctx, "strokes", [])
        app_state.ui.color_target = getattr(ctx, "color_target", "stroke")
    from controllers.panel.effects_wave import (
        effects_wave_hit,
        handle_wave_effects_primary,
        handle_wave_effects_secondary,
        handle_wave_effects_tertiary,
    )
    effects_wave_hit(
        app_state.tools, app_state.document, app_state.selection, app_state.ui,
        ctx.state, event, ctx,
        (handle_wave_effects_primary, handle_wave_effects_secondary,
         handle_wave_effects_tertiary),
    )
