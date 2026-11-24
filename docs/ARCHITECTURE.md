# Architecture (MVC)

`src/app.py` is a thin facade — `import app` (resolved via the root shim
or with `src/` on `sys.path`) still exposes every name, so scripts and
tests keep working unchanged. The core app lives under `src/`, separated
from `tests/` and `docs/` at the repository root.

## Layout

| Path | Role |
|---|---|
| `app.py` (root) | Launcher/shim that loads the real app from `src/` |
| `src/` | Core application source |
| `tests/` | Unit and end-to-end tests |
| `docs/` | Documentation |

## Packages (`src/`)

| Package | Modules | Responsibility |
|---|---|---|
| `models/` | `geometry.py` — curve construction, transforms, bbox/color math, oriented shape fitting (`shape_from_doodle`: min-area box for rect/square/ellipse, corner fit for triangles)<br>`strokes.py` — stroke data structures and operations (incl. `cut_ends` flags that keep gap-separated razor pieces from auto-merging)<br>`waves.py` — wave distortion styles, evaluation and sampling<br>`interaction.py` — snapping, hit testing, drawing-point collection, split curve tool (`cut_strokes_with_path`: gap 0 inserts a node, keeps the stroke connected, and starts a new curve component at each crossing; a gap splits with De Casteljau) | **Model**: all data and pure computation. No pygame/cairo/tkinter. |
| `views/` | `canvas.py` — cairo canvas rendering, stroke paths, image handling<br>`panel.py` — right properties panel: Pen/Eraser/Fill/Split curve grid on top, "Tool options" filtered per tool (Fill color HSV picker + swatches, Split curve toggle in Curve submode), `draw_panel_toggle` collapse tab<br>`toolbar.py` - left tool toolbar, bottom bar (shapes + Eraser/Split/Fill) with right-click option popups<br>`widgets.py` — `Button`, `Slider`<br>`dialogs.py` — native file dialogs (tkinter) | **View**: rendering only; reads model data, never mutates it. |
| `controllers/` | `app_controller.py` — `main()` event loop, app state, undo/redo<br>`app_state.py` — typed `AppState` contracts (viewport/document/selection/tools/drag/ui)<br>`app_frame_controller.py` — event/render frame helpers that mirror ctx into `AppState`<br>`coordinates.py` — window ↔ canvas coordinate mapping<br>`commands/` — command IDs + registry + file/edit command handlers<br>`input/` — keyboard input modes (modal/text/xform/bezier/wave/shortcuts)<br>`tools/`, `selection/` — canvas tool/selection handlers<br>`drag/` — `DragManager` + per-interaction sessions (UI/bezier/transform/pan/etc.)<br>`panel/` — semantic panel domains (`tool_options`, `fill_picker`, `gradient_stops`, `effects_wave`, `transform_inspector`, `color_target`, `color_panel`, `gradient_panel`), flat dispatch, shared rect contract<br>`commit/` — interaction commit handlers<br>`render_frame.py` — scene/UI render composition | **Controller**: wires View and Model, owns mutable app state. |
| *(root of src/)* | `config.py` — layout + theme constants/tables<br>`app.py` — facade/entry point<br>`bezier.py` — stroke simplification/fitting<br>`command_ids.py` — command IDs shared by menus (views) and command handlers (controllers), avoiding a view→controller cycle<br>`panel_rects.py` — shared panel rect contract + domain ownership schema, used by both view producers and controller hit handlers | Shared config, compat surface, geometry fitting, neutral cross-layer contracts. |

Each package's `__init__.py` re-exports its submodule names and
cross-populates submodule namespaces so intra-layer references resolve at
runtime (the original function bodies are kept verbatim).

## Dependency direction

```
config  ←  models  ←  views  ←  controllers  ←  app (facade)
```

No cycles: Model never imports View/Controller; View only reads Model;
Controller wires both.

## Semantic split contracts

The quantitative extraction scaffolding (ctx `SimpleNamespace` bags and
`hasattr` sync lists) has been replaced by semantic ownership:

- `AppState` (`controllers/app_state.py`) owns typed state groups. Frame helpers
  (`app_frame_controller.process_event_frame` / `render_frame_frame`) mirror
  changed ctx state into `AppState` at the point of mutation; `app_controller.main`
  no longer runs frame-locals bridge roundtrips.
- Commands are single-sourced through `command_ids` (both `views/menu.py` and
  controller handlers use `CMD.*`), dispatched by `controllers/commands/registry`.
- Panel hit rects are produced by `views/panel_domain_*` through `panel_rects.publish_rect`
  and consumed by `controllers/panel/*` domains through `hit_rect`, sharing the
  `RECT_DOMAINS` ownership schema.
- Interactions are owned by `DragManager` sessions, which handle their own
  begin/move/end lifecycle instead of scattered flag branches.

## Live layout values

`WIDTH, HEIGHT, CANVAS_W, CANVAS_X, PANEL_X` change on window resize.
They live in `src/config.py`, are excluded from `__all__` (so star-imports
can't create stale copies), and are mutated/read via
`import config as cfg` attribute access (`cfg.WIDTH = ...`).
`app.WIDTH` resolves live through the facade's module `__getattr__`.

`relayout()` in `app_controller.main()` is the single place that recomputes
`cfg.CANVAS_X/CANVAS_W/PANEL_X` and recreates the cairo surface. It runs on
`VIDEORESIZE` and when the right sidebar is collapsed/expanded: collapsing
sets the panel width to 0 (canvas grows to the window edge,
`cfg.PANEL_X == cfg.WIDTH`) and `draw_panel` is skipped for that frame.
