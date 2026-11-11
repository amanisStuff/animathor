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

- **Left toolbar**: simple icon tools to switch between **Draw** and **Edit** modes.
- **Canvas**: middle area where you draw and edit (Cairo 2D rendering).
- **Right panel**: context-sensitive controls for the active tool.

### Draw mode
- **Left mouse drag (canvas)**: draw a stroke
- **Hover endpoints**: circle indicator shows snap targets; start/end can snap to open endpoints (and a stroke can snap its end to its own start to close)
- **Connected strokes auto-merge** into continuous paths; once a shape is closed, no more lines can be added/snapped to it
- **Panel**: **Points / curve** slider (**2–5** default, 4), **Boost limit** to allow above 5 (up to 100), Undo/Clear

### Edit mode
- **Click stroke**: select it (highlighted) and reveal editable Bézier anchors/handles (pen-tool-style)
- **Drag anchors (circles)**: move curve endpoints/join points; handles attached to the anchor move with it, and joined segments stay connected
- **Drag handles (squares)**: adjust curve shape. Handles mirror at **smooth/symmetric** joins inside a stroke; joins where two drawn strokes were **merged/closed** are **corners** with independent handles
- **Drag path (not on a point)**: move the whole selected stroke
- **Click empty canvas**: deselect
- **Delete / Backspace**: remove selected stroke
- **Panel**: **Fill** and **Stroke** options for the selected stroke (stroke color, stroke width, fill color/none), plus Undo/Clear
- Drawing and snapping are disabled in Edit mode

- **Keyboard shortcuts**: `[` / `-` and `]` / `+` adjust points per curve, **Ctrl+Z** undo, **C** clear, **Esc** quit

The **points per curve** setting limits how many simplified points from each stroke are used when fitting Bézier segments (lower = simpler curves, higher = more detail).

## Files

- `app.py` — pygame UI, Cairo rendering, and input handling
- `bezier.py` — stroke simplification (RDP) and conversion to cubic Bézier segments
- `requirements.txt` — Python dependencies
