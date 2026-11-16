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
| `models/` | `geometry.py` — curve construction, transforms, bbox/color math<br>`strokes.py` — stroke data structures and operations<br>`waves.py` — wave distortion styles, evaluation and sampling<br>`interaction.py` — snapping, hit testing, drawing-point collection | **Model**: all data and pure computation. No pygame/cairo/tkinter. |
| `views/` | `canvas.py` — cairo canvas rendering, stroke paths, image handling<br>`panel.py` — right properties panel<br>`toolbar.py` — left tool toolbar<br>`widgets.py` — `Button`, `Slider`<br>`dialogs.py` — native file dialogs (tkinter) | **View**: rendering only; reads model data, never mutates it. |
| `controllers/` | `app_controller.py` — `main()` event loop, app state, undo/redo<br>`coordinates.py` — window ↔ canvas coordinate mapping | **Controller**: wires View and Model, owns mutable app state. |
| *(root of src/)* | `config.py` — layout + theme constants/tables<br>`app.py` — facade/entry point<br>`bezier.py` — stroke simplification/fitting | Shared config, compat surface, geometry fitting. |

Each package's `__init__.py` re-exports its submodule names and
cross-populates submodule namespaces so intra-layer references resolve at
runtime (the original function bodies are kept verbatim).

## Dependency direction

```
config  ←  models  ←  views  ←  controllers  ←  app (facade)
```

No cycles: Model never imports View/Controller; View only reads Model;
Controller wires both.

## Live layout values

`WIDTH, HEIGHT, CANVAS_W, CANVAS_X, PANEL_X` change on window resize.
They live in `src/config.py`, are excluded from `__all__` (so star-imports
can't create stale copies), and are mutated/read via
`import config as cfg` attribute access (`cfg.WIDTH = ...`).
`app.WIDTH` resolves live through the facade's module `__getattr__`.
