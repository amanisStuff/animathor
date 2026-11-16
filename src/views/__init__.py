"""MVC View package: rendering, panel, toolbar, widgets."""

from views import widgets, toolbar, canvas, panel, dialogs  # noqa: F401

_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
_SUBS = (widgets, toolbar, canvas, panel, dialogs)
for _m in _SUBS:
    for _n in dir(_m):
        if _n.startswith('__') or _n in _PLUMBING:
            continue
        globals()[_n] = getattr(_m, _n)
# cross-populate submodules with all view+model names
import models as _models
for _m in _SUBS:
    for _src in (_models,):
        for _n in dir(_src):
            if _n.startswith('__') or _n in _PLUMBING:
                continue
            _m.__dict__.setdefault(_n, getattr(_src, _n))
    for _n, _v in list(globals().items()):
        if _n.startswith('__') or _n in _PLUMBING:
            continue
        _m.__dict__.setdefault(_n, _v)
