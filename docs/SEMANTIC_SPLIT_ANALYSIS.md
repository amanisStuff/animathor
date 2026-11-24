# Semantic Split Analysis: Quantitative-Split God Functions

## Scope

This document analyzes the controller/view "god functions" that were previously split **quantitatively** (by line ranges / chunk size) and proposes a **semantic** split by responsibility. It is grounded in the current codebase, especially:

- `src/controllers/app_controller.py` — `main()` orchestration and state plumbing
- `src/controllers/event_loop.py` — extracted event dispatch
- `src/controllers/key_down.py` — `handle_keydown()`
- `src/controllers/mouse_button_down.py`, `mouse_button_down_canvas.py` — canvas/panel click dispatch
- `src/controllers/mouse_button_up.py` — `handle_mousebuttonup1()`
- `src/controllers/mouse_motion.py`, `mouse_motion_parts.py`, `mouse_motion_parts2.py`
- `src/controllers/render_frame.py` — `render_frame()`
- `src/controllers/mbd_panel_*.py`, `mbd_panel_*_parts.py` — panel click slices
- `src/controllers/menu_dispatch_controller.py`, `menu_actions.py`, `menu_actions_view.py`
- `src/views/panel_select_parts*.py` — quantitatively split panel rendering
- `tools/_extract_block.py`, `tools/_extract_render.py`, `tools/_split_panel_mods.py` — extraction scripts

The complexity report (`python tools/complexity_score.py --top 20`) still flags these areas as high-complexity, confirming that line-count splitting did not remove the underlying responsibility concentration.

## What "Quantitative Split" Means Here

The extraction scripts show the current pattern:

1. Select a line range from a large function.
2. Parse it, detect locals read/written, and rewrite names to `ctx.<name>`.
3. Write a new module with `def handler(ctx, event=None): ...`.
4. Replace the original block with:
   - build a `types.SimpleNamespace()` from `locals()`
   - call the extracted handler
   - copy selected fields back via `if hasattr(_ex_ctx, ...): name = _ex_ctx.name`
5. For panel handlers, split by function boundaries into `_a/_b/_c` and then into `_p1/_p2/_parts`.

This is visible in:

- `event_loop.py`: `_ev_keydown`, `_ev_mbd1`, `_ev_mbup1` copy almost the whole local state into a `SimpleNamespace`, call a handler, then sync dozens/hundreds of fields back.
- `render_frame.py`: called as `render_frame(ctx)` from `app_controller.main()`, followed by ~170 `if hasattr(_rf_ctx, ...): ... = _rf_ctx...` assignments.
- `mbd_panel_b.py` / `mbd_panel_c.py`: dispatch to `handle_b_part1/2/3` or `handle_c_tabs_filltype/stops/picker`, where names reflect chunking/order rather than domain.
- `mouse_motion_parts.py` / `mouse_motion_parts2.py`: motion logic split by part number.

### Why this split is harmful

| Problem | How it appears now | Consequence |
|---|---|---|
| Responsibility is still concentrated | `handle_keydown`, `_handle_canvas_click`, `handle_mousebuttonup1`, `render_frame` still own many unrelated decisions. | High cognitive load; changes risk regressions. |
| State boundary is implicit | `ctx` is a bag of almost every app variable. | No contract; hard to know what a handler reads/writes. |
| Sync plumbing is duplicated and fragile | Large `hasattr` sync lists in `app_controller` and `event_loop`. | Missing sync field causes subtle state loss; adding state requires editing many lists. |
| Names describe chunks, not domains | `mbd_panel_a_p2`, `handle_bc_part3`, `mm_part3`. | Hard to navigate by intent; poor ownership. |
| Star imports hide dependencies | `from models import *`, `from views import *`. | Unclear API, name collisions, static analysis blind spots. |
| Testing targets shape, not behavior | Handlers require constructing a full ctx replica. | Unit tests become integration tests by accident. |

---

## Semantic Domains and Recommended Split

The table below maps current quantitative units to semantic domains. The sections after it detail each domain.

| Semantic domain | Current quantitative locations | Primary responsibility |
|---|---|---|
| App lifecycle & frame orchestration | `app_controller.main` | Startup, state ownership, frame loop, layout, high-level wiring |
| Input/event routing | `event_loop.process_events`, `_ev_*` | Translate pygame events into semantic intents/handler calls |
| Keyboard commands & input modes | `key_down.handle_keydown` | Mode-aware key handling, shortcuts, text/numeric/formula input |
| Canvas tool interactions | `mouse_button_down_canvas._handle_canvas_click`, parts of mouse up/motion | Drawing, eraser, bucket, cutter, text placement, bezier pen |
| Selection/manipulation | canvas click selection branches, mouse motion transform/node/curve drag, mouse up commit | Select, marquee, move, transform, node edit, curve edit |
| Panel/UI command handling | `mbd_panel_a*.py`, `mbd_panel_b*.py`, `mbd_panel_c*.py`, `*_parts.py` | Panel button/slider/picker actions by UI domain |
| Overlay/render composition | `render_frame.render_frame`, view panel parts | Build render state, draw scene/UI/overlays, sync UI caches |
| Menu/command execution | `menu_dispatch_controller.py`, `menu_actions.py`, `menu_actions_view.py` | Named app commands invoked by menu/shortcuts/UI |
| Cross-cutting state/contracts | ctx construction everywhere | Shared app state, mutation protocol, geometry/view helpers |

---

## 1. App Lifecycle & Frame Orchestration

### Current functionality

`app_controller.main()` currently performs all of these:

- **Bootstrap**: initializes pygame, window, clock, fonts, cairo surface.
- **Layout**: defines `relayout()` and recalculates canvas/panel geometry.
- **State ownership**: declares almost all mutable app state as local variables (strokes, selection, tool mode, draw options, UI caches, drag state, export/workspace state, etc.).
- **Service adapters**: defines local helper closures (`push_undo`, `do_undo`, bucket/xform/text/bezier ctx builders and sync functions).
- **Per-frame derived state**: sanitizes selection, computes primary selection, bbox, active curve, and builds the large `state` dict consumed by views.
- **Menu command wiring**: defines `run_menu_action()` that builds a `SimpleNamespace`, calls menu dispatch, then copies fields back.
- **Frame execution**: runs `process_event_frame()`, calls `render_frame()`, then manually syncs ~170 fields back from render ctx.

### How it performs it now

- A single function owns long-lived mutable state through closure variables.
- Cross-module calls use ad-hoc ctx objects (`SimpleNamespace`) created from locals.
- The view layer receives a large `state` dict with both model data and UI cache rects.
- After rendering, controller state is reconstructed by `hasattr` checks over a hard-coded field list.

### Why this is a god function

It combines composition root, state container, frame scheduler, command router adapter, and view-model mapper. The quantitative extraction of rendering/event loop reduced line count but left `main()` as the central state bottleneck.

### Better semantic split

| New semantic unit | Responsibility | Suggested interface |
|---|---|---|
| `controllers/app.py` or `AppController` class | Own top-level lifecycle: init, run loop, shutdown. | `run() -> int` |
| `controllers/state.py` (`AppState` dataclass) | Typed app/document/UI/interaction state. | nested dataclasses: `DocumentState`, `SelectionState`, `ToolState`, `ViewportState`, `UiState` |
| `controllers/frame.py` | One frame: gather input, update, render. | `step(state, deps) -> FrameResult` |
| `controllers/layout.py` | Window/canvas/panel/ruler geometry. | `relayout(state.viewport, collapsed) -> ViewportLayout` |
| `controllers/state_sync.py` or remove entirely | Replace ctx sync with explicit return values. | handlers return `Patch`/mutations or mutate typed state |

**Better method:** move from "locals + ctx bag" to an explicit `AppState` object passed by reference, with handlers returning small typed result objects only where needed (e.g., `KeyResult(consumed=True)`). This eliminates most sync-back code and makes state ownership visible.

---

## 2. Input/Event Routing

### Current functionality

`event_loop.process_events()` handles:

- Window lifecycle: quit, resize.
- Global pointer/wheel behavior: panel scroll, canvas zoom-to-cursor.
- Slider routing: max points slider, cut gap slider, width slider with style-target rules.
- Key dispatch: delegates to `_ev_keydown`.
- Mouse dispatch: middle-drag pan, right-click shape menu, left click down/motion/up delegation.
- Special-case style target selection for width slider (transform vs component vs point width).

### How it performs it now

- It is an extracted block that still expects `ctx` to contain almost every variable.
- `_ev_keydown/_ev_mbd1/_ev_mbup1` each create a `SimpleNamespace`, copy locals, call handler, and sync back long field lists.
- The dispatch is imperative and order-dependent.

### Why this is quantitatively split

The extraction moved code out of `main`, but the interface is still "the whole app". The sync lists are a manual serialization of app state.

### Better semantic split

| New semantic unit | Responsibility | Suggested interface |
|---|---|---|
| `controllers/input/event_router.py` | Top-level pygame event dispatch. | `route(event, state, services) -> bool/None` |
| `controllers/input/wheel.py` | Panel scroll and canvas zoom behavior. | `handle_wheel(event, state, viewport)` |
| `controllers/input/mouse_router.py` | Button/motion routing by active interaction. | `handle_mouse_down/move/up(...)` |
| `controllers/input/drag_session.py` | Active drag lifecycle. | `DragSession.on_down/on_move/on_up` |

**Better method:** use an interaction/session model. On mouse down, create an active interaction object (`PanDrag`, `TransformDrag`, `BezierPenDrag`, `CutDrag`, etc.) stored in state; mouse motion/up dispatch to the active session first. This removes large "if dragging..." branches spread across handlers and avoids re-deriving intent from many booleans.

---

## 3. Keyboard Commands & Input Modes

### Current functionality

`key_down.handle_keydown()` is a priority chain for:

- **Modal dismissals**: close menu/help/export dialog on Escape.
- **Text entry mode**: capture printable chars, backspace, Enter commit, Escape cancel, Ctrl+Up/Down font size.
- **Transform numeric field mode**: digits/sign/dot input, backspace, Enter commit, Escape cancel, arrows nudge.
- **Bezier pen mode**: Enter finish, Escape cancel, Backspace remove last anchor.
- **Wave formula mode**: edit formula text; Enter/Escape finish.
- **Custom wave draw mode**: Enter/Escape finish drawing.
- **Global shortcuts**: file/edit/view/tool/selection commands through `run_menu_action`.
- **Editing shortcuts**: delete, cycle submode, points-per-curve adjust, shift-snap behavior.

### How it performs it now

- One function ordered by priority, with early `return 'continue'`.
- It mixes input capture, command execution, and state mutation.
- It reaches into many unrelated state fields (`text_entry`, `xform_field_*`, `bezier_pen`, `wave_formula_focus`, selected stroke internals).

### Better semantic split

| New semantic unit | Responsibility | Suggested interface |
|---|---|---|
| `controllers/input/keymap.py` | Global shortcut map to command IDs. | `resolve(event, state) -> CommandId | None` |
| `controllers/input/text_input.py` | Text tool typing behavior. | `handle_text_key(event, text_entry) -> InputResult` |
| `controllers/input/numeric_field_input.py` | Transform field editing/nudging. | `handle_xform_key(event, field_state, selection)` |
| `controllers/input/bezier_pen_input.py` | Bezier pen keyboard controls. | `handle_bezier_key(event, pen_state)` |
| `controllers/input/wave_input.py` | Wave formula/custom-draw key capture. | `handle_wave_key(event, wave_ui_state, stroke)` |
| `controllers/commands/execute.py` | Execute command IDs. | `execute(cmd, state, services)` |

**Better method:** implement an **input mode stack** or mode priority list. Each mode can consume or pass a key event. Example order: modal dialog > text entry > numeric field > bezier pen > wave formula > global keymap. This makes priority explicit and prevents tool shortcuts from leaking into text/input modes.

---

## 4. Canvas Tool Interactions

### Current functionality

`mouse_button_down_canvas._handle_canvas_click()` handles canvas left-click by mode:

- **Draw mode**: alt-drag reference image, eraser hit erase, bucket fill region creation, cutter swipe start, text placement/caret, bezier pen anchor placement/close/double-click finish, freehand/shape draw start.
- **Redraw curve mode**: start redraw stroke with fixed endpoints.
- **Selection mode**: eyedropper sample/apply, curve selection/cut/repeat-pick, transform handle/pivot/gradient handle hit-testing, object selection/group selection, marquee start, node selection in nodes mode.

### How it performs it now

- Deeply nested `if/elif` by `tool_mode`, then `draw_tool`, then selection submode.
- Direct mutation of strokes, selection, drag state, and UI flags.
- Contains geometry operations, style-copy logic, and hit-testing inline.

### Why this is a god function

It is a dispatcher, hit-test engine, tool behavior implementation, and selection policy all in one function (410 lines, very high branching).

### Better semantic split

Split by **active tool/interaction**, not by arbitrary line blocks:

| New semantic unit | Responsibility | Suggested interface |
|---|---|---|
| `controllers/tools/eraser.py` | Erase curve at point. | `on_down(ctx/state, pos)` |
| `controllers/tools/bucket_fill.py` | Geometric fill creation. | `fill_at_point(doc, pos, fill_color)` |
| `controllers/tools/cutter.py` | Start/preview cut swipe. | `begin_cut(interaction, pos)` |
| `controllers/tools/text_tool.py` | Place/edit text entry. | `place_text(state, pos)` |
| `controllers/tools/bezier_pen.py` | Anchor placement, handle drag, close/finish. | `PenTool.on_down/on_drag/on_up/on_key` |
| `controllers/tools/freehand_shape.py` | Start/commit drawn stroke or shape. | `begin_draw`, `commit_draw` |
| `controllers/selection/hit_test.py` | Stroke/component/point/handle hit tests. | pure query functions |
| `controllers/selection/transform_handles.py` | Scale/rotate/pivot/gradient handle interactions. | `hit_handle`, `begin_drag` |
| `controllers/selection/curve_mode.py` | Curve selection, cut mode, repeat pick. | `select_curve(...)` |
| `controllers/selection/node_mode.py` | Point hit/select/drag start. | `select_node(...)` |

**Better method:** use a **tool strategy/state machine** registry keyed by `(tool_mode, draw_tool, selection_submode)`. Each tool implements `pointer_down/move/up/cancel`. Mouse event routing becomes a small dispatch table; each tool owns only its state transitions.

---

## 5. Panel/UI Command Handling

### Current functionality

The panel click path is quantitatively split across many files:

- `mbd_panel_a.py` -> `_handle_panel_click_a_p1/p2/p3`
- `mbd_panel_b.py` -> `handle_b_part1/2/3` and color parts
- `mbd_panel_c.py` -> `handle_c_tabs_filltype/stops/picker`
- `mbd_panel_*_parts.py` contain large domain-mixed handlers

Based on names and complexity, these cover panel interactions such as draw/tool options, wave/displacement controls, color/fill/stroke editing, gradient stops/pickers, transform/selection options, and miscellaneous panel buttons.

### How it performs it now

- Entry handlers dispatch by part number.
- Parts operate on `ctx` and inspect hit rects cached in state.
- Color/stroke/wave logic is fragmented across multiple files with non-semantic names.
- Similar patterns repeat: find hit rect, mutate selected stroke/component/style, update picker state.

### Better semantic split

Split by **panel domain**, with each module owning its rect contract and mutation:

| New semantic unit | Responsibility | Current quantitative chunks |
|---|---|---|
| `controllers/panel/tool_options.py` | Draw tool, shape, snap, cutter gap, trace/boost options. | parts of `mbd_panel_a*` |
| `controllers/panel/fill_picker.py` | Fill/stroke tabs, HSV picker, alpha, swatches, eyedropper. | `mbd_panel_b_color*`, `mbd_panel_c_tabs_filltype/picker` |
| `controllers/panel/gradient_stops.py` | Gradient type, stop add/remove/select/position. | `mbd_panel_c_stops`, related color parts |
| `controllers/panel/stroke_style.py` | Width, cap/join/dash, markers, stroke color targets. | `mbd_panel_b_parts`, color parts |
| `controllers/panel/effects_wave.py` | Wave/displacement/repeat/thickness add/remove/edit. | `mbd_panel_b_parts` (`_b3_wave_*`) |
| `controllers/panel/transform_fields.py` | X/Y/W/H/R fields, align/distribute, mirror, opacity. | `mbd_panel_a*`/transform-related parts |
| `controllers/panel/selection_actions.py` | Path ops, bool ops, elevation, curve actions. | scattered panel parts |

**Better method:** define a small `PanelAction` contract, e.g. `handle_click(event, ui: PanelUiState, app: AppState) -> bool`. Each module checks only its own rects and returns handled/not handled. The panel dispatcher becomes a flat list of domain handlers in priority order. Also colocate rect names/constants with the handler or a shared `panel_rects` schema.

---

## 6. Drag/Motion Handling

### Current functionality

Mouse motion is split into `mouse_motion.py` and `mouse_motion_parts.py/parts2.py` (`mm_part1/2/3`). From names and codebase behavior, it covers:

- Ruler/guide dragging and guide creation/removal.
- Space/pan dragging.
- Bezier pen handle drag.
- Cutter swipe point accumulation.
- Reference image drag.
- Transform handle dragging (scale/rotate/skew), pivot drag, pending transform-toggle threshold.
- Gradient handle dragging.
- Node/point dragging and control-point behavior.
- Marquee update.
- Slider/picker drag updates.

### How it performs it now

- Split by numeric parts, not by drag target.
- Uses `ctx` for all transient drag state.
- Likely contains repeated guards like "if dragging X ... else if dragging Y...".

### Better semantic split

| New semantic unit | Responsibility |
|---|---|
| `controllers/drag/pan_drag.py` | Middle mouse/space pan. |
| `controllers/drag/guide_drag.py` | Ruler guide drag/create/remove. |
| `controllers/drag/transform_drag.py` | BBox scale/rotate/skew, pivot, toggle threshold. |
| `controllers/drag/gradient_drag.py` | Gradient handle movement. |
| `controllers/drag/node_drag.py` | Anchor/control point movement, symmetry constraints. |
| `controllers/drag/tool_drag.py` | Freehand draw, cutter, bezier handle, ref image drag. |
| `controllers/drag/ui_drag.py` | Panel sliders/pickers/opacity/gradient stop position drags. |

**Better method:** create an **active drag session** on mouse down. `mouse_motion` should mostly do:

```py
if state.active_drag: state.active_drag.move(event.pos, state)
```

This avoids global drag priority chains and makes each drag type testable in isolation.

---

## 7. Mouse Release / Commit

### Current functionality

`mouse_button_up.handle_mousebuttonup1()` finalizes interactions:

- Guide drag removal when released over ruler.
- Bezier pen mouse-up: close path when dragging first anchor, otherwise end handle drag.
- Cutter commit: append final point, call `cut_strokes_with_path`, update selection, one-shot curve-cut mode reset.
- Pan/pivot/transform/gradient drag end.
- Transform click-without-drag toggles scale/rotate.
- Marquee finalize: select intersecting strokes/groups.
- Redraw-curve commit: finalize points, push undo, replace component.
- Draw commit: shape detection/fitting, straight line, or freehand bezier fitting; create stroke(s), merge/close, arrowhead handling.
- Cleanup: clear drag flags, slider/picker drag state, sync slider value.

### How it performs it now

- A single function handles commit logic for many unrelated tools.
- It performs model mutations (stroke creation/cut/redraw) directly in the controller.
- It contains subtle behavior encoded in ordering (e.g., transform toggle only if not moved).

### Better semantic split

| New semantic unit | Responsibility |
|---|---|
| `controllers/commit/cut_commit.py` | Finalize cutter swipe and selection update. |
| `controllers/commit/draw_commit.py` | Convert drawn points into shape/freehand/line stroke(s). |
| `controllers/commit/redraw_commit.py` | Replace selected component with redrawn points. |
| `controllers/commit/selection_commit.py` | Marquee finalize, click-toggle finalize. |
| `controllers/drag/session.py` | Common `end()` behavior for drag sessions. |

**Better method:** pair each mouse-down interaction with a commit object. For example, `DrawSession` stores raw points and options; `on_up()` returns a `CreateStrokeCommand` or applies a document mutation through a service. This localizes the down/move/up lifecycle and makes cancel/commit symmetric.

---

## 8. Render Frame & UI Sync

### Current functionality

`render_frame.render_frame()` currently does:

- **Scene preparation**: choose active drawing points, build library preview strokes, build live text preview stroke.
- **Transform/gradient overlay prep**: compute effective pivot, gradient edit handles, ensure OBBs.
- **Scene render**: call `draw_scene(...)`, blit cairo frame.
- **Rulers/guides overlay**: draw top/left rulers and ticks when enabled.
- **Interaction overlays**: cutter preview, marquee rectangle.
- **UI render**: left toolbar, panel, panel toggle, bottom shape toolbar, shape menu, marker dropdown.
- **State sync back**: copy dozens of panel rects/cache values from `state` back to `ctx`.
- **Post-frame sync**: update width slider from selected stroke.
- **Top-level overlays**: menu bar, shortcuts overlay, export dialog.
- **Present frame**: `pygame.display.flip()` and `clock.tick(120)`.

### How it performs it now

- Mutates a large ctx in place.
- Treats `state` as both input and output for UI caches.
- The controller owns view-cache synchronization details.

### Better semantic split

| New semantic unit | Responsibility | Suggested interface |
|---|---|---|
| `controllers/render/scene_state.py` | Build `RenderScene` (strokes, active points, preview text, pivot, gradient handles). | pure-ish builder from app state |
| `controllers/render/canvas_overlay.py` | Rulers, guides, cutter preview, marquee. | draw functions |
| `controllers/render/ui_frame.py` | Compose panel/toolbars/menus/dialogs. | returns `UiFrameOutput` |
| `views/panel_state.py` | Typed panel rect/cache output instead of ad-hoc dict keys. | dataclass |

**Better method:** make rendering produce an explicit output:

```py
ui_out = render_ui(screen, fonts, app_state)
app_state.ui = app_state.ui.with_rects(ui_out.rects)
```

Avoid writing individual rect fields back through `ctx`. The view can return a typed `PanelRects` object; the controller stores it as one field. This removes the largest sync wall in `app_controller.main()`.

---

## 9. Menu/Command Execution

### Current functionality

- `menu_dispatch_controller.py` dispatches menu keys to `_menu_file/_menu_edit/_menu_view/_menu_tools`.
- `menu_actions.py` and `menu_actions_view.py` implement command behavior.
- `app_controller.run_menu_action()` wraps dispatch in `SimpleNamespace` copy/sync.
- `key_down.py` invokes many commands through `run_menu_action`.

### How it performs it now

- Commands are stringly-typed keys.
- Command implementations depend on broad app state.
- UI labels/menu structure and command semantics are partly coupled.

### Better semantic split

| New semantic unit | Responsibility |
|---|---|
| `controllers/commands/ids.py` | Command IDs/constants/enums. |
| `controllers/commands/registry.py` | Register and execute commands. |
| `controllers/commands/file_commands.py` | New/open/save/export/import. |
| `controllers/commands/edit_commands.py` | Undo/redo/copy/paste/duplicate/delete/group. |
| `controllers/commands/view_commands.py` | Zoom, fit, rulers/grid/panels/workspace. |
| `controllers/commands/tool_commands.py` | Tool switching, snapping, eyedropper. |

**Better method:** use a **command registry** where both menus and keyboard shortcuts bind to the same command IDs. Commands accept `(state, services)` and return a small result. This removes duplicate shortcut/menu logic and gives a clean place for undo/redo policy.

---

## 10. Cross-Cutting: Replace `ctx` Bag with Typed Contracts

### Current functionality

The `ctx` pattern is used as a compatibility layer after quantitative extraction. It allows extracted files to behave like they still live inside `main()`.

### How it performs it now

- Build `SimpleNamespace` from `locals()` or selected fields.
- Mutate `ctx.<field>`.
- Sync back with hard-coded field names and `hasattr`.
- Rely on star imports so extracted code can call model/view helpers.

### Better semantic split / method

This is not a feature domain; it is an architectural seam that should be removed.

| Better method | Why |
|---|---|
| Typed `AppState` dataclasses | Explicit fields, IDE/static checks, no sync lists. |
| Focused handler params | `handle_text_key(event, text_state)` instead of whole app ctx. |
| Command/result objects | Handlers return intent; caller applies it. |
| Explicit service objects | Pass `HistoryService`, `SelectionService`, `Viewport`, `Renderer` as dependencies. |
| Remove star imports in controllers | Use explicit imports; keeps dependency direction clear. |

**Pragmatic migration path:** keep `app_controller.main()` as composition root, but introduce `AppState` first. Then migrate one semantic domain at a time (keyboard, then mouse-up commit, then tool handlers), replacing ctx sync lists with direct state mutation or typed patches.

---

## Suggested Target Layout (Semantic)

```text
src/controllers/
  app.py                     # lifecycle / main loop
  state.py                   # AppState + nested state dataclasses
  layout.py                  # relayout / viewport calculations
  commands/
    registry.py
    file_commands.py
    edit_commands.py
    view_commands.py
    tool_commands.py
  input/
    event_router.py
    key_router.py
    keymap.py
  tools/
    bezier_pen.py
    freehand.py
    eraser.py
    bucket_fill.py
    cutter.py
    text_tool.py
  selection/
    hit_test.py
    marquee.py
    transform.py
    nodes.py
    curves.py
  drag/
    session.py
    pan_drag.py
    transform_drag.py
    node_drag.py
    gradient_drag.py
  panel/
    dispatch.py
    tool_options.py
    fill_picker.py
    gradient_stops.py
    stroke_style.py
    effects.py
    transform_inspector.py
  render/
    frame.py
    scene_builder.py
    overlays.py
```

This layout aligns with the existing MVC direction in `docs/ARCHITECTURE.md`: models remain pure data/geometry, views render, controllers orchestrate and mutate state.

## Prioritization

If this is implemented incrementally, prioritize by risk and payoff:

1. **Introduce `AppState` + remove render sync wall** — highest leverage; deletes large `hasattr` sync block.
2. **Split `key_down.handle_keydown` by input mode** — clear boundaries, low visual risk.
3. **Split mouse-up commit by interaction type** — isolates irreversible document mutations.
4. **Refactor canvas mouse-down into tool/selection handlers** — biggest behavior complexity reduction.
5. **Reorganize panel handlers by domain** — improves feature ownership; can be done after rect contracts are clarified.
6. **Convert active drags to interaction sessions** — removes cross-handler flag coupling.

## Notes

- This analysis intentionally focuses on semantic boundaries, not a big-bang rewrite. The current quantitative split can be used as a migration scaffold: move code, then replace ctx plumbing with typed state.
- The `app_broken_wave.py` syntax error reported by the complexity script is unrelated to these controller splits but should be kept out of scoring inputs or repaired if it is meant to be active code.
- View files like `panel_select_parts*.py` show the same quantitative pattern on the rendering side; they should be split by panel section/component once controller-side panel domains are defined, so rect production and hit handling share the same semantic ownership.


## Implementation Status (incremental)

Applied with passing tests (282 OK):
- Semantic handler splits: `key_down` -> `controllers/input/*`; `mouse_button_up` -> `controllers/commit/*`; `mouse_button_down_canvas` -> `controllers/tools/*` + `controllers/selection/*`.
- Render sync wall replaced in `app_controller.main` by automatic frame-locals sync from render ctx (no hardcoded render sync field list in the hot path). `ctx_sync.RENDER_SYNC_FIELDS` remains as legacy reference.
- Command registry/IDs added (`controllers/commands/*`) and shortcut keys use `CMD.*`.
- `AppState` contract added (`controllers/app_state.py`) with live frame bridge; sync fields are auto-derived from typed substate dataclasses. `app_controller.main` seeds `AppState` before the loop and pushes `AppState` -> locals at loop start for `AppState` sync fields (primary slice for that domain), then syncs locals -> `AppState` after events/render. Concrete primary-owner slice, but not yet sole source of truth for all app state.
- Panel/view semantic relocations with compat wrappers (`controllers/panel_actions/*`, `views/panel_domain_*.py`, `views/panel_domains.py`). Star-import removal/explicit contracts applied across `mbd_panel_*`, `panel_actions/*`, and `panel_domain_*.py`. Explicit-contract core functions added (with compat ctx-bag wrappers) in `views/panel_domain_style.py`, `views/panel_domain_selection.py` (`render_selection_a`, `render_distribute_and_path_section`), `views/panel_domain_style_effects.py`, `views/panel_domain_color.py` (`render_no_selection_state`, `render_color_section`, `render_color_picker_section`, `render_help_lines`), and `views/panel_domain_color_detail.py` (`render_color_tail_section`); many other internals still use legacy ctx-bag/sync_in-sync_out patterns and full semantic ctx-contract rewrite remains.
- DragManager/DragSession infrastructure wired; session-owned commits/moves for pan, guide, marquee, pivot, ref, transform, gradient, cutter, draw, redraw. Added `controllers/drag/ui_session.py` and wired `UiDragSession` in `event_loop` for UI/picker/wave-slider/opacity/fill-stop/bucket drag flags. `BezierPenSession` is DragManager-managed; MBD begin remains tool-state special-cased, but motion begin/end is normalized through `DragManager.modal_motion(...)` in `event_loop` (no inline bezier motion branch).
- Ctx sync plumbing reduced: `event_loop` uses automatic `_sync_all`, `menu_dispatch_controller` auto-syncs non-callback fields, `app_frame_controller` auto-syncs all frame locals and syncs `app_state` when present, and `app_controller` menu action/render paths auto-sync. `controllers/ctx_sync.py` slimmed to frame-locals bridge helpers only (dead per-handler sync field lists removed). Removed redundant `sync_in/sync_out` frame-locals roundtrips from thin explicit-core compat wrappers in `views/panel_domain_selection.py`, `views/panel_domain_style.py`, `views/panel_domain_style_effects.py`, and `views/panel_domain_color.py`. Fixed `app_frame_controller.init_ui_caches` pygame lookup to fall back to frame globals when absent from frame locals (runtime `AttributeError: 'NoneType' object has no attribute 'Rect'`).

Remaining (requires larger coordinated refactor):
- Make typed `AppState` the sole source of truth in `app_controller.main` (remove legacy locals/ctx-bag ownership). Current state is a live bidirectional bridge, not sole ownership.
- Fully rewrite remaining `mbd_panel_*`/`panel_domain_*` internals by semantic domain (not just relocation/wrappers). Current panel_actions/panel_domain modules still contain legacy star-import/ctx-bag internals moved behind semantic entry points.
- Convert all remaining drag interactions to fully session-owned move/commit lifecycles, including UI/picker drags and any remaining special-case bezier/transform-toggle edge flows.
- Fully eliminate remaining command/ctx sync plumbing across legacy boundaries, including `ctx_sync.py` legacy field lists and any remaining frame-locals bridge code once AppState becomes primary.
