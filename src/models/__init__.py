"""MVC Model package: data, geometry, wave math, hit tests."""

from models import geometry, strokes, waves, interaction, document  # noqa: F401

_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'document', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
_SUBS = (geometry, strokes, waves, interaction, document)
# export from submodules into package
for _m in _SUBS:
    for _n in dir(_m):
        if _n.startswith('__') or _n in _PLUMBING:
            continue
        globals()[_n] = getattr(_m, _n)
# cross-populate: every submodule sees every model name (resolves intra-model refs)
for _m in _SUBS:
    for _n, _v in list(globals().items()):
        if _n.startswith('__') or _n in _PLUMBING:
            continue
        _m.__dict__.setdefault(_n, _v)
