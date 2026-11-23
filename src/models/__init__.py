"""MVC Model package: data, geometry, wave math, hit tests."""

from models import geometry, strokes, waves, waves_extra, interaction, document, svg, appearance, organization, text, guides, pattern, markers  # noqa: F401

_PLUMBING = {'_m', '_n', '_mod', '_name', '_SUBS', '_PLUMBING', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_m_waves_extra', '_v_canvas', '_m_svg', '_m_appearance', '_m_organization', '_m_text', '_m_guides', '_m_pattern', '_m_markers', 'geometry', 'strokes', 'waves', 'waves_extra', 'interaction', 'document', 'svg', 'appearance', 'organization', 'text', 'guides', 'pattern', 'markers', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
_SUBS = (geometry, strokes, waves, waves_extra, interaction, document, svg, appearance, organization, text, guides, pattern, markers)
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
