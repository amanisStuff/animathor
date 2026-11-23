"""Controller: mouse motion handler (extracted for SRP)."""
import copy, math, pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *

def handle_mousemotion(ctx, event):
    for _k in ('drag_last','pending_transform_toggle','smart_snap_guides','start_strokes','pivot_pos','guides','wave_custom_drag'):
        from controllers.mouse_motion_parts import mm_part1, mm_part2, mm_part3
        if mm_part1(ctx, event): return
        if mm_part2(ctx, event): return
        if mm_part3(ctx, event): return
