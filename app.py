"""Animathor entry point (MVC facade).

models/       Model: geometry, strokes, waves, interaction (pure computation)
views/        View: canvas, panel, toolbar, widgets, dialogs (all rendering)
controllers/  Controller: app_controller (event loop/state), coordinates
config.py     Layout + theme constants

`import app` still exposes every public and private name, so existing
code and tests keep working unchanged. Layout values that change on
window resize (WIDTH, HEIGHT, ...) resolve live through config.
"""

import config as _config
import models as _models
import views as _views
import controllers as _controllers

_PLUMBING = {"_mod", "_name", "_m", "_n", "cfg", "config", "models", "views",
             "controllers", "geometry", "strokes", "waves", "interaction",
             "canvas", "panel", "toolbar", "widgets", "dialogs",
             "app_controller", "coordinates", "math", "copy", "pygame",
             "cairo", "_config", "_models", "_views", "_controllers"}

for _mod in (_models, _views, _controllers):
    for _name in dir(_mod):
        if _name.startswith("__") or _name in _PLUMBING:
            continue
        globals()[_name] = getattr(_mod, _name)

# back-compat: some callers/tests access `app.cairo` / backend
try:
    from views.canvas import cairo, CAIRO_BACKEND  # noqa: F401
except Exception:
    pass

main = _controllers.app_controller.main


def __getattr__(name):
    # Anything not copied above (e.g. live layout values) resolves in config.
    return getattr(_config, name)


if __name__ == "__main__":
    main()
