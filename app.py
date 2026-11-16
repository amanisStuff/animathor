"""Animathor entry point (MVC facade).

Model      -> model.py      stroke data, geometry, wave math, hit tests
View       -> view.py       cairo/pygame rendering, panel, toolbar, widgets
Controller -> controller.py event loop, app state, undo/redo
Config     -> config.py     layout + theme constants

`import app` still exposes every public and private name, so existing
code and tests keep working unchanged. Layout values that change on
window resize (WIDTH, HEIGHT, ...) resolve live through config.
"""

import config as _config
import model as _model
import view as _view
import controller as _controller

for _mod in (_model, _view, _controller):
    for _name in dir(_mod):
        if _name.startswith("__") or _name in {"_mod", "_name"}:
            continue
        globals()[_name] = getattr(_mod, _name)

main = _controller.main


def __getattr__(name):
    # Anything not copied above (e.g. live layout values) resolves in config.
    return getattr(_config, name)


if __name__ == "__main__":
    main()
