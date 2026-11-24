"""Edit menu commands."""

import copy
from models import *  # noqa: F401,F403
from views import *  # noqa: F401,F403
from controllers.coordinates import *  # noqa: F401,F403


def handle_edit_command(ctx, key):
    if key == "undo":
        ctx._bezier_pen_cancel()
        if ctx.do_undo():
            ctx.selected_strokes = {i for i in ctx.selected_strokes if 0 <= i < len(ctx.strokes)}
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
        return True
    if key == "redo":
        ctx._bezier_pen_cancel()
        if ctx.do_redo():
            ctx.selected_strokes = {i for i in ctx.selected_strokes if 0 <= i < len(ctx.strokes)}
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
        return True
    if key == "select_all":
        ctx.selected_strokes = set(range(len(ctx.strokes)))
        ctx.selected_point = None; ctx.selected_curve = None
        return True
    if key == "duplicate":
        if ctx.selected_strokes:
            ctx.push_undo()
            new_sel = set()
            for i in sorted(ctx.selected_strokes):
                if 0 <= i < len(ctx.strokes):
                    dup = ctx._copy_stroke(ctx.strokes[i])
                    ctx.translate_stroke(dup, 16, 16)
                    ctx.strokes.append(dup)
                    new_sel.add(len(ctx.strokes) - 1)
            if new_sel:
                ctx.selected_strokes = new_sel
                ctx.selected_point = None; ctx.selected_curve = None
        return True
    if key == "group":
        if len(ctx.selected_strokes) >= 2:
            ctx.push_undo()
            new_group = ctx.new_group_id()
            for i in sorted(ctx.selected_strokes):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes[i] = ctx.assign_group(ctx.strokes[i], new_group)
        return True
    if key == "ungroup":
        if ctx.selected_strokes:
            ctx.push_undo()
            for i in sorted(ctx.selected_strokes):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes[i] = ctx.clear_group(ctx.strokes[i])
        return True
    if key == "copy":
        if ctx.selected_strokes:
            ctx.clipboard_strokes = [ctx._copy_stroke(ctx.strokes[i]) for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
        return True
    if key == "cut":
        if ctx.selected_strokes:
            ctx.clipboard_strokes = [ctx._copy_stroke(ctx.strokes[i]) for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
            ctx.push_undo()
            for i in sorted(ctx.selected_strokes, reverse=True):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes.pop(i)
            ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
        return True
    if key == "paste":
        if ctx.clipboard_strokes:
            ctx.push_undo()
            new_sel = set()
            for st in ctx.clipboard_strokes:
                dup = ctx._copy_stroke(st)
                ctx.translate_stroke(dup, 16, 16)
                ctx.strokes.append(dup)
                new_sel.add(len(ctx.strokes) - 1)
            if new_sel:
                ctx.selected_strokes = new_sel
                ctx.selected_point = None; ctx.selected_curve = None
        return True
    if key == "delete":
        if ctx.selected_strokes:
            ctx.push_undo()
            for i in sorted(ctx.selected_strokes, reverse=True):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes.pop(i)
            ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None
        return True
    return False
