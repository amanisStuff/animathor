"""Controller: window <-> canvas coordinate mapping."""

import config as cfg

import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))


def to_canvas(pos):
    return (pos[0] - cfg.CANVAS_X, pos[1])

def in_canvas(pos):
    return cfg.CANVAS_X <= pos[0] < cfg.CANVAS_X + cfg.CANVAS_W and 0 <= pos[1] < cfg.HEIGHT

def clamp_to_canvas(pos):
    """Map any window position to the nearest point inside the canvas."""
    cx = clamp(pos[0] - cfg.CANVAS_X, 0, cfg.CANVAS_W - 1)
    cy = clamp(pos[1], 0, cfg.HEIGHT - 1)
    return (cx, cy)
