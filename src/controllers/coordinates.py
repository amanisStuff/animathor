"""Controller: window <-> canvas coordinate mapping."""

import config as cfg

import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))


def to_canvas(pos):
    """Convert a screen position to world/canvas coordinates (view-aware)."""
    z = getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0
    px = getattr(cfg, "VIEW_PAN_X", 0.0)
    py = getattr(cfg, "VIEW_PAN_Y", 0.0)
    return ((pos[0] - cfg.CANVAS_X - px) / z, (pos[1] - py) / z)

def in_canvas(pos):
    """True if the screen position is over the canvas viewport area."""
    return cfg.CANVAS_X <= pos[0] < cfg.CANVAS_X + cfg.CANVAS_W and 0 <= pos[1] < cfg.HEIGHT

def clamp_to_canvas(pos):
    """Map any window position to the nearest world point visible in the canvas viewport."""
    sx = clamp(pos[0], cfg.CANVAS_X, cfg.CANVAS_X + cfg.CANVAS_W - 1)
    sy = clamp(pos[1], 0, cfg.HEIGHT - 1)
    return to_canvas((sx, sy))

def to_screen(world_pos):
    """Convert world/canvas coordinates to a screen position (view-aware)."""
    z = getattr(cfg, "VIEW_ZOOM", 1.0) or 1.0
    px = getattr(cfg, "VIEW_PAN_X", 0.0)
    py = getattr(cfg, "VIEW_PAN_Y", 0.0)
    return (world_pos[0] * z + px + cfg.CANVAS_X, world_pos[1] * z + py)
