# Semantic Split — Application Plan

> Companion to `docs/SEMANTIC_SPLIT_ANALYSIS.md` (the analysis).
> This document converts that analysis into an **executable, phased plan** for
> applying the semantic split, and tracks what has already landed versus what
> remains.

## 1. Objective of this plan

Take the quantitative line-range splits (with the `ctx` SimpleNamespace bag and
`hasattr` sync-back pattern) that were done as extraction scaffolding, and move
the codebase to the **semantic split** the analysis proposes — handlers organized
by responsibility/domain, typed state ownership, session-based drags, command
registry — while keeping the app behavior-preserving and fully tested.

## 2. Inputs reviewed

- `docs/SEMANTIC_SPLIT_ANALYSIS.md` — scope, semantic domains, per-domain
  "better semantic split" tables, suggested target layout, prioritization
  (risk/payoff order), and the incremental implementation status.
- `src/controllers/**` — current post-split module layout (evidence gathered
  2026-11-24).
- `src/controllers/app_state.py`, `src/controllers/ctx_sync.py`,
  `src/controllers/app_frame_controller.py`, `src/controllers/event_loop.py`,
  `src/controllers/menu_dispatch_controller.py`.
- `src/controllers/commands/**`, `src/controllers/drag/**`, `src/controllers/input/**`,
  `src/controllers/commit/**`, `src/controllers/tools/**`, `src/controllers/selection/**`,
  `src/controllers/panel_actions/**`, `src/views/panel_domain_*.py`.
- `tools/complexity_score.py`, `tests/` (282-test baseline).

## 3. Verified current state (2026-11-24)

### 3.1 Landed (do not re-litigate; build on top of)

All of the following were confirmed in the working tree and are reported in the
analysis doc's "Implementation Status (incremental)":

1. **Semantic handler splits**
   - `key_down.handle_keydown` → priority chain over
     `controllers/input/{modal_keys,text_entry_keys,xform_field_keys,bezier_pen_keys,wave_keys,shortcut_keys}.py`.
   - `mouse_button_up.handle_mousebuttonup1` → delegates to
     `controllers/commit/{guide_commit,bezier_pen_commit,cutter_commit,selection_commit,redraw_commit,draw_commit}.py`.
   - `mouse_button_down_canvas._handle_canvas_click` → delegates into
     `controllers/tools/{draw_mode,redraw_mode}` + `controllers/selection/*`.
2. **Render sync wall replaced** — `app_controller.main` no longer carries a
   hardcoded render sync field list; `app_frame_controller._sync_back` syncs all
   ctx attrs, and render ctx writes back to frame locals automatically.
3. **Command registry / IDs** — `controllers/commands/{ids,registry,file_commands,edit_commands}.py`;
   shortcuts import `CMD.*` (`controllers/input/shortcut_keys.py`).
4. **`AppState` typed contract** — `controllers/app_state.py` with nested
   substate dataclasses (`Viewport/Document/Selection/Tool/Drag/UiCache`), live
   frame bridge via `sync_from_locals` / `to_locals_dict` / auto-derived
   `_SYNC_FIELDS`.
5. **Panel/view semantic relocations** — `controllers/panel_actions/*`,
   `views/panel_domain_*.py`, `views/panel_domains.py` with compat ctx-bag
   wrappers; star-import removal started.
6. **DragManager / DragSession** — `controllers/drag/session.py` base manager +
   per-interaction sessions; `controllers/drag/ui_session.py` (`UiDragSession`);
   event_loop routes via `DragManager`.
7. **Ctx sync plumbing reduced** — auto `_sync_all`, menu auto-sync,
   `app_frame_controller` auto-syncs all frame locals; `controllers/ctx_sync.py`
   reduced to frame-locals bridge helpers only.

### 3.2 Remaining gaps (the actual work)

From the analysis doc plus direct inspection of the working tree:

1. **Typed `AppState` is not yet the sole source of truth.**
   `app_controller.main()` still owns the majority of mutable app state as
   **frame locals**, builds ad-hoc `SimpleNamespace` ctx bags
   (`_bucket_ctx`, `_xform_ctx`, `_bp_ctx`, `_frame` ctx, `run_menu_action` ctx),
   and syncs via frame-locals bridges. The doc explicitly lists this as
   "Remaining (requires larger coordinated refactor)".
2. **Panel internals not yet rewritten by semantic domain.**
   `mbd_panel_*` / `panel_actions/*` / `panel_domain_*` internals still use the
   legacy ctx-bag / star-import patterns behind semantic entry points; full
   domain rewrite remains.
3. **Drag sessions incomplete.**
   `event_loop` still special-cases drag dispatch; `UiDragSession` is partial;
   `BezierPenSession` begin remains tool-state special-cased; transform-toggle
   edge flows not fully session-owned.
4. **Command/ctx sync plumbing not fully eliminated.**
   `ctx_sync.py` frame-locals bridge, menu callback-field sync lists, remaining
   frame-locals roundtrips.

### 3.3 Verification baseline (updated this session)

- Tests: `python -m unittest discover -s tests -t .` → **Ran 306 tests … OK**
  (baseline 282 + typed-state/dispatch + panel-domain + drag-session + typed-controller tests).
- Complexity: `python tools/complexity_score.py --top 20` → max score **8**
  (scale 0–10; median 4.0), mean 4.2; no regression. `app_broken_wave.py` still
  fails to parse (known, unrelated).

## 4. Phased application plan

Ordered by the analysis' risk/payoff ranking, adjusted for current reality.

### Phase 0 — Baseline & guardrails (complete)

- [x] Capture baseline: 282 tests OK, complexity snapshot, duplicate-function check.
- [x] Complexity report reviewed; `app_broken_wave.py` excluded from scoring.

### Phase 1 — Make typed `AppState` the sole source of truth (highest leverage)

**Rationale:** deletes the largest remaining sync wall and the biggest state
bottleneck in `app_controller.main()`.

| # | Task | Target |
|---|---|---|
| 1 | Extend `controllers/app_state.py` substate dataclasses to cover all live frame locals (document, selection, tools, drag, ui, services, caches). | `src/controllers/app_state.py` |
| 2 | Convert controller ctx builders to read from typed substate objects instead of frame locals / ad-hoc SimpleNamespace. | `app_controller._bucket_ctx/_xform_ctx/_bp_ctx`, `app_frame_controller`, handlers |
| 3 | Remove frame-locals bridge from `app_controller.main` hot loop (`sync_to_frame_locals` / `sync_from_locals(locals())` roundtrips). | `app_controller.main`, `controllers/ctx_sync.py` |
| 4 | Migrate one substate group end-to-end (recommended order: viewport/layout → document → selection → tools → drag → ui) before moving to the next, to bound risk. | handlers + state |

**Acceptance criteria**
- No handler/ctx builder reads a frame local for migrated fields; typed
  substate objects are passed directly.
- `controllers/ctx_sync.py` bridge helpers either deleted or reduced to a
  typed-only path.
- Full suite green: 285 tests OK; no new complexity regressions.

**Progress this session (implementation slices)**

- [x] Viewport substate group wired into `AppState._SYNC_FIELDS` auto-sync.
- [x] `app_controller.main.relayout()` writes layout geometry into
      `app_state.viewport`.
- [x] Added `tests/test_app_state.py` (5 tests) covering typed bridge round-trips,
      viewport defaults, document-state sync, and undo/redo through typed state.
- [x] Document substate group migrated: `DocumentState` extended (`clipboard_strokes`,
      `undo_stack`, `redo_stack`, `max_undo`, id counters); history closures
      (`push_undo`/`do_undo`/`do_redo`) now operate on `app_state.document.*`;
      `MAX_UNDO` local renamed to typed field `max_undo`.
- [x] **Phase 1 Task 2 (ctx builders)**: all four controller ctx builders
      (`_bucket_ctx`, `commit_text_entry`, `_xform_ctx`, `_bp_ctx`) and the
      `run_menu_action` command ctx now source values from typed substate objects
      (`app_state.document/selection/tools/drag/ui`), with sync functions writing
      typed state as well as legacy frame locals. Required typed fields added
      (`ToolState`: bucket picker/text options/bezier_pen; `UiCacheState`: text/xform
      input, picker, export dialog, help/workspace/running).
- [x] **Phase 1 sole-source-of-truth**: `AppState` is now authoritative at every
      frame dispatch boundary. `_build_ctx()` builds handler ctx with typed state
      overriding legacy locals (no local→typed seeding at dispatch); `main()`
      captures its own direct local mutations at a single frame-start point;
      frame helpers sync typed state after event/render dispatch. Added
      `test_typed_state_is_authoritative_at_dispatch`.
- [x] **Mid-frame curve sanitization migrated**: `selected_curve` / `redrawing_curve`
      invalidation in `main` now writes typed `AppState` (selection/drag) first and
      mirrors legacy locals; the view-model `state` dict reads those typed fields
      directly. Completes the drag/interaction group end-to-end (Task 4).
      Suite + 5-frame event smoke green.
- [x] **Drag/interaction group extended into the view model**: `bezier_pen`,
      `selected_point`, `selected_curves` in the per-frame `state` dict now read
      typed `AppState` substates (selected_curve/redrawing_curve remain local reads
      until their mid-frame sanitization is migrated). Event smoke green.
- [x] **Phase 1 Task 1 coverage completed for UI caches**: `UiCacheState` extended
      with 117 rect/cache fields from `main`, so all 124 `*_rect`/`*_cache` locals
      are now typed `AppState` fields (auto-derived `_SYNC_FIELDS`). Added
      `test_appstate_covers_main_rect_cache_locals` asserting zero missing fields.
      Full suite + 5-frame event smoke green (306 OK).
- [x] **Tools/selection substate group migrated end-to-end into the view model**:
      17 fields in `main`'s per-frame `state` dict now read typed `AppState`
      substates directly (`tool_mode`, `draw_tool`, `draw_shape`, variants,
      `snap_enabled`, `selection_submode`, `selected_strokes`, `guides`,
      `cut_gap`, `curve_cut_mode`, `eyedropper_pick`, `workspace`, etc.) instead
      of legacy frame locals. Full event smoke green.
- [x] **Phase 1 Task 3 fully closed**: deleted `controllers/ctx_sync.py` entirely
      (grep confirmed zero source references — only historical doc mentions remain).
      The old `sync_attrs` / `sync_to_frame_locals` bridge helpers no longer exist.
      Full suite + 5-frame event smoke green.
- [x] **Typed substates extended** (Phase 1 Task 1): added 22 more typed fields
      to `app_state.py` (tool shape options/counters, drag guide/pivot/cut state,
      selection `prev_selection_set`), including the ten fields `main` mutates
      at frame start; narrow capture set updated. Added
      `test_extended_tool_and_drag_fields_sync`. Suite green (305 OK).
- [x] **Narrowed frame-start capture**: `AppState.sync_from_locals(ns, fields=...)`
      supports a named subset; `app_controller.main` now captures only the six
      fields it mutates directly (`selected_strokes`, `selected_curve`,
      `redrawing_curve`, `transform_handle_mode`, `xform_field_focus/buffer`)
      instead of overwriting every typed field from stale legacy locals. Added
      `test_narrow_sync_does_not_clobber_typed_fields`. Suite green (304 OK).
- [x] **Legacy locals reduced**: removed 22 duplicate frame-local declarations in
      `app_controller.main` (the second init block re-assigned values already
      initialized in the first block with identical values). `app_controller.py`
      is now 714 SLOC / complexity 7 (from 829 SLOC at the start of the migration).
      Full-suite + 5-frame event smoke still green.
- [x] **Ctx-bag removal (four builders)**: `bucket_controller`, `text_entry_controller`,
      `transform_field_controller`, and `bezier_pen_controller` now accept typed
      `AppState` substates directly with explicit service params. `app_controller`
      deleted `_bucket_ctx`/`_bucket_sync`, `_xform_ctx`/`_xform_sync`, `_bp_ctx`/`_bp_sync`,
      and the `commit_text_entry` ctx construction. Added `tests/test_typed_controllers.py`
      (5 tests). Suite green (303 OK).
- [x] Remaining ctx adapters are dispatch-only: `run_menu_action` command ctx
      (single-sourced from typed state) and `_build_ctx` (typed-authoritative
      dispatch snapshot).
- [x] Runtime verification: 5-frame event smoke (KEYDOWN, MOUSEMOTION,
      MOUSEBUTTONDOWN, MOUSEBUTTONUP, QUIT) passes on top of 2-frame render smoke.
- [x] **Phase 1 Task 3 (complete)**: both event-side and both frame-loop bridge
      roundtrips removed. `main()` now uses `_frame.process_event_frame()` and
      `_frame.render_frame_frame()`, which mirror event/render ctx state into
      `AppState` at the point of mutation; history/ctx helpers mirror their own
      locals. No `sync_to_frame_locals` / `sync_from_locals(locals())` calls remain
      in the `main` hot loop.
- [x] **Phase 2 (complete)**: canonical command IDs moved to neutral
      `src/command_ids.py` (no view→controller cycle); `controllers/commands/ids.py`
      re-exports them; `views/menu.py` uses `CMD.*` for all 45 menu item keys;
      handler modules (`file_commands.py`, `edit_commands.py`, `menu_actions_view.py`)
      compare `key` against `CMD.*` constants (46 replacements); the
      `_MENU_CALLBACK_FIELDS` blacklist was replaced by authoritative typed
      `state_fields` sync. Updated `test_ui_theme` to the single-sourced
      convention; menu dispatch smoke test confirmed toggle works and callbacks
      are preserved.

**Phase 1 status**: bridge removal complete; remaining refinement is to have all
legacy handlers read typed state directly (Tasks 1/4 completion), now that the
hot-loop bridge is gone.

**Risk:** high blast radius (many handlers still read `ctx.<field>`).
**Mitigation:** substate-group-by-substate-group migration with tests after each group.

### Phase 2 — Complete command registry adoption

| # | Task | Target |
|---|---|---|
| 1 | Register remaining semantic commands (zoom/fit/view, selection ops) so menu + shortcut share one ID space. | `controllers/commands/*` |
| 2 | Replace stringly-typed menu/special-case dispatch keys with `CMD.*` references. | `views/menu.py`, `views/panel_*`, `menu_actions*`, `input/shortcut_keys.py` |
| 3 | Remove `_MENU_CALLBACK_FIELDS` sync hack (use typed state). | `controllers/menu_dispatch_controller.py`, `app_controller.run_menu_action` |

### Phase 3 — Panel domain semantic rewrite

| # | Task | Target |
|---|---|---|
| 1 | Finalize panel domain map: tool_options, fill_picker, gradient_stops, stroke_style, effects_wave, transform_inspector, selection_actions (from analysis tables). | `controllers/panel/*` (new layout) |
| 2 | Move remaining mixed handlers out of `mbd_panel_*` / `panel_actions/*` / `panel_domain_*` into those domains. | `src/controllers/mbd_panel_*.py`, `src/controllers/panel_actions/*`, `src/views/panel_domain_*.py` |
| 3 | Define shared panel rect contract (rect producer + hit handler in same semantic module). | `views/panel_select*.py`, `controllers/panel/*` |

**Progress (Phase 3, continued)**

- [x] Created `controllers/panel/` package with `dispatch.py`: flat ordered
      `DOMAIN_HANDLERS` (`tool_options` → `fill_picker` → `gradient_stops`) and
      `handle_panel_click()`; `mouse_button_down_panel` now delegates to it.
- [x] Added shared typed rect contract `controllers/panel/rects.py`
      (`PanelRects`, `rects_from_state`, `hit_rect`); `fill_picker.py` now resolves
      10 hit-rect sites through the shared contract; import smoke test confirms
      all moved names (including compat wrappers) resolve.
- [x] Moved `mbd_panel_b_color.py` internals to `controllers/panel/color_target.py`
      (compat wrapper left behind; `effects_wave` imports from the new domain).
- [x] Moved the core dispatch internals into semantic domains (compat wrappers
      left at old paths): `mbd_panel_a.py` → `panel/tool_options.py`,
      `mbd_panel_b.py` → `panel/color_panel.py`,
      `mbd_panel_c.py` → `panel/gradient_panel.py`; `panel/dispatch.py` now
      sources all three domains from the new modules; `tool_options` imports
      transform helpers directly from `panel/transform_inspector`.
- [x] Added `tests/test_panel_domains.py` (5 tests) covering order, short-circuit,
      rect contract, and `hit_rect`. Suite green (292 OK).
- [x] **Broader rect-contract adoption**: 22 more `ctx.state.get("*_rect")`
      hit sites in `tool_options.py` now use `hit_rect()` (32 total with
      `fill_picker.py`). Import smoke test confirms all core domain names and
      compat wrappers resolve. Suite green (293 OK).
- [x] **View-side rect ownership**: neutral `src/panel_rects.py` now owns the
      shared contract + `RECT_DOMAINS`/`domain_of`/`publish_rect` schema;
      `controllers/panel/rects.py` re-exports it. `views/panel_domain_color.py`
      publishes 21 rects through `publish_rect(state, key, rect)` so rect
      production and domain hit handling share one contract (no view→controller
      dependency).
- [x] Adopted `publish_rect` in the remaining five `views/panel_domain_*` modules
      (`color_detail`: 54, `effects`: 67, `selection`: 24, `style`: 9,
      `style_effects`: 47 rect publications — 201 total). All panel-domain view
      modules now publish rects through the shared contract; runtime frame smoke
      test still passes. Suite green (293 OK).

### Phase 4 — Complete drag/session ownership

| # | Task | Target |
|---|---|---|
| 1 | Finish UI/picker/wave-slider/opacity/fill-stop/bucket drag ownership via `UiDragSession` (event_loop special cases). | `src/controllers/event_loop.py`, `src/controllers/drag/ui_session.py` |
| 2 | Move bezier pen begin/end fully into `BezierPenSession`. | `src/controllers/drag/bezier_session.py`, `src/controllers/tools/draw_mode.py` |
| 3 | Resolve remaining transform-toggle / edge flows into session lifecycle. | `src/controllers/drag/transform_session.py`, `src/controllers/commit/selection_commit.py` |

**Progress (Phase 4, complete)**
- [x] `UiDragSession.end()` owns the complete UI-drag cleanup (mirrors state
      flags before clearing ctx flags); `mouse_button_up._cleanup_mouseup`
      delegates to it instead of duplicating flag cleanup.
- [x] `BezierPenSession.applies(ctx)` encapsulates the pen-tool condition;
      `event_loop` uses it instead of an inline tool/mode check.
- [x] Bezier pen pointer-down logic moved from `tools/draw_mode.py` into
      `BezierPenSession.begin()` (which now owns anchor placement, double-click
      finish, and close-path handle setup); `event_loop`'s special-case begin
      was removed.
- [x] Transform-toggle flows moved into `TransformDragSession.end()`;
      `commit_transform_toggle` is now a compat wrapper.
- [x] Added `tests/test_drag_sessions.py` (4 tests); suite green (297 OK).

### Phase 5 — Plumbing & dead-code cleanup

- [x] Removed all **70 star imports** in controllers, replacing them with AST-derived
      explicit imports (`models` / `views` / `controllers.coordinates`), plus explicit
      `config` and `command_ids` re-exports. Verified with an AST global-name audit:
      **0 unresolved globals** across all controller modules.
- [x] Retired dead compat wrappers: deleted `mbd_panel_a2.py`, `mbd_panel_b_parts.py`,
      `mbd_panel_b_color_parts.py`, `mbd_panel_c_parts.py`, and the whole
      `controllers/panel_actions/` package after rewiring call sites to the
      `controllers/panel/*` domains.
- [x] Updated `docs/ARCHITECTURE.md` to reflect the new semantic package layout
      and cross-layer contracts.
- Verification: 297 tests OK, runtime 2-frame smoke OK, complexity max 8 (no regression).

## 5. Concrete next-step backlog (updated this session)

1. ~~Write failing-state tests for `AppState` sync semantics before Phase 1
   migration~~ → **DONE**: added `tests/test_app_state.py` (3 tests, passing) as
   the Phase 1 bridge-coverage baseline.
2. ~~Phase 1, substate group 1: viewport/layout~~ → **DONE (this session)**:
   typed viewport group wired into auto-sync + `relayout` writes through
   `app_state.viewport`; suite green (285 OK), complexity unchanged (max 8).
3. ~~Phase 1, substate group 2: document state~~ → **DONE**: typed document group
   (clipboard, undo/redo stacks, counters) + history closures migrated.
4. ~~Phase 1 Task 2: ctx builders sourced from typed state~~ → **DONE**: four
   controller ctx builders + `run_menu_action` now source typed substates.
5. ~~Phase 1 Task 3 (partial): redundant pre-event bridge sync removed~~ → **DONE**.
6. ~~Finish Phase 1 Task 3 event-side bridge removal~~ → **DONE**.
7. ~~Remove remaining loop-start/end-of-frame bridge points~~ → **DONE**:
   `main()` uses frame helpers for event/render ctx sync; headless smoke test
   ran 2 full frames successfully.
8. ~~Phase 2: single-source menu UI keys + remove `_MENU_CALLBACK_FIELDS`~~ →
   **DONE**: neutral `command_ids`, `CMD.*` in menu and handlers, typed
   `state_fields` sync.
9. ~~Phase 3 first slice: semantic panel domain dispatcher~~ → **DONE**
   (`controllers/panel/`, ordered domains, 2 new tests).
10. Next: move remaining mixed panel handler internals into `controllers/panel/*`
    domains, then Phases 4–5 (drag/session ownership, cleanup).

## 6. Verification & acceptance gates

- `python -m unittest discover -s tests -t .` → expect **306 OK** (baseline 282 + typed-state/dispatch + panel-domain + drag-session + typed-controller tests; no regressions).
- `python tools/complexity_score.py --top 20` → controllers trending toward low scores.
- New tests added per phase must keep suite green; complexity must not regress.

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Behavior drift during ctx→typed migration | Substate-group-by-group; full suite + new AppState tests after each group |
| Frame-locals bridge (`PyFrame_LocalsToFast`) is CPython/implementation specific | Replace with direct typed access, not rely on fallback |
| Panel rewrite touches many files | One domain per PR/branch |
| Drag session edge cases (bezier modal, transform toggle) | Keep behavior-preserving: test before/after per flow |

## 8. Exit criteria for "semantic split applied"

- No god-function-sized controller remains in the analyzed set (complexity well
  under threshold).
- `AppState` is the sole source of truth; legacy locals/ctx-bag removed.
- Command IDs single-sourced; registry dispatch used by menus + shortcuts.
- Drag interactions session-owned end-to-end.
- No star imports / dead ctx sync in controllers; ARCHITECTURE.md updated.
