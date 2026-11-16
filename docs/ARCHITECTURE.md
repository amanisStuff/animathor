# Architecture (MVC)

`app.py` is a thin facade — `import app` still exposes every name, so
scripts and tests keep working unchanged. The code is split by MVC role:

| Layer      | Module         | Responsibility |
|------------|----------------|----------------|
| Model      | `model.py`     | Stroke/geometry data, Bézier math, wave styles + sampling, hit testing, transforms, merging. Pure computation — no pygame/cairo/tkinter. |
| View       | `view.py`      | All rendering: cairo canvas (`draw_scene`, stroke paths), pygame right panel (`draw_panel`), left toolbar, widgets (`Button`, `Slider`). Reads model data, never mutates it. |
| Controller | `controller.py`| Event handling, app state wiring, undo/redo stacks, window layout updates, `main()`. |
| Config     | `config.py`    | Layout + theme constants and UI tables. |

## Dependency direction

```
config  <-  model  <-  view  <-  controller  <-  app (facade)
```

No cycles: Model never imports View/Controller; View only reads Model;
Controller wires both.

## Live layout values

`WIDTH, HEIGHT, CANVAS_W, CANVAS_X, PANEL_X` change on window resize.
They live in `config.py`, are excluded from `__all__` (so star-imports
can't create stale copies), and are mutated/read via
`import config as cfg` attribute access (`cfg.WIDTH = ...`).
`app.WIDTH` resolves live through the facade's module `__getattr__`.

## Re-export mechanics

Each module makes the others' names available as bare names at import
time (e.g. `view.py` copies Model names into its globals), keeping the
original function bodies byte-identical to the pre-refactor source.
