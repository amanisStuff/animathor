"""Flat, priority-ordered panel domain dispatch.

Each domain handler checks only its own UI rects and returns ``'continue'`` when
it handled the click (legacy ctx-handler convention) or ``None`` to let the next
domain try. This replaces the quantitative part-number dispatch chain with named
semantic domains while preserving identical behavior (the domain handlers are
the existing semantic entry points until their internals are rewritten).
"""


def sections(ctx, event):
    """Section headers take priority over the controls they contain."""
    from controllers.panel.sections import handle_section_click
    return handle_section_click(ctx, event)


def tool_options(ctx, event):
    """Draw tool options / toolbar area (currently mbd_panel_a)."""
    from controllers.panel.tool_options import _handle_panel_click_a
    return _handle_panel_click_a(ctx, event)


def fill_picker(ctx, event):
    """Fill/stroke/color picker area (currently mbd_panel_b)."""
    from controllers.panel.color_panel import _handle_panel_click_b
    return _handle_panel_click_b(ctx, event)


def gradient_stops(ctx, event):
    """Gradient stops / tabs / picker area (currently mbd_panel_c)."""
    from controllers.panel.gradient_panel import _handle_panel_click_c
    return _handle_panel_click_c(ctx, event)


# Ordered by UI priority: section headers, tool options, color/fill, gradients.
DOMAIN_HANDLERS = (sections, tool_options, fill_picker, gradient_stops)


def handle_panel_click(ctx, event):
    """Dispatch a panel click through the ordered semantic domains."""
    for handler in DOMAIN_HANDLERS:
        result = handler(ctx, event)
        if result == 'continue':
            return 'continue'
        if result == 'handled':
            return None
    return None
