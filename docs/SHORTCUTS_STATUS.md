# Keyboard Shortcuts & UI Conventions — Implementation Status

> Audited/updated against `src/controllers/app_controller.py`, `src/views/*.py`, `src/models/*.py`, `src/config.py` (branch `refactor`).  
> **Legend:** **Implemented** = works as expected · **Partial** = exists but differs from convention or is limited · **Not implemented** = missing · **N/A** = not applicable to this app's domain

## 1. Universal System & Editing Shortcuts

| Action | Conventional | Status | Notes in this app |
|---|---|---:|---|
| Undo | `Ctrl+Z` | **Implemented** | `Ctrl+Z` undoes (snapshot-based stack, max 100). Toolbar button with tooltip. |
| Redo | `Ctrl+Shift+Z` / `Ctrl+Y` | **Implemented** | Both `Ctrl+Shift+Z` and `Ctrl+Y` redo. Toolbar button with tooltip. |
| Cut | `Ctrl+X` | **Implemented** | Cuts selected strokes to an internal clipboard (selection mode). |
| Copy | `Ctrl+C` | **Implemented** | Copies selected strokes to an internal clipboard (selection mode). |
| Paste | `Ctrl+V` | **Implemented** | Pastes clipboard strokes offset by (+16,+16) and selects them. |
| Paste in Place / Paste w/o format | `Ctrl+Shift+V` | **Not implemented** / N/A | Paste offsets; no "paste in place" variant. No formatted paste concept. |
| Duplicate | `Ctrl+D` or `Ctrl+J` | **Implemented** | `Ctrl+D` duplicates selected strokes (+16,+16) and selects duplicates. `Ctrl+J` not bound. |
| Select All | `Ctrl+A` | **Implemented** | Selects all strokes. |
| Deselect | `Ctrl+D` / `Esc` | **Implemented** | `Esc` cancels/deselects in priority order (redraw → marquee → drawing → transform/drag/selection → pan) before quitting the app when nothing is active. |
| Save | `Ctrl+S` | **Implemented** | Saves document as XML (`.athors`, default) or JSON (`.anim.json`) via native dialog; remembers path. `src/models/document.py`. |
| Save As | `Ctrl+Shift+S` | **Implemented** | Prompts for a new path and saves (default `.athors`). |
| Export | `Ctrl+Shift+E` | **Implemented** | Exports current canvas view to PNG or SVG (`export_scene_image`; cairo image/SVG surface) via native dialog. |
| Open | `Ctrl+O` | **Implemented** | Opens a saved `.athors` or `.anim.json` document (replaces current strokes, undoable). |
| Group / Ungroup | `Ctrl+G` / `Ctrl+Shift+G` | **Not implemented** | No grouping; strokes merge by endpoint snapping, but no explicit group commands. |
| Command Palette / Search | `Ctrl+K` / `Ctrl+P` | **Not implemented** | No command palette or searchable action menu. |

## 2. Single-Key Tool Selection

| Key | Conventional tool | Status | Notes in this app |
|---|---|---:|---|
| `V` | Move / Selection tool | **Implemented** | `V` switches to **Selection** tool (toolbar tooltip shows shortcut). Former "hold V for straight line while drawing" was remapped to **holding `Shift`** during draw/drag (aligns with constrain convention). |
| `B` | Brush | **Implemented** | `B` switches to **Draw (pen)** tool. |
| `P` | Pen / Vector | **Not implemented** | No `P` shortcut (pen is the default draw subtool, reachable via `B`). |
| `E` | Eraser | **Implemented** | `E` switches to **Draw (eraser)** subtool; Eraser also has a button at the right end of the bottom toolbar. |
| `F` | Fill / Paint bucket | **Implemented (app-specific)** | `F` switches to **Draw (bucket fill)** subtool; Fill also has a button at the right end of the bottom toolbar. Its fill color is chosen in the right panel (preview + hex, HSV square and hue bar, preset swatches) or from the right-click Fill popup swatches; fills are opaque. |
| `T` | Text / Type | **Not implemented** | No text tool. |
| `I` | Eyedropper / Color picker | **Implemented** | Eyedropper is a tool within the **Selection** panel ("Eyedropper - pick style (I)"). Activate via the panel button or `I` (switches to Selection), then click a stroke on the canvas to sample its stroke/fill color, line stroke size, and wave effects and apply them to the current selection (or to the selected curve/component when in Curve submode, with fill applied at stroke level). If nothing is selected, the picked stroke is selected. Pick mode is one-shot (or `Esc` to cancel). |
| `C` | Crop / Cut-Razor | **Implemented (app-specific)** | `C` switches to **Draw (Split Curve / razor)**. Drag across curves to break them: each crossing becomes a **node** and the curve becomes **two separate curves** that stay connected (they share the node, and joined curves stay joined). Each half is its own curve component, selectable individually in Curve mode. The **Gap** slider in the panel (or the gap stepper in the split popup) trims an optional visible gap (0–20 px) and only then fully separates the pieces; separated ends never auto-merge with later strokes. Also available as a bottom-bar button and, in Selection **Curve** submode, as the **Split curve** toggle beside **Redraw** (splits only the selected curve and turns off after one swipe). `Ctrl+C` remains Copy. |
| `R` / `S` / `G` | Rotate / Scale / Grab (3D) | **N/A** (3D) | 2D app: transform handles support move/scale/rotate in selection transform submode (mouse-driven), but no `R`/`S`/`G` hotkeys. `S` toggles **snapping** instead. |
| `[` / `]` | Decrease / Increase brush size (or step) | **Implemented** | `[` / `-` / Numpad `-` decrease max-points/width parameter; `]` / `=` / `+` / Numpad `+` increase (context-dependent slider behavior preserved). |
| Other app-specific keys | — | **Implemented (non-standard)** | `N` — cycle selection submode (transform/nodes/curve). `Delete` / `Backspace` — delete selection. `Space` — temporary pan (see navigation). `S` — toggle snapping. `Shift` (hold while drawing) — constrain to a straight line. |

## 3. Canvas & Viewport Navigation

| Action | Conventional | Status | Notes in this app |
|---|---|---:|---|
| Temporary Pan (Space + drag) | Hold `Space` + LMB drag | **Implemented** | Hold `Space` and drag with LMB to pan; releasing Space ends temporary pan. |
| Middle-click pan | MMB drag | **Implemented** | Middle-mouse drag pans the canvas. |
| Zoom (scroll wheel) | `Ctrl/Cmd` or `Alt` + Wheel → zoom at cursor | **Implemented** | Mouse wheel over the **canvas** zooms toward cursor (0.1×–20×). Mouse wheel over the **right panel** still scrolls the panel. (No modifier required when over canvas.) |
| Zoom in/out steps | `Ctrl/Cmd` + `+` / `-` | **Partial** | `Ctrl+0`/`Ctrl+1` implemented (see below); `+`/`-`/`[`/`]` still adjust stroke/point parameters rather than stepping zoom. |
| Fit to screen | `Ctrl/Cmd + 0` | **Implemented** | `Ctrl+0` fits all strokes into view (or resets view if empty). |
| Actual size (100%) | `Ctrl/Cmd + 1` | **Implemented** | `Ctrl+1` resets zoom to 100% and pan to origin. |
| Hide UI / clean canvas | `Tab` or `Ctrl/Cmd+\`` | **Not implemented** | No `Tab`/backtick toggle for panels/toolbars. |
| Rulers | `Ctrl/Cmd + R` | **Not implemented** | No rulers. |
| Guides / Grid toggle | `Ctrl/Cmd + ;` or `'` | **Not implemented** | No guides or grid toggle. |

## 4. Modifier Key Conventions (Mouse + Keyboard)

| Modifier behavior | Conventional | Status | Notes in this app |
|---|---|---:|---|
| `Shift` — constrain aspect / 45°/90° | Lock ratio, orthogonal move, add to selection | **Partial** | `Shift` held while drawing/dragging now constrains to a **straight line** (replacing former `V`-hold), and makes numeric-field scrubbing 5× coarser. `Shift` is also used in selection/snap flows; not a full, uniform "constrain to 45°/90° + aspect-lock + add-to-selection" across all transforms. |
| `Alt` — duplicate on drag / transform from center / subtract selection | `Alt+Drag` dup, center-scale, subtract | **Partial** | `Alt` is used with the **reference image** interactions; not a general "duplicate object on drag", "scale from center", or "subtract from selection" modifier. |
| `Ctrl/Cmd` — override / bypass snap | Direct-select override or disable snapping while dragging | **Partial** | `Ctrl`/`Cmd` used for file/edit/view shortcuts and combos, and makes numeric-field scrubbing 10× finer; no general "temporarily disable snapping while dragging" or direct-selection override modifier. |

## 5. Expected UI & Workspace Interactions

| Interaction | Conventional | Status | Notes in this app |
|---|---|---:|---|
| Scrubby sliders | Drag numeric labels (↔) to adjust; `Shift`=coarse, `Alt`=fine | **Implemented (Ctrl/Cmd instead of Alt)** | All numeric parameters now use `DragField` / `draw_drag_field()` (`src/views/widgets.py`): press to start a scrub from the current value (no click-to-jump), then drag horizontally across the field width to cover the range. `Ctrl`/`Cmd` = 10× finer, `Shift` = 5× coarser. The legacy `Slider` is a `DragField` subclass. Double-click a field to type an exact value: digits/`.`/`-` edit, `Enter` commits (clamped/stepped), `Escape` cancels; opacity fields take percentages (`35` → 35%). |
| Math in input fields | Evaluate expressions (e.g. `1920/2`, `+24px`) | **Not implemented** | No general numeric property fields with arithmetic; wave formula field evaluates wave expressions only. |
| Context-sensitive properties panel | Inspector updates per selection | **Implemented** | Right panel is context-sensitive (draw settings, selection/curve/wave properties update with the active tool/selection). Controls are grouped under clickable collapsible headers; Transform and Curve styles stay open by default, while Arrange, Stroke style, Appearance, Color (curve mode) and Reference start folded. The Transform X/Y/W/H/R fields use a compact two-column grid. |
| Non-destructive layer/node stack | Reorder, eye/lock toggles, right-click mask/group | **Partial** | Per-curve **wave distortion styles** remain a non-destructive, stackable modifier system (enable/reorder/remove, base geometry preserved). No general layers panel with drag-reorder, visibility (eye)/lock icons per stroke, or right-click mask/group. |
| Spring-loaded tools | Hold key to temporarily activate, release to return | **Partial** | `Space` is spring-loaded for **temporary pan**; `Shift`-hold constrains straight drawing. Not spring-loaded switching between primary tools. |
| Customizable keymaps & discoverability | Tooltips show shortcuts; remappable presets | **Partial** | Toolbar buttons now show **hover tooltips with shortcuts** (`Undo Ctrl+Z`, `Redo Ctrl+Y/Ctrl+Shift+Z`, `Draw/Brush B`, `Move/Select V`). No full remappable keymap/preferences UI and no tooltips across all controls. |

## Summary

| Status | Count (approx.) |
|---|---:|
| **Implemented** | 23 (undo/redo, cut/copy/paste, duplicate, select-all, Esc-deselect, save/save-as/open, export PNG, V/B/E/F tool keys, S snapping, `[`/`]`, space-pan, MMB pan, wheel-zoom-at-cursor, fit/100%, context panel, toolbar shortcut tooltips, scrubby numeric fields) |
| **Partial** | 9 (`Ctrl+Shift+V` absent, bare-`C` rebound, zoom-step keys, Shift/Alt/Ctrl modifier semantics, non-destructive wave stack vs full layers, spring-loaded pan/shift, tooltip coverage/remapping) |
| **Not implemented** | ~12 (paste-in-place, group/ungroup, command palette, P/T/I/crop tools, hide-UI, rulers/guides, math-in-inputs, full layer panel, key remapping) |
| **N/A** | 1 (3D R/S/G) |

## Recently implemented (this pass)

- **View/camera transform:** `VIEW_ZOOM`, `VIEW_PAN_X`, `VIEW_PAN_Y` in `src/config.py`; view-aware `to_canvas`/`clamp_to_canvas`/`to_screen` in `src/controllers/coordinates.py`; `draw_scene(..., view_zoom, view_pan)` applies cairo translate/scale (`src/views/canvas.py`).
- **Navigation:** mouse-wheel zoom toward cursor over canvas; `Space`+LMB drag and MMB drag to pan; `Ctrl+0` fit-all; `Ctrl+1` actual size.
- **File I/O:** `src/models/document.py` (XML `.athors` and JSON `.anim.json` serialize/deserialize/save/load) + native dialogs (`pick_open/save/export` in `src/views/dialogs.py`) + `export_scene_image` (PNG/SVG); wired to `Ctrl+S`, `Ctrl+Shift+S`, `Ctrl+O`, `Ctrl+Shift+E`.
- **Editing/selection:** `Ctrl+A` select all, `Ctrl+D` duplicate (+offset), `Ctrl+C/X/V` internal clipboard, improved `Esc` cancel/deselect priority.
- **Tool shortcuts & discoverability:** `V` select, `B` draw/pen, `E` eraser, `F` fill (bucket), `S` toggle snapping; straight-line constraint moved to `Shift`-hold during draw; toolbar hover tooltips with shortcuts (`src/views/toolbar.py`). Bare `C` no longer clears the canvas. Line is a **draw shape** (select `Line` in the bottom shape toolbar), not a separate hotkey; hold `Shift` while drawing with the pen to constrain a straight segment. The per-tool options live in the **right-click popup** on each bottom-bar button: Freehand (fitting, points/curve, boost), Line (45° constrain, arrowhead), Rect/Square (corner radius), Ellipse/Circle (segments), Triangle (isosceles/right/equilateral), Fill (fill color swatches), Eraser/Fill (snapping), plus a shared snapping toggle. There is no top-right Options menu any more.
- **Oriented shape fitting:** `shape_from_doodle` (`src/models/geometry.py`) fits the sketch instead of the axis-aligned bbox: rect/square/ellipse use the min-area oriented box (`_doodle_obb`) and triangles are fitted to the best three sketch corners (`_triangle_corners` + `_perfect_triangle`), so tilted outlines become perfect tilted shapes. Sketches within ~3° of an axis snap to axis-aligned, and straight drags (no width information) keep the old bbox behavior.
- **Bottom toolbar tools & collapsible sidebar:** the bottom bar is `DRAW_SHAPES` + `BOTTOM_TOOLS` (`src/config.py`) — Eraser and Fill appear after a divider; selecting either sets `draw_tool`, while selecting a shape resets `draw_tool` to pen. The right panel leads with a **Tool options** heading and the Pen/Eraser/Fill row; the option groups below it are filtered by the active `draw_tool` (pen → points/curve, boost, tracing; fill → fill color picker; eraser → usage hint), then snapping and reference controls. The sidebar collapses via the chevron tab drawn by `draw_panel_toggle` (`src/views/panel.py`); `relayout()` in `src/controllers/app_controller.py` recomputes `cfg.CANVAS_W`/`PANEL_X` and recreates the cairo surface, and is reused on `VIDEORESIZE`.
- **Fill color:** `bucket_fill_color` (default `(0.45, 0.72, 1.0)`) is chosen in the panel with an HSV square + hue bar + `BUCKET_SWATCHES` presets, or from the right-click Fill popup swatches (`bucket_color_<i>` items). `bucket_pick`/`set_bucket_color` keep the picker and this frame's `state` in sync; new fills are always opaque.

- **Draggable numeric fields:** `DragField` / `draw_drag_field()` (`src/views/widgets.py`) and `scrub_value()` (`src/models/interaction.py`) replace track-and-knob sliders for panel numeric parameters. A click keeps the current value; horizontal drag scrubs relative to the click over the field width. `Ctrl`/`Cmd` = 10× finer, `Shift` = 5× coarser. `Slider` remains as a compatible `DragField` subclass with a `track` alias. Double-click opens an inline editor (`src/controllers/numeric_field_edit.py`); typing replaces the value, `Enter` commits with clamping/stepping, `Escape` cancels, and clicking elsewhere commits first. See `docs/STYLE_GUIDE.md#draggable-numeric-fields`.
