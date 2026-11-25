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

### 3.2 Remaining gaps (updated 2026-11-25)

The originally-listed gaps below are **now closed** (see Phase 1–5 progress):

- ~~Typed `AppState` not sole source of truth~~ → all state groups typed;
  `app_state.ui` covers every rect/cache local; view-model and handler boundaries
  read typed state; hot-loop frame-locals bridges and `ctx_sync.py` deleted;
  `SimpleNamespace` builders replaced by typed `CommandContext` / `DispatchContext`.
- ~~Panel internals not rewritten by semantic domain~~ → `controllers/panel/*`
  owns the domains; `views/panel_domain_*` publish rects through the shared
  `panel_rects` contract; several panel entries expose typed contracts.
- ~~Drag sessions incomplete~~ → `DragManager` sessions own begin/move/end
  including bezier, transform toggle, UI/picker and commit flows.
- ~~Command/ctx sync plumbing~~ → single-sourced `command_ids`, typed command
  dispatch, no callback blacklist.

**Still open (smaller, bounded):**
1. A few legacy locals with live readers remain in `app_controller.main`
   (681 lines / score 7); the frame helpers now pass typed `AppState` directly
   into `DispatchContext` — the `_build_ctx` helper was removed.
2. Bodies inside the large panel handlers keep their extracted ctx style; their
   domain entry points are typed, not every internal line.
3. Complexity max 8 persists in model/view geometry and large panel-domain
   modules; `app_controller.py` is no longer in the top-20 set.

- [x] **Phase 5 progress**: Panel handler typed-field coverage fixed (added
      missing `UiCacheState` fields: `fill_gradient_stop`, `fill_stop_pos_drag`,
      `obj_opacity_drag`, `picker_h/s/v`, `color_target`, `bucket_picker_drag`)
      that the migration referenced but had not declared; runtime smoke caught
      them and they are now declared. Suite 323 OK, event + panel-click smokes
      green. `complexity_score.py --top 20`: 185 files, mean 4.1, max 8 (no
      regression).

The analysis' exit criteria for the **controller** split are met:
- No god-function-sized controller remains in the analyzed set — controller
  ceiling is now **7** (`app_controller.py`, `view_commands.py`); no controller
  module scores 8.
- `AppState` is the sole typed owner at every dispatch/view-model boundary; the
  hot-loop frame-locals bridges and `ctx_sync.py` are deleted.
- Command IDs are single-sourced; typed command/dispatch contexts replace ctx bags.
- Interactions are owned by `DragManager` sessions.
- No controller star imports; `ARCHITECTURE.md` updated.

The remaining **overall max 8** scores live in `src/models/*` (pure data/geometry:
`geometry.py`, `waves_extra.py`, `strokes.py`, `interaction.py`) and
`src/views/*` (`panel_domain_*`, `canvas_extra3.py`). The analysis explicitly
defines models as pure data/geometry and views as rendering, outside the
controller split scope; lowering the overall max below 8 requires a separate
refactor of pure model/view geometry functions and is outside this plan as
written.

### 3.3 Verification baseline (updated this session)

- Tests: `python -m unittest discover -s tests -t .` → **Ran 322 tests … OK**
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

- [x] **Stale docs corrected**: `docs/SEMANTIC_SPLIT_PLAN.md#3.2` now marks the
      originally-listed Phase 1 gaps (ctx_sync, ctx bags, bridges, panel/drag
      relocations) as closed and lists only the remaining bounded items.
- [x] **Typed-ownership audit clean**: a parsing audit of `app_controller.main`
      reports **0 bare reads of typed-field names** — every such field is read
      through `app_state.<sub>.<field>`. Suite 322 OK.
- [x] **Sanitization block migrated to typed-only**: `selected_curve` /
      `redrawing_curve` / `selected_curves` invalidation in `app_controller.main`
      now writes typed `AppState` only; the mirror locals and mirror assignments
      in `commit_text_entry` / `_bp_mirror_locals` were deleted. Event + panel
      smokes green.
- [x] **Score-8 `mouse_button_down_menus.py` split**: into `menu_pre_dispatch.py`
      and `menu_clicks.py` with a compat re-export; no longer in top 20.
- [x] **Mouse-motion package import bug fixed**: the new `controllers/mouse_motion/`
      package shadowed `mouse_motion.py`, so `handle_mousemotion` became unimportable
      on real MOUSEMOTION events. Moved the dispatcher into the package `__init__.py`
      and deleted the shadowed module; a stale `_apply_comp_stroke_color_drag`
      compat import was removed. Event smoke (with real motion) + panel-click smoke
      now pass.
- [x] **Last safe bare reads migrated**: `snap_move_delta(strokes, …)`,
      `reference_image`, `reference_error` now read typed `AppState` fields.
      Suite 322 OK.
- [x] **Complexity exit criterion met for controllers**: after extracting large
      functions into semantic helpers, **no controller module scores 8** in
      `complexity_score.py --top 20`; the controller ceiling is **7**
      (`app_controller.py`, `view_commands.py`). Overall max 8 remains only in
      model/view geometry modules. Suite 323 OK, event + panel smokes green.
- [x] **Score-8 single-function modules split into semantic helpers** with compat
      re-exports / dispatchers: `view_commands.py` (view/artboard/symbol/shape-state),
      `menu_clicks.py` (menu-bar/marker/shape-menu helpers), `wave_motion.py`
      (eight drag-domain helpers). Runtime smoke caught an uninitialized
      `handled` in the menu helpers and a pre-existing undefined `current_points`
      in wave motion; both fixed. All three modules are out of the top-20 set.
      Suite 323 OK, event + panel smokes green.
- [x] **Explicit typed UI-frame output** (analysis §8): added `views/panel_state.py`
      with `UiFrameOutput` (typed rect snapshot + dimensions); `render_ui_frame`
      now returns it instead of a bare integer. Added a typed-output test.
      Suite 323 OK, panel-click smoke green.
- [x] **Latent typed-body bugs fixed**: a bare-`ctx` audit found and fixed
      10 residual `hit_rect(ctx, …)` calls in the split fill-picker typed bodies
      (now use `rects_from_state(state)`) and a missing `ctx` parameter in
      `effects_wave_part3_typed`. Verified: audit 0 suspects, panel-click smoke green.
- [x] **Score-8 `effects_wave.py` split**: into `wave_hits.py` (shared ctx helpers),
      `effects_wave_add.py`, `effects_wave_edit.py`, `effects_wave_apply.py`;
      original is a compat re-export + typed dispatcher. No longer in top 20.
      Suite 322 OK.
- [x] **Score-8 mouse-motion modules split**: `mouse_motion_parts.py` / `parts2.py`
      → `controllers/mouse_motion/{guide_cut_motion,wave_motion,transform_motion}.py`;
      originals are compat re-exports. Neither old module appears in
      `complexity_score.py --top 20`. Suite 322 OK, panel smoke green.
- [x] **Score-8 controller module split**: `menu_actions_view.py` split into
      `controllers/commands/view_commands.py` and `controllers/commands/tool_commands.py`
      (matching the analysis' suggested layout); original is a compat re-export.
      No longer in `complexity_score.py --top 20`. Suite 322 OK, panel smoke green.
- [x] **Score-8 controller module split**: `mouse_button_down.py` split into
      `mouse_button_down_menus.py` (pre-menu + menus) and
      `mouse_button_down_toolbar.py`; the original is a compat re-export plus the
      main dispatcher. No longer in `complexity_score.py --top 20`. Suite 322 OK,
      panel-click smoke green.
- [x] **Score-8 panel module split**: `fill_picker.py` split into semantic modules
      `fill_picker_options.py`, `fill_picker_stops.py`, `fill_picker_color.py`;
      the original is now a compat re-export + typed dispatcher. All three new
      modules score below the top-20 cutoff (`complexity_score.py --top 20` no
      longer lists any `fill_picker*` module). Suite 322 OK, panel-click smoke green.
- [x] **`transform_fields.py` handler body fully typed**: `_handle_panel_click_a_p2`
      rewritten as `transform_fields_typed(tools, selection, document, drag, ui, ...)`;
      legacy ctx wrapper with projection retained; 0 residual `ctx.*`.
- [x] **`tool_options.py` handler body fully typed**: `_handle_panel_click_a_p1`
      rewritten as `tool_options_typed(...)`; 22 `hit_rect(ctx, ...)` sites migrated
      to the shared `rects_from_state(state)` contract; runtime smoke caught a
      missing typed `reference_image` field (added to `DocumentState`) and a
      residual bare `ctx` (fixed); 0 residual `ctx.*`. Suite 322 OK, event +
      panel-click smokes green.
- [x] **`align_distribute.py` handler body fully typed**: `_handle_panel_click_a_p3`
      rewritten as `align_distribute_typed(tools, selection, document, drag, ui,
      state, event, push_undo, clamp)` with a legacy ctx wrapper (legacy-ctx
      projection included). Grep caught one residual `ctx.shadow`; fixed, now 0
      residual `ctx.*`. Suite 322 OK, event + panel-click smokes green.
- [x] **`gradient_stops.py` handler bodies fully typed**: `handle_c_tabs_filltype`,
      `handle_c_stops`, `handle_c_picker` rewritten as typed contracts with explicit
      services and legacy ctx wrappers (legacy-ctx projection included). Grep
      caught 7 residual `ctx.default_*_gradient` / `ctx.normalize_gradient` refs
      in the first pass; fixed, now 0 residual `ctx.*` in typed bodies. Unit tests,
      5-frame event smoke and 10-frame panel-click smoke pass.
- [x] **`effects_wave.py` handler bodies fully typed**: `handle_b_part1/2/3`
      rewritten as `effects_wave_part1_typed` / `part2_typed` / `part3_typed`,
      taking typed tool/selection/document/UI substates plus explicit services;
      legacy wrappers retained with legacy-ctx projection. Grep confirms 0
      residual `ctx.*` in typed bodies. Unit tests, 5-frame event smoke, and
      10-frame panel-click smoke pass. Suite 322 OK.
- [x] **`fill_picker.py` handler bodies fully typed**: `handle_bc_part1/2/3`
      rewritten as `fill_picker_part1_typed` / `part2_typed` / `part3_typed`,
      taking typed substates + explicit services (`get_fill_gradient`,
      `rgb_to_hsv`, `clamp`, `globals_map`, etc.); legacy ctx wrappers retained.
      A first scripted pass leaked `ctx.globals()` / service refs into the typed
      bodies — grep caught it and all 71 affected lines were fixed (0 residual
      `ctx.*` in typed bodies). Unit tests, 5-frame event smoke, and a 10-frame
      panel-click smoke pass.
- [x] **Transform panel domain split** (Phase 3 complexity reduction):
      `transform_inspector.py` (score 8) split into `transform_fields.py` (p2)
      and `align_distribute.py` (p3); `transform_inspector.py` is now a compat
      re-export with explicit underscore-name imports. Regression tests caught
      the missing underscore re-exports; fixed. `transform_inspector` no longer
      appears in `complexity_score.py --top 20`. Suite 322 OK, event smoke green.
- [x] **Panel handler typed contracts**: `color_target.py`, `gradient_panel.py`,
      `color_panel.py`, `fill_picker.py`, `effects_wave.py` expose typed entry points
      with ctx compat wrappers that project legacy ctx fields into typed substates
      (kept for regression tests calling with plain ctx). Typed boundaries were
      also added to `gradient_stops.py`, `transform_inspector.py`, `tool_options.py`
      (`gradient_stops_hit`, `transform_inspector_hit`, `tool_options_hit`), and
      `gradient_panel` routes through `gradient_stops_hit`. Suite 322 OK, event
      smoke green. `complexity_score.py --top 20` shows `app_controller.py`
      no longer in the top-20 set (max 8 remains across model/view/panel-domain
      geometry modules).
- [x] **Panel handler typed contract (color target)**: `controllers/panel/color_target.py`
      exposes `color_target_hit(ui, selection, document, state, event, was_hit, ctx, ...)`
      with a `_b3_color` ctx compat wrapper; added `UiCacheState.color_target`.
      Added typed no-op test. Suite 319 OK, event smoke green.
- [x] **Final typed-reader sweep in `main`**: migrated 38 same-name state-dict
      reads (`shape_menu_*`, `star_*`, `trace_algorithm`, `wave_*`, etc.) plus 7
      low-risk bare reads (`snap_enabled`, `guides`, `running`, `draw_shape`,
      `text_entry`) to typed `AppState` fields. Remaining bare reads are mirrors
      inside the sanitization block where typed writes are already performed.
      Suite 322 OK, event smoke green.
- [x] **Mirror locals deleted**: removed `_bp_mirror_locals` and `_sync_history_locals`
      helpers and all their call sites; `push_undo`/`do_undo`/`do_redo`/bezier
      helpers now read/write typed state only. `strokes` reads in `main` (state
      dict) now read `app_state.document.strokes`. `app_controller.py` is now
      **548 lines / score 7** (from 829). Suite 323 OK, event + panel smokes green.
- [x] **Dead local mirrors deleted**: after migrating view-model readers, removed
      119 unused `*_cache` / `*_rects` local declarations from `app_controller.main`
      (their only remaining references were typed reads). `app_controller.py` is
      now **681 lines / score 7** (from 829 lines at the start of the migration).
      Full suite 318 OK and 5-frame event smoke green.
- [x] **View-model UI-cache readers migrated to typed state**: 117 `*_cache`
      / `*_rects` values in `main`'s per-frame `state` dict now read
      `app_state.ui.<field>` instead of legacy locals. A parsing audit reports
      **0 bare typed-field locals** left in the state dict. The final three
      cache locals (`picker_rects`, `swatch_rects_cache`, `fill_stop_rects_cache`)
      were migrated and deleted too; runtime smoke caught that
      `_frame.init_ui_caches()` must seed typed UI fields directly (it now
      initializes `swatch_rects_cache` and copies cache updates into
      `app_state.ui`), which was fixed. Suite 322 OK, event smoke green.
- [x] **Draw commit typed contract**: `controllers/commit/draw_commit.py` exposes
      `commit_draw_typed(drag, document, selection, tools, event, ...)` with a ctx
      compat wrapper; added typed no-op test. Suite 318 OK, event smoke green.
- [x] **Bezier-pen commit typed contract**: `controllers/commit/bezier_pen_commit.py`
      exposes `commit_bezier_pen_mouseup_typed(tools, finish_pen)` with a ctx compat
      wrapper; added typed handle-release test. Suite 317 OK, event smoke green.
- [x] **Redraw commit typed contract**: `controllers/commit/redraw_commit.py`
      exposes `commit_redraw_curve_typed(drag, document, event, ...)` with a ctx
      compat wrapper; added typed no-op test. Suite 316 OK, event smoke green.
- [x] **Selection commit typed contract**: `controllers/commit/selection_commit.py`
      exposes `commit_marquee_typed(drag, selection, document, tools, ...)` with a
      ctx compat wrapper; added typed no-op test. Suite 315 OK, event smoke green.
- [x] **Commit handler typed contract (cutter)**: `controllers/commit/cutter_commit.py`
      exposes `commit_cutter_typed(drag, document, selection, tools, state, event, ...)`
      with a ctx compat wrapper; added typed no-op test. Suite 314 OK, event smoke
      green.
- [x] **Commit handler typed contract (guide)**: `controllers/commit/guide_commit.py` now
      exposes `commit_guide_drag_typed(drag, pos, ruler_size, top_bar_h)` with a
      thin ctx compat wrapper; runtime smoke caught and fixed an eager attribute
      access in the wrapper. Added typed test. Suite 313 OK, event smoke green.
- [x] **Dead typed mirror declarations removed**: AST audit found 7 typed-state
      mirror locals with zero reads after their last declaration; removed them.
      `app_controller.py` is now **571 lines / score 7** (from 829 lines at the
      start of the migration). Suite 323 OK, event + panel-click smokes green.
- [x] **Frame-start bridge fully removed**: the last `sync_from_locals(locals())`
      roundtrip in `main`'s hot loop is gone. The ten formerly-captured fields
      (`selected_strokes`, `selected_curve`, `redrawing_curve`,
      `transform_handle_mode`, `xform_field_*`, `pivot_pos`,
      `prev_selection_set`, shape variants) are now written to typed `AppState`
      at their mutation sites with local mirrors. Only the one-time startup seed
      and the menu-result mirror remain. Suite + 5-frame event smoke green.
- [x] **Selection handler typed contract**: `controllers/selection/eyedropper.py`
      now exposes `eyedropper_hit(tools, document, selection, state, event, ...)`
      taking typed substates + explicit services; `handle_eyedropper(ctx, event)`
      is a thin compat wrapper. Added a miss-mode test. Suite 312 OK, event smoke
      green.
- [x] **`_build_ctx` helper removed**: both frame helpers now construct
      `DispatchContext(app_state, fields)` directly, passing typed `AppState`
      into handlers without the snapshot-builder wrapper. Updated the unit test
      that imported `_build_ctx` to construct `DispatchContext` directly.
      Suite 322 OK, 10-frame panel-click smoke green.
- [x] **Dispatch ctx snapshot replaced by live typed context**: added
      `controllers/dispatch_context.py::DispatchContext` — a typed view over
      `AppState` whose writes to typed fields propagate into the owning substate
      immediately. `_build_ctx` now returns it instead of `SimpleNamespace`.
      Added `test_dispatch_context_writes_typed_state`. Suite 311 OK; event smoke
      green; AST audit 0 problems.
- [x] **Menu command ctx bag replaced by typed contract**: added
      `controllers/commands/context.py::CommandContext` (typed dataclass with
      document/selection/tool/drag/UI fields + explicit service deps);
      `app_controller.run_menu_action` now builds `CommandContext` instead of a
      `SimpleNamespace`. Added `test_command_context_covers_menu_action_fields`
      (parsing guard) — full suite 310 OK, event smoke green.
- [x] **Render frame split by semantic responsibility** (analysis §8): created
      `controllers/render/{scene_state,canvas_overlay,ui_frame}.py`; `render_frame.py`
      is now a thin orchestrator calling `render_scene`, `render_canvas_overlay`,
      `render_ui_frame` in order. Behavior-preserving: full suite (309 OK) and
      5-frame event smoke pass; AST audit reports 0 unresolved globals and zero
      controller star imports.

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

- `python -m unittest discover -s tests -t .` → expect **322 OK** (baseline 282 + typed-state/dispatch + panel-domain + drag-session + typed-controller tests; no regressions).
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
