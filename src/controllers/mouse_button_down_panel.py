"""Controller: MOUSEBUTTONDOWN button 1 handler (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *
from controllers.mbd_panel_a import _handle_panel_click_a
from controllers.mbd_panel_b import _handle_panel_click_b
from controllers.mbd_panel_c import _handle_panel_click_c

# Panel click helpers

def _handle_panel_click(ctx, event):
    for _fn in (_handle_panel_click_a, _handle_panel_click_b, _handle_panel_click_c):
        _r = _fn(ctx, event)
        if _r == 'continue':
            return 'continue'
        if _r == 'handled':
            return None
    return None




