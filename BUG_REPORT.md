# Bug Report — Animathor UI responsiveness

- **Report date:** 2026-11-26
- **Baseline investigated:** `0bc4a22` (`shape-library-workspace`)
- **Overall status:** Nine user-facing regressions were confirmed. All nine are fixed in the current working tree with regression tests; changes still need to be committed.

## Executive summary

The previous report concentrated on the selection-panel exception and treated the other panel observations as secondary. That understated the user impact. The visible symptom is broader: **controls in the side properties panel can appear clickable but do nothing, several top-bar dropdown options close their menu without performing their action, a color-panel click can terminate the event loop with a `NameError`, dragging the color selector circle can terminate it with an `UnboundLocalError`, editing the second gradient stop can silently collapse a gradient to a solid fill, panel sliders stop dragging, the empty-selection Fill tab overlaps the following panel content, curve-style sliders/headers are drawn over earlier controls so those controls are hidden, redrawing a curve shows only the faded template instead of the live path being drawn, and resizing the window leaves the canvas render surface at its old dimensions.**

A mandatory 8px UI-chrome spacing contract was also added in `docs/STYLE_GUIDE.md` and enforced across panels, toolbars, menus, and dialogs.

| ID | Area | User-visible result | Severity | Status at report time |
|---|---|---|---|---|
| RESP-01 | Right/side control panel | Draw-mode controls silently ignore clicks; in Selection mode a panel click can terminate the event loop and freeze the window | Blocker / High | Fixed in the current working tree; commit and regression coverage pending |
| RESP-02 | Top-bar dropdown options | Edit, Tools, and Help options close the dropdown but do not execute; the related single-key shortcuts also do nothing | High | Fixed in the current working tree; regression test added |
| RESP-03 | Fill/color panel click | Setting a color in Curve submode raises `NameError` and terminates the event loop; in Transform submode a fill swatch can be a no-op | Blocker / High | Fixed in the current working tree; regression tests added |
| RESP-04 | Color-picker drag | Dragging the selector's SV circle/square raises `UnboundLocalError` and terminates the event loop; hue drags have the same defect | Blocker / High | Fixed in the current working tree; regression tests added |
| RESP-05 | Gradient stop editing | Setting the second gradient stop's color collapses the gradient into a solid fill | High | Fixed in the current working tree; regression tests added |
| RESP-06 | Panel slider dragging / layout | Panel sliders such as object opacity stop responding to drag, and the empty-selection Fill tab overlaps following controls | High | Fixed in the current working tree; regression tests added |
| RESP-07 | Panel control overlap | Curve-style sliders and section headers are drawn over earlier buttons/previews, hiding controls | High | Fixed in the current working tree; regression tests added |
| RESP-08 | Curve redraw preview | Redrawing a curve shows only the faded template; the path being drawn is invisible until release | High | Fixed in the current working tree; regression tests added |
| RESP-09 | Window resize / infinite canvas | Maximising or resizing the window leaves the canvas at its previous render size instead of expanding with the window | High | Fixed in the current working tree; regression tests added |

### Scope

- **Side control panel** means the right-hand properties/tool-options panel. Its collapse chevron is a separate control and is not the subject of this report.
- **Top-bar options** means items in the File, Edit, View, Tools, and Help dropdowns. The direct **Draw / Library** switcher at the far left uses a separate event path and is not affected by RESP-02.
- A Selection-mode panel crash can make the entire window, including the top bar, appear unresponsive. RESP-02 is nevertheless a separate, reproducible command-dispatch defect.

---

## RESP-01 — Side control panel does not respond

### Expected behavior

- In Draw mode, clicking a control in the right panel updates its corresponding state: the Snap toggle changes, a Fill picker or swatch changes the fill color, the Pen/Eraser/Fill/Split arrows change the active tool, the trace-algorithm arrows change the algorithm, and reference-image controls load/show/clear the reference.
- In Selection mode, clicking the Transform/Nodes/Curve arrows changes the selection submode, and the rest of the selection controls react without terminating the app.

### Actual behavior

#### Draw mode: valid clicks are silently consumed

The following visible controls do not react to clicks:

- **Snapping: ON/OFF**
- Fill **HSV picker** and preset swatches
- Draw-tool **previous/next** arrows (Pen / Eraser / Fill / Split)
- Trace-algorithm **previous/next** arrows
- Reference-image **Load / Show / Clear** controls

The **Boost** control was an exception because it was handled by a more specific branch before the faulty catch-all. This made the failure look intermittent even though the controls share the same dispatch path.

#### Selection mode: a panel click can crash and freeze the app

A click in the right panel while Selection mode is active can raise:

```text
AttributeError: 'ToolState' object has no attribute 'selection_submode'
```

The exception escapes event processing and terminates the application event loop. The window remains visible but stops processing input, so subsequent side-panel and top-bar clicks also appear to do nothing.

### Reproduction

**Draw-mode silent failure**

1. Start the app and remain in Draw mode.
2. Click **Snapping: ON** in the right panel.
3. Expected: the label/state toggles to OFF.
4. Actual: nothing changes.
5. Repeat with a Fill swatch and the draw-tool arrows; the same controls remain unchanged.

**Selection-mode crash**

1. Start the app and switch to Selection mode.
2. Click any location in the right panel.
3. Expected: the clicked control reacts and the app remains responsive.
4. Actual (baseline `0bc4a22`): the `AttributeError` above is printed and the event loop terminates; the window freezes.

### Root causes

#### 1. A duplicate Draw-mode branch shadows every real control handler

In the baseline version of `src/controllers/panel/tool_options.py`, two adjacent branches both tested `tools.tool_mode == "draw"`:

```python
elif tools.tool_mode == "draw":
    _matched = True
elif tools.tool_mode == "draw":
    # real handling for reference image, snapping, bucket picker/swatches,
    # draw-tool cycling, shapes, and trace-algorithm cycling
```

The first branch matched **every** Draw-mode panel click. The real handling branch was therefore unreachable. The function then returned `None`, so the click was not reported as handled but also produced no state change. The baseline location was `0bc4a22:src/controllers/panel/tool_options.py:47-50`.

#### 2. The Selection submode is read from the wrong state owner

`selection_submode` belongs to `SelectionState` (`src/controllers/app_state.py:51`), but the baseline typed panel handler read it from `ToolState` in four places:

- `0bc4a22:src/controllers/panel/align_distribute.py:67`
- `0bc4a22:src/controllers/panel/align_distribute.py:118`
- `0bc4a22:src/controllers/panel/align_distribute.py:147`
- `0bc4a22:src/controllers/panel/align_distribute.py:154`

Those reads raised as soon as a Selection-mode panel click entered the align/distribute handler. The main event loop has no exception boundary around frame event processing (`src/controllers/app_controller.py:542-544`), so the exception terminated the loop.

#### 3. After a valid click, stale frame locals overwrote the typed mutation

Removing the first two blockers exposed the reason the panel still looked dead in a live session. A panel click does reach `tool_options_typed()` and mutates `AppState`, but `process_event_frame()` then calls `AppState.sync_from_locals(loc)` without narrowing the fields (`src/controllers/app_frame_controller.py`, pre-fix lines 58-64). The event boundary `event_loop._call_handler()` operates on a plain snapshot (`src/controllers/event_loop.py:16-21`) and `_sync_all()` copies that stale snapshot back over `ctx` (line 13). Consequently the typed mutation was immediately reverted from the stale frame local and the next render showed the old value.

A direct probe of the pre-fix sync showed:

```text
OLD-WIDE result= continue ctx.snap= True typed.snap= True
FILTERED result= continue ctx.snap= True typed.snap= False
```

### Current worktree status

The current working tree addresses all three causes:

- The duplicate Draw-mode catch-all was removed, the real control branch is reachable, and `tool_options_typed()` now returns `'continue'` after handling a matched control (`src/controllers/panel/tool_options.py:47-162`).
- All four panel reads now use `selection.selection_submode` (`src/controllers/panel/align_distribute.py:67,118,147,154`).
- `process_event_frame()` snapshots the dispatch context and syncs back only fields actually rebound by an event handler, so direct typed mutations from panel handlers survive (`src/controllers/app_frame_controller.py:55-75`). Legacy `ctx` field rebinding still reaches typed state.
- Regression tests:
  - `tests/test_tool_cycling.py`
  - `tests/test_submode_cycling.py`
  - `tests/test_panel_event_sync.py` - drives real panel handlers through `process_event_frame()` for the Snap toggle and Transform/Nodes arrow, and checks that legacy rebinding still propagates.

These changes are not part of baseline `0bc4a22`; they still need to be committed.

### Acceptance criteria

1. Every visible Draw-mode panel control updates state on its first click.
2. A Selection-mode panel click never raises `AttributeError` and never stops the event loop.
3. The Transform/Nodes/Curve arrows update the selected submode in both directions.
4. The side panel remains responsive after switching repeatedly between Draw and Selection modes.
5. A regression test exercises the real typed `AppState`/dispatch path (`tests/test_panel_event_sync.py`).

---

## RESP-02 — Top-bar dropdown options do not execute

### Expected behavior

Choosing a top-bar dropdown item runs that command. For example, **Tools → Pen** enters Pen mode, **Edit → Workspace** switches between Draw and Library, and **Help → Keyboard Shortcuts…** opens the shortcut overlay.

### Actual behavior

Affected menu items close the dropdown but leave the application state unchanged:

- **Edit → Workspace**
- **Edit → Cycle Selection Mode**
- **Tools → Pen**
- **Tools → Select / Move**
- **Tools → Eyedropper**
- **Tools → Eraser**
- **Tools → Bucket Fill**
- **Tools → Split Curve**
- **Help → Keyboard Shortcuts…**

The same command path is used by the single-key shortcuts, so these documented shortcuts are also ineffective:

- `V` — Select/Move
- `B` — Pen
- `I` — Eyedropper
- `E` — Eraser
- `F` — Bucket Fill
- `C` — Split Curve
- `T` — Text
- `N` — Cycle Selection Mode

Not all top-bar items are broken. File and ordinary Edit commands are handled by earlier registry entries. View/artboard/symbol/shape-state actions execute inside the View handler. **View → Toggle Snapping** (`S`) therefore still works. The direct Draw/Library switcher at the far left also works independently.

### Reproduction

1. Start the app.
2. Open **Tools** and click **Pen**.
3. Expected: the active tool changes to Pen.
4. Actual: the dropdown closes and the active tool remains unchanged.
5. Open **Edit → Workspace** or **Help → Keyboard Shortcuts…**; the same no-op behavior occurs.

A direct registry probe against the current code produced:

```text
WORKSPACE    handled=True  workspace: 'draw' -> 'draw'
TOOL_SELECT  handled=True  tool_mode: 'draw' -> 'draw'
TOOL_PEN     handled=True  tool_mode: 'selection' -> 'selection'
SHORTCUTS    handled=True  help_open: False -> False
```

`handled=True` is misleading: the command was reported as handled even though its state did not change.

### Root cause

The semantic command registry stops at the first handler that returns a truthy value:

- `src/controllers/commands/registry.py:18-22`

Handlers are registered in this order:

- `src/controllers/commands/registry.py:25-35`

```python
reg.register(handle_file_command)
reg.register(handle_edit_command)
reg.register(_menu_view)
reg.register(_menu_tools)
```

The View wrapper returns `True` unconditionally, even when none of its sub-handlers recognized the command:

- `src/controllers/commands/view_commands.py:249-259`

```python
for handler in (...):
    if handler(ctx, key):
        return True

return True  # consumes every command before _menu_tools is reached
```

As a result, `_menu_tools` (`src/controllers/commands/tool_commands.py:8-58`) is never called for Tool, Help, Edit-Workspace, or Edit-Cycle commands. The top-bar click handler does call `run_menu_action()` correctly (`src/controllers/menu_clicks.py:33-40`); the command is discarded later in registry dispatch.

### Fix applied (current working tree)

Restored the registry contract:

- `src/controllers/commands/view_commands.py` - `_menu_view` now returns `False` when no view/artboard/symbol/shape-state handler recognizes the command; view-domain subhandlers return `True` on recognized commands.
- `src/controllers/commands/tool_commands.py` - `_menu_tools` returns `True` only for recognized tool/workspace/help/cycle commands, else `False`.
- `src/controllers/commands/registry.py` keeps first-match ordered dispatch.

Regression coverage: `tests/test_command_registry_dispatch.py` dispatches through the registry and asserts state changes for `WORKSPACE`, `TOOL_SELECT`, `TOOL_PEN`, `SHORTCUTS`, `CYCLE_SUBMODE`, and that an unknown command returns `False` without mutating state.

### Acceptance criteria

1. Every item in the File, Edit, View, Tools, and Help dropdowns performs its advertised action.
2. The direct Draw/Library switcher continues to work.
3. `V`, `B`, `I`, `E`, `F`, `C`, `T`, and `N` update the same state as their menu items.
4. An unknown command returns `False` from the registry.
5. A known command returns `True` and has an observable state change.
6. Tests dispatch commands through the registry rather than checking only that command IDs appear in source.

---

## RESP-03 — Fill/color panel click crashes or does nothing

### Expected behavior

Clicking a color target, swatch, or picker control in the right panel applies the color and leaves the application responsive. This must work both in Selection → Curve submode (component colors) and Selection → Transform submode (stroke/fill colors).

### Actual behavior

In Selection → Curve submode, any color-panel click follows this path and crashes before a color handler runs:

```text
_handle_panel_click_b
  -> effects_wave_hit
     -> handle_b_part3
        -> effects_wave_part3_typed
           -> _b3_wave_hits
              -> NameError: name 'state' is not defined
```

The exception escapes `process_event_frame()` and terminates the event loop, so the window remains visible but stops accepting input. In Selection → Transform submode, a fill swatch click could also be silently consumed because the fill-picker bridge attributes were never published.

### Reproduction

1. Start the app and switch to Selection mode.
2. Select a curve component (Curve submode).
3. Click a color tab, swatch, or picker control in the right panel.
4. Expected: the component color is edited and the app stays responsive.
5. Actual: the `NameError` above is printed and the event loop stops.

A second reproduction covers the silent failure:

1. Switch to Selection → Transform mode with a stroke selected.
2. Switch the color tab to **Fill** and click a preset fill swatch.
3. Expected: the stroke fill color changes.
4. Actual (pre-fix): the click produced no color change.

### Root causes

1. **Extracted wave-hit handlers referenced bare locals that no longer existed.** `src/controllers/panel/wave_hits.py` was mechanically split from a `ctx`-based body. `_b3_wave_hits()` and `_b3_wave_sliders()` still referenced `state`, `selection`, `document`, `ui`, `stroke_components`, `get_distortion_style`, `set_distortion_style`, and `wi` as locals. In the typed dispatch path these values live on `AppState` substates and on `ctx` attributes, so the first loop in `_b3_wave_hits()` raised `NameError` even when no wave rect was hit. The `repeat_pick_curve_rect` branch also used `si`/`comp_i` before assigning them on that path.
2. **The color-target bridge forwarded an undefined `tools` name.** `color_target_hit()` called `fill_picker_hit(tools, ...)` although `tools` was not a parameter or a resolved local.
3. **The Transform-mode panel wrapper bypassed its typed domain entry point.** `_handle_panel_click_c()` called `gradient_stops_hit()` directly instead of `gradient_panel_hit()`, so `_c_primary_obj`, `_c_sel_list`, and `_c_set_comp_stroke_color` were never written to the dispatch context. The downstream fill-picker handlers therefore saw no primary object and ignored swatch clicks.
4. **Adjacent extracted handlers had the same class of latent undefined names.** `wave_motion.py` used an undefined `color_target` as a dict default and in a drag condition. `fill_picker_options.py` and `gradient_tabs.py` referenced guarded gradient helpers as bare globals instead of resolving them through their `globals_map` argument.

### Fix applied (current working tree)

- Added `_wave_hit_context(ctx)` in `src/controllers/panel/wave_hits.py`. It resolves typed `selection`/`document`/`ui` substates, the live `state` mapping, service callables from `ctx` with model-level fallbacks, the active wave index, and `clamp`. Both wave-hit functions now use those locals, and the repeat-pick branch derives its target from `selection.selected_curve`.
- `src/controllers/panel/color_target.py` now derives `tools` from `ctx.tools` or `ctx._app_state.tools` before forwarding to the typed fill-picker entry point.
- `src/controllers/panel/gradient_panel.py` now calls `gradient_panel_hit()` (with `ctx._stroke_components`) from `_handle_panel_click_c()`, so the typed entry point publishes the fill-picker bridge attributes before ctx-based handlers run.
- `src/controllers/mouse_motion/wave_motion.py` now resolves `color_target` from `ctx.state` with a safe `ctx.color_target` fallback.
- `src/controllers/panel/fill_picker_options.py` and `src/controllers/panel/gradient_tabs.py` now call guarded gradient helpers through `globals_map[...]` instead of bare global names.
- A static global-reference scan over `src/controllers` reports no remaining undefined names in the extracted panel/motion handlers. The only remaining hits are pre-existing dynamic wildcard-import globals in `app_controller.py`, `coordinates.py`, and `mouse_button_down.py`.

Regression coverage: `tests/test_fill_color_panel_hits.py` drives the exact `_handle_panel_click_b` / `effects_wave_hit` / `handle_b_part3` path from the traceback and asserts that a color click no longer raises and actually updates a component color. It also checks a displacement toggle through the same path and a Transform-mode fill swatch through `_handle_panel_click_c`.

### Acceptance criteria

1. A color-panel click in Selection → Curve submode never raises `NameError` and never stops the event loop.
2. Wave/displacement hit controls still update the active component style through the typed dispatch context.
3. A Transform-mode fill swatch changes the selected stroke's fill color.
4. No extracted panel or motion handler references an undefined bare global.
5. Regression tests exercise the real typed `AppState`/dispatch path, not just source-string checks.

---

## RESP-04 — Dragging the color selector crashes the event loop

### Expected behavior

Dragging the HSV color selector — the SV circle/square, hue strip, or alpha strip — updates the picker values and the selected stroke or component color, and the application stays responsive.

### Actual behavior

The user-reported symptom is: “i get thhis error whenever i try to grag the color selector(s circle thing”. Dragging the selector raises:

```text
File "C:\Users\amani\Documents\animathor\src\controllers\mouse_motion\wave_motion.py", line 72, in color_picker_drag_move
    col = ctx.hsv_to_rgb(picker_h, picker_s, picker_v)
UnboundLocalError: cannot access local variable 'picker_h' where it is not associated with a value
```

The exception escapes mouse-motion dispatch and terminates the event loop. The window remains visible but stops accepting input. Hue drags fail the same way for `picker_s`/`picker_v`.

### Reproduction

1. Start the app and switch to Selection mode with a stroke selected.
2. Open the right-panel color controls so the `sv_rect` and `hue_rect` values are live.
3. Drag the color selector circle/square, or drag along the hue strip.
4. Expected: the color and picker readout change continuously while dragging.
5. Actual: the `UnboundLocalError` above is printed and the event loop stops.

### Root cause

`src/controllers/mouse_motion/wave_motion.py` was mechanically split from a `ctx`-based body. In `color_picker_drag_move()`, the HSV values were only assigned inside individual branches:

- the SV branch assigned `picker_s` and `picker_v`, then called `ctx.hsv_to_rgb(picker_h, picker_s, picker_v)` without ever assigning `picker_h`;
- the hue branch assigned `picker_h`, then used the never-assigned `picker_s` and `picker_v`.

Because those names are assigned somewhere in the function, Python treats them as locals throughout the function. Missing assignments therefore raise `UnboundLocalError` instead of reading the current values from `ctx.state` or `ctx`. After a successful drag, only `ctx.state` was updated; the matching `ctx` attributes stayed stale, so the next dispatched event could feed old picker values back into the drag handler. `gradient_stop_drag_move()` had the same state-only write after deriving HSV from a gradient stop.

The RESP-03 fix to the undefined `color_target` default had to be in place before execution could reach the failing HSV line. Without that fix, the same function failed earlier on `ctx.state.get("color_target", color_target)`.

### Fix applied (current working tree)

- Added `_read_picker_hsv(ctx)` in `src/controllers/mouse_motion/wave_motion.py`. It reads `picker_h`, `picker_s`, and `picker_v` from `ctx.state`, falls back to `ctx` attributes, normalizes them to floats, and is called before any drag branch uses the values.
- Added `_write_picker_hsv(ctx, picker_h, picker_s, picker_v)`. It publishes updated picker values to both `ctx.state` and the corresponding `ctx` attributes, so rendering and typed dispatch see the same values.
- Used the shared writer after SV drags, hue drags, and gradient-stop position drags.
- Replaced the undefined `color_target` local default with `getattr(ctx, "color_target", "stroke")` and applied the same resolution in `gradient_stop_drag_move()`.

Regression coverage: `tests/test_color_picker_drag.py` drives an SV drag through `UiDragSession.move()` and a hue drag through `color_picker_drag_move()` directly. It asserts that no exception is raised, picker state updates, the selected fill color changes, saturation/value survive hue changes, and `ctx` mirrors `ctx.state` after the drag.

### Acceptance criteria

1. Dragging the color selector circle/square never raises `UnboundLocalError` and never stops the event loop.
2. Hue drags preserve the current saturation and value while updating hue and the target color.
3. Picker values are available to both the render state and the typed dispatch context after a drag.
4. Gradient-stop position drags publish their derived HSV values through the same helper.
5. Regression tests exercise the real UI-drag session path, not just source-string checks.

---

## RESP-05 — Editing the second gradient stop collapses the gradient

### Expected behavior

After converting a fill to a gradient, selecting the second stop and changing its color must update only that stop. The fill must remain a gradient and `fill_color` must stay `None`.

### Actual behavior

Setting the second stop's color turns the entire fill into a solid color. A direct panel probe against the pre-fix handlers produced:

```text
after fill type next
  fill_color: None
  gradient type: linear
  stops: [{'pos': 0.0, 'color': [0.1, 0.2, 0.3, 1.0]}, {'pos': 1.0, 'color': [1.0, 1.0, 1.0, 1.0]}]

after second stop swatch
  fill_color: (0.9, 0.2, 0.3, 1.0)
  gradient type: None
  stops: None
```

The same problem affects gradient-stop color changes made through the SV/hue drag path.

### Reproduction

1. Select a shape and switch the **Fill** target to a gradient, for example **Linear**.
2. Select the second gradient stop swatch in the panel.
3. Click a preset swatch, or drag the color selector, to change that stop's color.
4. Expected: only the second stop changes; the shape still has a two-stop gradient.
5. Actual (pre-fix): `fill_color` becomes a solid color and `fill_gradient` is cleared.

### Root cause

The extracted panel handlers receive `get_fill_gradient` as an explicit typed-service parameter, but their guards checked the module globals map instead:

```python
fg = get_fill_gradient(stroke) if 'get_fill_gradient' in globals_map else None
```

`get_fill_gradient` is not imported into those extracted modules' globals, so the guard was always false. Every color edit treated the stroke as if it had no gradient and took the solid-fill branch. The same wrong guard existed in `src/controllers/mouse_motion/wave_motion.py` as `'get_fill_gradient' in globals()`; related `get_gradient_stop_color`, `set_gradient_stop_color`, `set_gradient_stop_pos`, and `clamp_gradient_stop_index` guards there also checked module globals instead of the services available on the dispatch context.

### Fix applied (current working tree)

- Replaced all 32 `'get_fill_gradient' in globals_map` guards across `fill_picker_color.py`, `fill_picker_options.py`, `fill_picker_stops.py`, `gradient_color_picker.py`, `gradient_stops_edit.py`, and `gradient_tabs.py` with `callable(get_fill_gradient)`, so the explicit typed service parameter is used.
- Replaced the equivalent `globals()` guards in `src/controllers/mouse_motion/wave_motion.py` with `callable(getattr(ctx, ...))` checks against the live dispatch context.
- Gradient-stop swatch clicks and SV/hue/alpha drags now preserve `fill_gradient` and call `set_gradient_stop_color()` for the selected stop.
- Fill-type cycling now recognizes an existing gradient regardless of type and preserves its edited stops.

After the fix, the same probe reports:

```text
after second stop swatch
  fill_color: None
  gradient type: linear
  stops: [{'pos': 0.0, 'color': [0.1, 0.2, 0.3, 1.0]}, {'pos': 1.0, 'color': [0.9, 0.2, 0.3, 1.0]}]
```

Regression coverage: `tests/test_gradient_stop_preservation.py` asserts that a second-stop swatch click preserves the gradient, that fill-type cycling keeps the edited stop, and that a hue drag updates the second stop without collapsing the fill.

### Acceptance criteria

1. Changing the second stop's color never clears `fill_gradient` or sets a solid `fill_color`.
2. The first stop and stop positions remain unchanged when the second stop's color is edited.
3. Cycling fill type after editing the second stop preserves the edited stop colors.
4. Gradient-stop color drags preserve the gradient and update only the selected stop.
5. Regression tests cover panel click, fill-type cycling, and drag paths.

---

## RESP-06 — Sliders stop dragging and panel controls overlap

### Expected behavior

- Dragging a right-panel slider such as **Object opacity**, **Fill alpha**, or the bucket picker continues to update its value while the mouse moves.
- Published panel controls occupy their own vertical space. In the empty-selection view, the visible **Fill** tab must not be drawn on top of the following help text or any later control.

### Actual behavior

A panel slider can be clicked and appears to move for one frame, but continuing to drag does not update the value. Separately, in Selection mode with no shape selected, the newly visible **Fill** tab is drawn at a y position that is immediately reused by the next panel content, so the two overlap.

### Reproduction

1. Select a shape in Selection mode.
2. Click and drag the **Object opacity** slider horizontally.
3. Expected: opacity follows the cursor continuously.
4. Actual (pre-fix): the drag session never activates, so the opacity stops changing after the initial click.
5. Clear the selection so the panel shows **Select a stroke** and the **Fill** tab.
6. Expected: help text starts below the tab.
7. Actual (pre-fix): help text starts at the tab's top edge and overlaps it.

### Root causes

#### 1. Typed drag flags were overwritten by the handler sync boundary

Panel mouse-down handlers run through `_call_handler()` in `src/controllers/event_loop.py`. That helper gives each handler a plain `SimpleNamespace` snapshot of the context, then `_sync_all()` copies the snapshot back. The typed handlers write drag ownership directly to `AppState.ui`, for example:

```python
ui.obj_opacity_drag = True
state["obj_opacity_drag"] = True
```

The typed field and view-state dict became `True`, but the stale flat field in the handler snapshot stayed `False`. `_sync_all()` copied that stale value back onto the context, so `ui_drag_active(ctx)` returned false and `UiDragSession` never began. A probe of that boundary produced:

```text
before: ctx=False typed=False state=False
after:  ctx=False typed=True  state=True   # pre-fix
```

The same pattern affected the other typed UI drag flags (color alpha/SV/hue, bucket picker, reference opacity).

#### 2. The empty-selection Fill tab did not advance the layout cursor

`render_no_selection_state()` in `src/views/panel_domain_color.py` publishes and draws a Fill tab, then returned the same `y` used for the tab's top edge. The caller drew subsequent content from that y. A rendered-panel probe showed:

```text
tab = (1056, 176, 116, 26)   # bottom = 202
BEFORE content_bottom = 176  # next content starts above the tab bottom
AFTER  content_bottom = 208  # next content starts below the tab
```

### Fix applied (current working tree)

- `src/controllers/event_loop.py` now snapshots typed substate values before each handler call. `_sync_all()` preserves typed fields changed directly by handlers and still propagates ordinary flat rebindings through `DispatchContext.__setattr__`. The same typed snapshot is used around the mouse-motion handler.
- After the fix, the drag-boundary probe reports all three views of the flag as `True`:

```text
after: ctx=True typed=True state=True
```

- `render_no_selection_state()` advances `y` by the tab height plus spacing, so the caller's help text and later controls start below the tab. The tab is also drawn active when the fill target is selected.
- The empty-selection Fill tab click is now dispatched in `gradient_panel_hit()` so the visible tab actually sets `color_target` to `fill` even with no shape selected.

Regression coverage: `tests/test_slider_drag_and_layout.py` asserts that a real opacity-panel click activates the UI drag session, that drag motion updates the selected stroke's opacity, that the Fill tab reserves vertical space, and that clicking it without a selection sets the fill target.

### Acceptance criteria

1. Typed UI drag flags set by panel handlers are visible on the flat dispatch context used by `UiDragSession`.
2. Object opacity and equivalent panel sliders continue updating while the mouse moves.
3. The empty-selection Fill tab is clickable and drawn active when selected.
4. Subsequent panel content starts below the Fill tab instead of overlapping it.
5. Regression tests cover both the drag-sync and layout paths.

---

## RESP-07 — Curve-style controls are hidden by overlapping draws

### Expected behavior

Every visible panel control owns its vertical space. A later section's header, slider label, or slider track must not be drawn on top of an earlier button, affect toggle, custom-curve preview, or shape selector.

### Actual behavior

With a selected curve style, several later draws land on top of controls that are already visible. Those earlier controls are still in the hit-rect map, but their label or center is obscured, so they appear unavailable. An instrumented draw-call probe recorded these concrete overlaps before the fix:

```text
shadow:       672px2  control=(1056, 712, 117, 22) covered by blit (1056, 712, 42, 16)
displacement:1092px2  control=(1056, 444, 117, 24) covered by blit (1056, 456, 91, 15)
displacement: 949px2  control=(1056, 472, 117, 24) covered by blit (1056, 482, 73, 13)
wave:         476px2  control=(1088, 424, 176, 28) covered by blit (1056, 430, 66, 14)
wave:         392px2  control=(1056, 424, 28, 28) covered by blit (1056, 430, 66, 14)
wave:         325px2  control=(1268, 424, 28, 28) covered by blit (1271, 430, 25, 13)
```

The published-rect probe also showed the repeat-curve preview box overlapped by all three stale slider hit rects:

```text
wave_custom_box_rect = (1064, 432, 180, 80)
amplitude            = (1056, 414, 240, 22)
frequency            = (1056, 440, 240, 22)
phase                = (1056, 466, 240, 22)
```

### Reproduction

1. Select a stroke in Selection mode and switch to Curve submode.
2. Add a Wave, Displace, Repeat, or Thickness curve style.
3. Observe the style parameters and the controls immediately above them: slider labels/tracks are drawn over the affect buttons or shape selector, and later buttons sit at stale y positions.
4. Enable a drop shadow and observe the following section's "Color" header/text drawn directly over the `- Blur` / `+ Blur` stepper.
5. Expected: each section starts below the previous section's last control. Actual (pre-fix): the sections reuse the same y coordinates.

### Root causes

#### 1. The shadow blur stepper did not reserve its row

`render_color_section()` in `src/views/panel_domain_color.py` published and drew `shadow_blur_minus_rect` / `shadow_blur_plus_rect`, then returned to the color-picker section without advancing `y`. The next "Color" header was rendered at the same y as the stepper buttons.

#### 2. The extracted style renderers advanced the wrong frame's `y`

`_part_b2b_main()` in `src/views/panel_domain_effects.py` defines `_style_slider` as a closure over its own `nonlocal y`. The extracted renderers in `src/views/panel_domain_style_effects.py` receive their own `y` argument/local. When `render_displacement_section()`, `render_repeat_section()`, `render_thickness_section()`, or `render_wave_section()` called that closure, it advanced `_part_b2b_main`'s `y`, not the renderer's `y`. Sliders were therefore drawn at a stale position, overlapping earlier controls, and the renderer returned a stale y for subsequent buttons.

### Fix applied (current working tree)

- `src/views/panel_domain_color.py`: advance `y` by the blur stepper height plus spacing after `- Blur` / `+ Blur`, so the color section starts below the buttons.
- `src/views/panel_domain_style_effects.py`:
  - added `draw_style_slider()`, which draws one slider and returns the next y;
  - added `_local_style_slider()`, which advances a section-owned `y_holder`;
  - converted all four style sections to the local y-holder pattern and set `y = _yh["y"]` before drawing following controls and returning;
  - kept `_style_slider` in each signature only for legacy ctx-bag compatibility.

After the fix, the expanded instrumented probe covered 18 panel states (draw modes, selection submodes, shadow, and all four curve styles) and reported `TOTAL UNEXPECTED OVERLAPS: 0`. The only remaining hits are intentional child elements drawn inside their own empty-label container buttons: the `ON`/`OFF` and `×` labels inside a style-row button, and the shape name inside the shape-value button. The published rects now show clean separation, for example:

```text
shadow:    blur buttons y=876..898, next color tabs y=928..954
repeat:    preview box y=432..512, sliders y=592..666
```

Regression coverage: `tests/test_panel_control_overlaps.py` renders the real panel for a shadow stroke and for each of the four curve-style types. It asserts that the shadow stepper does not overlap the color tabs, that repeat/thickness sliders start below their drawing boxes, that displacement sliders start below the affect buttons, and that wave sliders start below the shape selector.

### Acceptance criteria

1. A shadow blur stepper is never covered by the following color section header.
2. Curve-style sliders are drawn below the section controls they follow, not on top of them.
3. Published slider hit rects do not intersect preview boxes, affect buttons, or shape selectors.
4. Existing nested child controls inside a parent button remain usable.
5. Regression tests exercise the real panel render path for all affected sections.

---

## RESP-08 — Curve redraw has no live preview

### Expected behavior

After clicking **Redraw** in Selection → Curve mode, dragging on the canvas shows the path being drawn while the mouse is held down. The original curve remains visible as a faded yellow template, and releasing the mouse commits the new curve.

### Actual behavior

Dragging shows only the faded yellow template of the original component. The in-progress polyline is not rendered, so the user cannot see the replacement curve until the gesture is already committed.

### Reproduction

1. Select a stroke in Selection mode and switch to Curve submode.
2. Select one curve component and click **Redraw**.
3. Drag across the canvas to sketch the replacement.
4. Expected: the orange live path follows the drag.
5. Actual (pre-fix): no live path; only the faded original template is drawn.

### Root cause

`render_scene()` already published the in-progress points as the renderer's `active_stroke`:

```python
ctx.active = ctx.current_points if (ctx.drawing and ctx.tool_mode == "draw") else (
    ctx.redrawing_curve.get("points") if ctx.redrawing_curve else None
)
```

`draw_scene()` then discarded that data because its only live-preview block was gated by `redrawing_curve is None`, and its generic branch also required `not edit_mode`. Curve redraw runs in Selection (edit) mode with `redrawing_curve` set, so neither preview path ran. The extracted live-preview block introduced in `8b60e2a` covered freehand/Bezier drawing but omitted the redraw case.

### Fix applied (current working tree)

- `src/views/canvas_extra3.py`: added `_draw_redraw_preview()`, which draws the active redraw points as an orange `EDITOR_ACCENT` polyline.
- The preview is drawn after the selection overlay so it stays visible above both the faded template and the selected-curve highlight.
- The preview remains excluded from export renders (`for_export=True`), matching the previous preview contract.

Rendered pixel evidence from the real Cairo path at the probe vertex `(57, 43)`:

```text
no live points: (255, 255, 255, 255)
live preview:  (242, 121, 36, 255)
```

A side-by-side PNG was also generated at `C:\Users\amani\AppData\Local\Temp\opencode\redraw_preview_evidence.png`.

Regression coverage: `tests/test_redraw_preview.py` renders the real panel/canvas scene and asserts that redraw points change the probe pixel to the orange preview color and that export renders remain unchanged.

### Acceptance criteria

1. The live redraw path is visible while dragging.
2. The faded template of the original curve remains visible underneath.
3. The preview sits above the Curve-mode selection highlight.
4. Exported artwork does not contain the preview.
5. A regression test exercises the real `draw_scene()` render path with redraw points.

---

## RESP-09 — Canvas does not expand when the window is resized

### Expected behavior

Resizing or maximising the window grows the infinite canvas to the new available area. `cfg.WIDTH`, `cfg.HEIGHT`, `cfg.CANVAS_W`, `cfg.CANVAS_X` and `cfg.PANEL_X` update together, and the next frame renders into a Cairo surface with the new canvas dimensions.

### Actual behavior

The window frame resizes, but the canvas artwork area keeps its old size. On a larger window the canvas does not fill the newly available space; on a smaller window it remains clipped to the old render dimensions.

### Reproduction

1. Start the app at its default `1316 x 700` window size.
2. Maximise the window or drag its edge to `1600 x 1000`.
3. Expected: the canvas surface becomes `1264 x 916` (`1600 - left bar - panel`, `1000 - top bar - bottom bar`).
4. Actual (pre-fix): the render surface stays `980 x 616` even though the window and layout constants changed.

### Root cause

`relayout()` did recreate the Cairo surface and rebind the `cairo_surface` frame local, but the extracted frame boundary creates a `DispatchContext` snapshot of all frame fields before calling `process_events()`:

```python
ctx = DispatchContext(app_state, fields)   # captures old cairo_surface
_pe(ctx)
_sync_back(ctx, loc)                       # copies old cairo_surface over relayout's new one
```

`VIDEORESIZE` updated `cfg.WIDTH`/`cfg.HEIGHT` and called `ctx.relayout()`, but the stale flat `ctx.cairo_surface` field was then copied back by `_sync_back()`. `render_scene()` used that stale surface, so the visible canvas never matched the new window geometry.

### Fix applied (current working tree)

- `src/controllers/app_controller.py`: created `cairo_surface_holder`, a shared holder updated by `relayout()` on every resize or sidebar toggle.
- `src/controllers/event_loop.py` and `src/controllers/menu_pre_dispatch.py`: refresh the flat `ctx.cairo_surface` mirror from the holder after relayout, so `_sync_back()` cannot restore the old surface.
- `src/controllers/render/scene_state.py`: added `canvas_surface_for_context()`; `render_scene()` now prefers the holder's current surface and still supports legacy contexts that only provide `cairo_surface`.

Rendered-surface evidence from the real sync boundary:

```text
window:            1316 x 700 -> 1600 x 1000
flat ctx after sync: 980 x 616
render resolves:    1264 x 916
```

A PNG of the resized render surface was saved at `C:\Users\amani\AppData\Local\Temp\opencode\window_resize_evidence.png`.

Regression coverage: `tests/test_window_resize.py` posts a real `VIDEORESIZE` event through `process_event_frame()` and asserts that the layout constants, flat mirror, and holder-resolved render surface all expand to `1264 x 916`. It also checks the legacy-context fallback.

### Acceptance criteria

1. Maximising or resizing the window updates all live layout constants.
2. The flat `cairo_surface` mirror is refreshed from `relayout()`.
3. `render_scene()` resolves the current holder surface rather than a stale snapshot.
4. Collapsing/expanding the right panel still rebuilds the canvas surface.
5. A regression test drives a real `VIDEORESIZE` event through the extracted event boundary.

---

## Secondary findings

These remain separate from the nine regressions above:

1. **`ui.ref_opacity_drag` is not a declared `UiCacheState` field.** `src/controllers/panel/reference_image_actions.py:28` writes it, while `src/controllers/mouse_motion/guide_cut_motion.py:29` reads it. Add it to the owning typed state (or move it to the reference-image state) and update both sides consistently.
2. **Panel scroll coordinates may be mixed.** `src/views/panel.py:41` subtracts `panel_scroll` from the initial `y`, then the scrollbar calculation adds `_scroll` again. Verify scrolling and dragging of the scrollbar in a tall panel.
3. **Bottom-bar selection labels may be stale.** `src/views/toolbar.py:88` reads `selection_submode` from the render-state dictionary; verify that the Transform/Nodes/Curve label changes with the panel arrows.
4. **Plain `Esc` exits the app as a fallback.** `src/controllers/input/shortcut_keys.py:11-27` clears active UI state first, but sets `ctx.running = False` when nothing else can be cancelled. Confirm that this is intended.

## Validation approach

The findings were established using:

- the previous headful run and automated UI-event sweep;
- static inspection of typed state ownership and command dispatch;
- source comparison against baseline `0bc4a22`;
- direct command-registry probes that checked both the returned “handled” value and the resulting state;
- a static global-reference scan over `src/controllers` to catch mechanically split handlers that still used removed locals;
- an instrumented draw-call probe that records every blit/fill after each control is drawn and reports covered controls;
- a published-rect probe that intersects all visible panel rects across draw/selection/style scenarios;
- focused panel, drag, and render-layout regression tests in the current working tree.

Run the repository test suite with:

```powershell
python -m unittest discover -s tests -t .
```

After fixing RESP-02, runtime assertions cover each affected menu command and its matching keyboard shortcut. After integrating RESP-01, panel tests use the live typed application state. After fixing RESP-03, `tests/test_fill_color_panel_hits.py` covers the Curve/Transform color clicks. After fixing RESP-04, `tests/test_color_picker_drag.py` covers SV and hue drags through the UI-drag session path. After fixing RESP-05, `tests/test_gradient_stop_preservation.py` covers second-stop edits, fill-type cycling, and gradient-stop drags. After fixing RESP-06, `tests/test_slider_drag_and_layout.py` covers typed drag-sync, real opacity drag motion, and empty-selection layout. After fixing RESP-07, `tests/test_panel_control_overlaps.py` covers real panel renders for the shadow stepper and all four curve-style sections. After adding the style guide, `tests/test_ui_spacing.py` unit-tests the validator and renders every panel state. After fixing RESP-08, `tests/test_redraw_preview.py` checks the real Cairo render with and without live redraw points and verifies that exports stay clean. After fixing RESP-09, `tests/test_window_resize.py` posts a real `VIDEORESIZE` event through the extracted event boundary and checks that the holder-resolved render surface matches the new canvas dimensions.

The spacing probe covered 19 rendered panel states and reported `spacing<8px: 0` in every state. The instrumented draw-overlap probe covered 18 panel states and reported `TOTAL UNEXPECTED OVERLAPS: 0`; the only nested hits are intentional children inside composite controls.

Targeted regression results after the RESP-09, RESP-08 and spacing fixes:

```text
python -m unittest tests.test_slider_drag_and_layout -v
Ran 4 tests in 0.016s

OK

python -m unittest tests.test_gradient_stop_preservation -v
Ran 3 tests in 0.007s

OK

python -m unittest tests.test_color_picker_drag -v
Ran 2 tests in 0.001s

OK

python -m unittest tests.test_panel_control_overlaps -v
Ran 5 tests in 0.081s

OK

python -m unittest tests.test_ui_spacing -v
Ran 10 tests in 0.142s

OK

python -m unittest tests.test_redraw_preview -v
Ran 2 tests in 0.001s

OK

python -m unittest tests.test_window_resize -v
Ran 2 tests in 0.009s

OK
```

The custom AST/symtable undefined-global scan over `src/controllers` reports no undefined names in the extracted panel or motion handlers. The only remaining hits are pre-existing dynamic wildcard-import globals in `app_controller.py`, `coordinates.py`, and `mouse_button_down.py`.

Current full-suite result after all nine fixes:

```text
Ran 363 tests in 5.599s

OK
```
