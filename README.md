# Cairo Vector Drawing (Strokes to Bézier Curves)

A small vector drawing program that captures freehand mouse strokes and converts them into cubic Bézier curves rendered with [Cairo 2D](https://www.cairographics.org/).

## How it works

1. **Capture**: While you drag the left mouse button, the app samples points along your stroke.
2. **Snap & merge**: Hover near either endpoint of an existing (open) stroke to see a circle indicator. Starting or ending a stroke on that indicator snaps it to the endpoint; connected strokes are automatically **merged into a continuous path** (edges merged). You can also snap a stroke's end to its own start to close a shape; once a shape is closed, its endpoints are no longer offered as snap targets so no more lines can be added to it.
3. **Simplify**: On release, the stroke is simplified with the Ramer–Douglas–Peucker algorithm to remove redundant points while preserving shape.
4. **Fit to Bézier**: The simplified polyline is converted into a sequence of cubic Bézier segments (Catmull–Rom to Bézier conversion).
5. **Render**: All fitted curves are drawn with Cairo (`cairo.Context.curve_to`). Control points/handles are shown lightly so you can see the resulting Bézier structure.

## Requirements

- Python 3.10+
- [pycairo](https://pycairo.readthedocs.io/) (Cairo bindings; Windows wheels typically bundle Cairo) **or** [cairocffi](https://cairocffi.readthedocs.io/) with native Cairo installed
- [pygame](https://www.pygame.org/) (window/input/display)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** The app prefers `pycairo` and falls back to `cairocffi`. If you use `cairocffi`, the native Cairo 2D library must be installed and discoverable (e.g. `libcairo-2.dll` on Windows). If you see `OSError: no library called "cairo-2" was found`, install `pycairo` (`pip install pycairo`) which includes Cairo on common Windows setups.

## Run

```bash
python app.py
```

## Controls

- **Top bar**: **File** menu on the left.
- **Left toolbar**: simple icon tools to switch between **Draw** and **Edit** modes.
- **Canvas**: middle area where you draw and edit (Cairo 2D rendering).
- **Bottom toolbar**: shape tools — freehand/curve, line, rectangle, square, ellipse, circle, triangle — followed, after a divider, by **Eraser**, **Split Curve**, and **Fill (bucket)**. Picking any of them switches to Draw mode. Shapes are fitted to your sketch: trace a rough (even tilted) outline and you get a **perfect** rect/square/ellipse/triangle in that orientation and size (sketches within ~3° of an axis stay axis-aligned). **Right-click any button** to open that tool's options in a popup above the button (Freehand: fitting Fit/C-R/Single, points/curve, boost; Line: 45° constrain, arrowhead; Rect/Square: corner radius; Ellipse/Circle: segments; Triangle: isosceles/right/equilateral; Fill: fill color swatches; Split: gap stepper; Eraser/Fill: snapping; plus a shared Snapping toggle).
- **Right panel**: the **Pen / Eraser / Fill / Split curve** tool buttons sit at the top in a 2×2 grid under a **Tool options** heading; the options below are context-sensitive to the active tool (Pen: points/curve, boost limit, tracing algorithm; Fill: fill color — preview + hex, HSV square and hue bar, preset swatches; Eraser: a short usage hint; Split curve: a split hint plus a **Gap** slider), followed by the snapping toggle and reference-image controls. Click the small chevron tab on the panel's left edge to **collapse the sidebar**; the canvas then grows to the window edge, and clicking the tab again (now at the window's right edge) restores it.

### Draw mode
- **Left mouse drag (canvas)**: draw a stroke
- **Shape tools (Rect/Square/Ellipse/Triangle)**: sketch the shape's outline; it snaps to a perfect shape that keeps your sketch's rotation and size (e.g. sketch a tilted rectangle and you get a clean tilted rectangle). Straight corner-to-corner drags still produce axis-aligned boxes.
- **Hover endpoints**: circle indicator shows snap targets; start/end can snap to open endpoints (and a stroke can snap its end to its own start to close)
- **Connected strokes auto-merge** into continuous paths; once a shape is closed, no more lines can be added/snapped to it. Razor-split pieces that were separated by a **Gap** are exempt: they stay separate.
- **Panel**: **Points / curve** slider (**2–5** default, 4), **Boost limit** to allow above 5 (up to 100), Undo/Clear
- **Fill (bucket)**: click inside an enclosed region to create an opaque vector fill. Pick its color in the panel's **Fill color** section (preview + hex, HSV square and hue bar, preset swatches) or from the right-click Fill popup swatches.
- **Split Curve (razor)**: pick it on the bottom bar (or press `C`) and **drag across curves**. Every curve the drag crosses gets a **node** at the crossing and becomes **two separate curves** (components of the same stroke). The halves **stay connected** — they share the node, and if the stroke was joined to other curves they stay joined — but each half can be picked individually in **Curve** mode. Use the **Gap** slider in the panel (or the gap stepper in the split tool's right-click popup) to trim a visible gap (0–20 px) when you want the pieces fully separated; separated pieces never auto-merge back. Works on open curves and closed shapes; undo restores the original stroke.
- **Curve-mode split**: in Edit mode's **Curve** submode, select a curve and use **Split curve** beside **Redraw** to split just that curve into two selectable halves; the toggle turns off after one swipe so you can click a half right away. The same **Gap** slider appears while it is active.

### Edit mode
- **Click stroke**: select it (highlighted) and reveal editable Bézier anchors/handles (pen-tool-style)
- **Drag anchors (circles)**: move curve endpoints/join points; handles attached to the anchor move with it, and joined segments stay connected
- **Drag handles (squares)**: adjust curve shape. Handles mirror at **smooth/symmetric** joins inside a stroke; joins where two drawn strokes were **merged/closed** are **corners** with independent handles
- **Drag path (not on a point)**: move the whole selected stroke
- **Click empty canvas**: deselect
- **Delete / Backspace**: remove selected stroke
- **Panel**: **Fill** and **Stroke** options for the selected stroke (stroke color, stroke width, fill color/none), plus Undo/Clear
- Drawing and snapping are disabled in Edit mode

- **Keyboard shortcuts**: `V` select, `B` pen, `E` eraser, `F` fill (bucket), `C` split curve (razor), `S` toggle snapping, `[` / `-` and `]` / `+` adjust points per curve, **Ctrl+Z** undo, **Esc** quit

The **points per curve** setting limits how many simplified points from each stroke are used when fitting Bézier segments (lower = simpler curves, higher = more detail).

## Files
- `app.py` — root launcher/shim (loads the core app from `src/`)
- `src/` — core application (MVC)
  - `app.py` — facade/entry point (re-exports all names for compatibility)
  - `bezier.py` — stroke simplification (RDP) and conversion to cubic Bézier segments
  - `config.py` — layout and theme constants
  - `models/` — `geometry.py`, `strokes.py`, `waves.py`, `interaction.py` (data & pure computation)
  - `views/` — `canvas.py`, `panel.py`, `toolbar.py`, `widgets.py`, `dialogs.py` (rendering/UI)
  - `controllers/` — `app_controller.py`, `coordinates.py` (event loop & app state)
- `tests/` — unit and end-to-end tests
- `docs/` — `ARCHITECTURE.md` (MVC structure overview)
- `requirements.txt` — Python dependencies
