# Bug Report — Animathor (Cairo Vector Drawing app)

**Status:** App runs (see below), all functionality exercised; findings below.

**How this was run:**

1. **Headful run:** `python app.py` (display `:0`). Window runs at 1920×1040. App is
   still running in the background (see "Running state").
2. **Automated UI bug-hunt harness:** runs the app in-process, injects pygame
   events (grid of ~1500 left-button clicks, right-click grid, double clicks,
   hover sweep, keyboard sweep, key combos with mods, mouse-wheel sweep, drag
   gestures across canvas/panel, resize events, targeted clicks on top bar,
   left bar, canvas, panel, bottom bar) and records any exception raised inside
   the app loop. When the loop dies it is restarted and the sweep continues
   (with per-crash monkeypatches to find further bugs).
3. **Static analysis:** AST checks of typed state classes (`ToolState`,
   `SelectionState`, `UiCacheState`, `DocumentState`, `CommandContext`, …)
   against attribute accesses and hit-rect keys.

---

## Confirmed crash (blocking — should be fixed first)

### Bug 1 — `AttributeError: 'ToolState' object has no attribute 'selection_submode'`

- **Repro:** run the app, click anywhere on the right panel while the tool mode
  is "Selection" (the grid sweep hit it within ~200 clicks). The app thread
  dies; the window freezes (with the exception logged to stdout).
- **Where:** `src/controllers/panel/align_distribute.py:67` in
  `align_distribute_typed()` — the condition
  `tools.tool_mode == "selection" and tools.selection_submode == "nodes" and any(state.get(k, Rect(0,0,0,0)).collidepoint(event.pos) for k in ("path_close_rect", ...))`
  raises because `tools` is a `ToolState` that has no `selection_submode`.
  Callers: `_handle_panel_click_a_p3` in the same file (line ~198).
- **Cause:** the refactor moved `selection_submode` from `ToolState`
  (`src/controllers/app_state.py`, ToolState class) to `SelectionState`
  (`src/controllers/app_state.py:51`, SelectionState class, field
  `selection_submode: str = "transform"`), but many readers still do
  `tools.selection_submode`.
- **Same-class readers found by the static scan** (all of the form
  "attribute moved but some readers still use `tools.selection_submode`");
  the confirmed crash is `align_distribute.py:67`. Grep
  `src/` for `selection_submode` to enumerate them all — e.g.
  `mouse_motion/wave_motion.py`, `mouse_motion/transform_motion.py`,
  `input/*` files read it via the dispatch context, which mirrors AppState
  substates, so they should be re-checked for the owner that now holds the
  field.
- **Fix suggestion:** read the field from the owner: `selection.selection_submode`
  (pass/receive `SelectionState` where needed), or add `selection_submode`
  back to `ToolState` as a maintained default. After fixing, re-run the harness
  (`cd /tmp/opencode && python3 ui_bug_hunt_master.py`) — it reproduces this
  crash deterministically.

---

## Other findings (static review; no crash reproduced during the sweep)

### Bug 2 — `ui.ref_opacity_drag` is not a real `UiCacheState` field

- `src/controllers/panel/reference_image_actions.py:28` writes
  `ui.ref_opacity_drag = True` while the static scan shows `UiCacheState`
  (`src/controllers/app_state.py`) has no `ref_opacity_drag` field (it has
  `obj_opacity_drag`, `picker_drag_sv/hue/alpha`, `bucket_picker_drag`).
- `src/controllers/mouse_motion/guide_cut_motion.py:29` reads
  `ctx.ref_opacity_drag`; readers like this can `AttributeError` if the flag is
  not set first (dataclasses don't pre-create it).
- Suggested fix: move the flag to `UiCacheState` (or to `DocumentState.reference_image`
  state) and update the writer/reader pair.

### Things to verify manually (not reproduced by automation)

These are UI-layout/behavioral suspects found while reviewing key view files
(`src/views/panel.py`, `src/views/toolbar.py`, `src/views/widgets.py`). They
need eyes/clicks to confirm; the harness (click-only) did not trigger crashes
for them:

1. **Panel scroll coordinate mixing** — `src/views/panel.py:41` starts the panel
   content at `y = top + 18 - state["panel_scroll"]` but line 88 computes
   `content_bottom = y + _scroll` again; scrollbar math uses
   `max_scroll = max(0, content_bottom + 24 - cfg.HEIGHT)` which may be
   systematically off (double-counted offset). Worth a visual check while
   scrolling the long panel.
2. **Bottom-bar selection mode labels** — `src/views/toolbar.py:88` reads
   `state.get("selection_submode", "transform")`; if the selection substates
   were moved off the state dict, this label would always show "transform"
   (worth verifying what owns it now).
3. **App exits on plain ESC** — `src/controllers/input/shortcut_keys.py:27`
   (`ctx.running = False` as a fallback). Verify intended; if the app should
   keep running, remove the fallback.

---

## How to re-run the hunt

```
cd /tmp/opencode
python3 ui_bug_hunt_master.py        # runs ui_probe3.py rounds, records crashes
python3 ui_probe3.py                 # single round in foreground
```

Crash logs: `/tmp/opencode/round_logs/roundN.log`, `/tmp/opencode/crash_summary.txt`.

## Running state

- The app is running headed on display `:0` (relaunch: `python3 -u app.py`
  from `/home/gool/projects/animathor/animathor`; PID 28894).
- Screenshots were captured with `ffmpeg -f x11grab` (e.g.
  `/tmp/opencode/shot_main.png`, `/tmp/opencode/shot_final.png`).
  Note: this model does not support image input, so the screenshots were not
  visually inspected; the report above is based on the runtime harness + static analysis.
