"""MVC Controller package: event handling, state, coordinates."""

from controllers import coordinates, app_controller  # noqa: F401

_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
_SUBS = (coordinates, app_controller)
for _m in _SUBS:
    for _n in dir(_m):
        if _n.startswith('__') or _n in _PLUMBING:
            continue
        globals()[_n] = getattr(_m, _n)
import models as _models
import views as _views
for _m in _SUBS:
    for _src in (_models, _views):
        for _n in dir(_src):
            if _n.startswith('__') or _n in _PLUMBING:
                continue
            _m.__dict__.setdefault(_n, getattr(_src, _n))
    for _n, _v in list(globals().items()):
        if _n.startswith('__') or _n in _PLUMBING:
            continue
        _m.__dict__.setdefault(_n, _v)
