# Cairo Vector Drawing (Strokes to Bézier Curves)

A small vector drawing program that captures freehand mouse strokes and converts them into cubic Bézier curves rendered with [Cairo 2D](https://www.cairographics.org/).

## How it works

1. **Capture**: While you drag the left mouse button, the app samples points along your stroke.
2. **Simplify**: On release, the stroke is simplified with the Ramer–Douglas–Peucker algorithm to remove redundant points while preserving shape.
3. **Fit to Bézier**: The simplified polyline is converted into a sequence of cubic Bézier segments (Catmull–Rom to Bézier conversion).
4. **Render**: All fitted curves are drawn with Cairo (`cairo.Context.curve_to`). Control points/handles are shown lightly so you can see the resulting Bézier structure.

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

- **Left mouse drag (canvas)**: draw a stroke
- **Right-side GUI panel**:
  - **Max points / curve** slider and `-` / `+` buttons to set the curve point limit (2–500)
  - **Undo** and **Clear** buttons
  - Live stroke count and backend info
- **Keyboard shortcuts**:
  - **`[` / `-`**: decrease max points per curve
  - **`]` / `+`**: increase max points per curve
  - **Ctrl+Z**: undo last stroke
  - **C**: clear canvas
  - **Esc**: quit

The **max points per curve** setting limits how many simplified points from each stroke are used when fitting Bézier segments (lower = simpler curves, higher = more detail).

## Files

- `app.py` — pygame UI, Cairo rendering, and input handling
- `bezier.py` — stroke simplification (RDP) and conversion to cubic Bézier segments
- `requirements.txt` — Python dependencies
