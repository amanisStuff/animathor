"""Semantic mouse-motion domains and the main motion dispatcher.

The dispatcher lives here (rather than in a sibling module) so the package name
``controllers.mouse_motion`` remains the canonical import path for callers.
"""
from controllers.mouse_motion import guide_cut_motion, wave_motion, transform_motion  # noqa: F401
import copy  # noqa: F401
import math  # noqa: F401
import pygame  # noqa: F401
import config as cfg  # noqa: F401


def handle_mousemotion(ctx, event):
    from controllers.mouse_motion_parts import mm_part1, mm_part2, mm_part3
    if mm_part1(ctx, event):
        return
    if mm_part2(ctx, event):
        return
    if mm_part3(ctx, event):
        return
