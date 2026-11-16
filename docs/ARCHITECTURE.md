# Architecture (MVC)

`app.py` is a thin facade — `import app` still exposes every name, so
scripts and tests keep working unchanged. The code is split by MVC role
into packages:

## Packages

| Package | Modules | Responsibility |
|---|---|---|
| `models/` | `geometry.py` — curve construction, transforms, bbox/color math<br>`strokes.py` — stroke data structures and operations<br>`waves.py` — wave distortion styles, evaluation and sampling<br>`interaction.py` — snapping, hit testing, drawing-point collection | **Model**: all data and pure computation. No pygame/cairo/tkinter. |
| `views/` | `canvas.py` — cairo canvas rendering, stroke paths, image handling<br>`panel.py` — right properties panel<br>`toolbar.py` — left tool toolbar<br>`widgets.py` — `Button`, `Slider`<br>`dialogs.py` — native file dialogs (tkinter) | **View**: rendering only; reads model data, never mutates it. |
| `controllers/` | `app_controller.py` — `main()` event loop, app state, undo/redo<br>`coordinates.py` — window ↔ canvas coordinate mapping | **Controller**: wires View and Model, owns mutable app state. |
| *(root)* | `config.py` — layout + theme constants/tables<br>`app.py` — facade/entry point | Shared config and compatibility surface. |

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
They live in `config.py`, are excluded from `__all__` (so star-imports
can't create stale copies), and are mutated/read via
`import config as cfg` attribute access (`cfg.WIDTH = ...`).
`app.WIDTH` resolves live through the facade's module `__getattr__`.
