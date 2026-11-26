# Animathor Style Guide

This guide is the contract for UI chrome: the properties panel, toolbars,
menus, popovers, dropdowns and dialogs. Canvas artwork is not chrome and is
outside this rule.

## Mandatory spacing rule

> **Every independent UI element must have at least 8px of clear space between
> it and every other independent UI element.**

Use `config.MIN_ELEMENT_SPACING` (currently `8`) for every inter-element gap.
Do not write literal `2`, `4` or `6` gaps between buttons, swatches, steppers,
rows, cards, sliders or panels. Small tokens such as `SPACE_XS`/`SPACE_SM` are
for padding *inside* one element (label inset, icon inset, card padding), not
for separating two elements.

### What counts as an element

- A button, toggle, swatch, slider track/hit area, input, tab, card or dropdown
  item with its own hit rectangle.
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

## Enforcement

- `tests/test_ui_spacing.py` unit-tests the validator and renders every panel
  state, asserting zero spacing violations.
- `tests/test_panel_control_overlaps.py` guards against overlapping draws.
- Run `python -m unittest discover -s tests -t .` before finishing UI work.
