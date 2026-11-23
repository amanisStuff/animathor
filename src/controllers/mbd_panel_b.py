"""Panel click helpers (split for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

# _handle_panel_click_b

def _handle_panel_click_b(ctx, event):
    _matched = False
    from controllers.mbd_panel_b_parts import handle_b_part1, handle_b_part2, handle_b_part3
    if handle_b_part1(ctx, event):
        return "handled"
    if handle_b_part2(ctx, event):
        return "handled"
    if handle_b_part3(ctx, event):
        return "handled"
    return None
