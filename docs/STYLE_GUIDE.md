# Animathor Style Guide

This guide is the contract for UI chrome: the properties panel, toolbars,
menus, popovers, dropdowns and dialogs. Canvas artwork is not chrome and is
outside this rule.

## Mandatory spacing rule

> **Every independent UI element must have at least 8px of clear space between
> it and every other independent UI element.**

Use `config.MIN_ELEMENT_SPACING` (currently `8`) for every inter-element gap.
Do not write literal `2`, `4` or `6` gaps between buttons, swatches, steppers,
rows, cards, draggable numeric fields or panels. Small tokens such as
`SPACE_XS`/`SPACE_SM` are for padding *inside* one element (label inset, icon
inset, card padding), not for separating two elements.

### What counts as an element

- A button, toggle, swatch, draggable numeric field, input, tab, card or
  dropdown item with its own hit rectangle.
- A group of controls that is presented as a single composite control (for
  example a `< value >` stepper, a marker row with inline toggle/remove, or a
  single row in a menu/list) counts as one element. Its children may sit inside
  it; the composite itself must keep 8px from other composites.

### How the gap is measured

For two axis-aligned rectangles `a` and `b`:

- horizontal gap: `max(0, b.left - a.right, a.left - b.right)`
- vertical gap: `max(0, b.top - a.bottom, a.top - b.bottom)`
- the pair passes when the greater of those two gaps is at least 8px.
- touching or overlapping rectangles fail.
- a child rectangle fully contained by its parent is not a separate element.

The validator `panel_rects.spacing_violations()` implements exactly this
measurement. `panel_rects.panel_spacing_violations(state)` applies it to every
published `*_rect` / `*_rects` hit area in a rendered view state.

### Allowed exceptions

- Decorative strokes, icons, labels and textures drawn inside one button or
  card.
- Children of a composite control (stepper arrows around their value, toggle
  and remove buttons inside a list row).
- Rows of a single menu/list container, where the container is the element.
- Canvas content and editor overlays.

## Layout requirements

1. Import and use `MIN_ELEMENT_SPACING` from `config` for all inter-element
   gaps, including row pitch (`control_h + MIN_ELEMENT_SPACING`) and wrapping
   grids (`step = size + MIN_ELEMENT_SPACING`).
2. When a control is hidden, publish a zero-sized rect (or empty collection)
   instead of leaving a stale visible rect.
3. When adding or moving a control, run the spacing tests and fix violations
   in the same change. Do not lower the minimum or add an exception for a new
   control.
4. Prefer wrapping to a new row over compressing a gap. Never shrink a gap to
   make more swatches fit; the panel scrolls.

## Draggable numeric fields

Numeric parameters use `DragField` / `draw_drag_field()` (`src/views/widgets.py`)
instead of a track-and-knob slider. The whole field is the hit target: pressing
starts a scrub from the *current* value (a click never jumps), and horizontal
motion maps the drag distance across the field width to the parameter range.
`Ctrl`/`Cmd` is ten times finer, `Shift` is five times coarser; integer fields
quantise to whole steps. `scrub_value()` in `src/models/interaction.py` owns the
shared math, and `views.widgets.drag_modifiers()` reads the modifier flags.

Double-clicking a field opens an inline numeric editor
(`src/controllers/numeric_field_edit.py`): the first click still scrubs, while a
second click on the same field within 400 ms and 8 px enters text mode. Typing a
digit, `.` or `-` replaces the current value; `Backspace` edits the buffer,
`Enter` commits (clamped to the field range and stepped for integer fields) and
`Escape` cancels. Opacity fields accept percentages, so `35` means `0.35`.
Clicking another control commits first; the editor is modal, so global shortcuts
never fire while typing. The caret overlay is clipped to the published field
rect and adds no new hit target.

The legacy `Slider` constructor remains as a `DragField` subclass so existing
callers and tests keep working; `slider.track` is an alias of `slider.rect`.
Fields are `DRAG_FIELD_H` tall and publish their real rectangle, so the 8px
contract is measured against the field itself rather than an inflated hit box.

## Collapsible panel sections

The right properties panel is a vertical stack of clickable section headers,
not one continuous wall of controls. Section state lives in
`state["panel_sections"]` as `key -> expanded bool`; a missing key falls back to
`views.panel_sections.DEFAULT_OPEN`, so callers that build their own state dict
keep working. Header hit rects are published in `state["panel_section_rects"]`
and are validated by the shared spacing contract like any other element.

Defaults keep the two priority workflows immediately usable:

- **Open:** `selection_transform`, `selection_text`, `selection_color`,
  `curve_styles`.
- **Closed:** `selection_arrange`, `selection_stroke`, `selection_appearance`,
  `curve_color`, `draw_reference`, `help`.

`draw_section_header()` returns `(next_y, expanded)` and advances `y` by the
header height plus `MIN_ELEMENT_SPACING`. A collapsed section must not draw its
body and must clear every rect the body can publish (use `clear_section()` /
`clear_rects()` with the registered keys), so no stale hit area survives a
frame. Section clicks are handled first in
`controllers/panel/dispatch.py` by `controllers/panel/sections.py`, before any
control inside a section can consume them.

## Enforcement

- `tests/test_numeric_field_edit.py` covers double-click detection, typed
  buffers, commit/cancel, clamping, percent scaling and the caret overlay.
- `tests/test_ui_spacing.py` unit-tests the validator and renders every panel
  state, asserting zero spacing violations.
- `tests/test_panel_sections.py` covers section defaults, toggling, header-click
  priority, rect clearing/restoration, reduced content height and spacing in
  collapsed/expanded states.
- `tests/test_panel_control_overlaps.py` guards against overlapping draws.
- Run `python -m unittest discover -s tests -t .` before finishing UI work.
