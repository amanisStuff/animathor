"""Controller: menu action handler (extracted from app_controller.main for SRP)."""
import copy
import math
import pygame
import config as cfg
from models import *
from views import *
from controllers.coordinates import *
from controllers.menu_actions_view import _menu_tools
from controllers.menu_actions_view import _menu_view

def run_menu_action(ctx, key):
    """Execute a menu command.

    Keyboard shortcuts and menu clicks both funnel through here so a
    command behaves identically no matter how it was invoked.
    """

    if _menu_file(ctx, key): return
    if _menu_edit(ctx, key): return
    if _menu_view(ctx, key): return
    if _menu_tools(ctx, key): return

def _menu_file(ctx, key):
    if key == "new":
        ctx._bezier_pen_cancel()
        ctx.push_undo()
        ctx.strokes.clear()
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None
        ctx.selected_curves.clear(); ctx.transform_drag = None; ctx.drag_last = None
        ctx.redrawing_curve = None
        ctx.document_path = None
        ctx.artboards = []
        ctx.active_artboard = -1
        ctx.symbols = {}
        ctx._symbol_counter = 0
        ctx.shape_states = {}
        ctx._shape_state_counter = 0
    elif key == "save":
        try:
            if ctx.document_path is None:
                ctx.document_path = ctx.pick_save_document_path()
            if ctx.document_path:
                ctx.save_document(ctx.document_path, ctx.strokes, {"view": {"zoom": ctx.cfg.VIEW_ZOOM, "pan": [ctx.cfg.VIEW_PAN_X, ctx.cfg.VIEW_PAN_Y]}, "artboards": list(ctx.artboards or []), "active_artboard": int(ctx.active_artboard), "symbols": ctx.copy.deepcopy(ctx.symbols), "shape_states": ctx.copy.deepcopy(ctx.shape_states)})
        except Exception:
            pass
    elif key == "save_as":
        try:
            path = ctx.pick_save_document_path()
            if path:
                ctx.document_path = path
                ctx.save_document(ctx.document_path, ctx.strokes, {"view": {"zoom": ctx.cfg.VIEW_ZOOM, "pan": [ctx.cfg.VIEW_PAN_X, ctx.cfg.VIEW_PAN_Y]}, "artboards": list(ctx.artboards or []), "active_artboard": int(ctx.active_artboard), "symbols": ctx.copy.deepcopy(ctx.symbols), "shape_states": ctx.copy.deepcopy(ctx.shape_states)})
        except Exception:
            pass
    elif key == "open":
        try:
            path = ctx.pick_open_document_path()
            if path:
                loaded, meta = ctx.load_document_with_meta(path)
                ctx._bezier_pen_cancel()
                ctx.push_undo()
                ctx.strokes.clear(); ctx.strokes.extend(loaded)
                ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
                ctx.transform_drag = None; ctx.drag_last = None; ctx.redrawing_curve = None
                ctx.document_path = path
                # Restore the saved camera, ctx.artboards, and ctx.symbols.
                meta = meta or {}
                view = meta.get("view") or {}
                if isinstance(view, dict):
                    if isinstance(view.get("zoom"), (int, float)):
                        ctx.cfg.VIEW_ZOOM = max(0.1, min(20.0, float(view["zoom"])))
                    pan = view.get("pan")
                    if isinstance(pan, (list, tuple)) and len(pan) == 2:
                        ctx.cfg.VIEW_PAN_X = float(pan[0]); ctx.cfg.VIEW_PAN_Y = float(pan[1])
                _abs = meta.get("artboards")
                ctx.artboards = [dict(a) for a in _abs] if isinstance(_abs, list) else []
                try:
                    ctx.active_artboard = int(meta.get("active_artboard", -1))
                except Exception:
                    ctx.active_artboard = -1
                if not (0 <= ctx.active_artboard < len(ctx.artboards)):
                    ctx.active_artboard = -1
                _syms = meta.get("symbols")
                ctx.symbols = ctx.copy.deepcopy(_syms) if isinstance(_syms, dict) else {}
                ctx._symbol_counter = 0
                try:
                    for _sid in ctx.symbols.keys():
                        if isinstance(_sid, str) and _sid.startswith("sym"):
                            _n = int(''.join(ch for ch in _sid[3:] if ch.isdigit()) or '0')
                            ctx._symbol_counter = max(ctx._symbol_counter, _n)
                except Exception:
                    pass
                _ssts = meta.get("shape_states")
                ctx.shape_states = ctx.copy.deepcopy(_ssts) if isinstance(_ssts, dict) else {}
                ctx._shape_state_counter = 0
                try:
                    for _sid in ctx.shape_states.keys():
                        if isinstance(_sid, str) and _sid.startswith("shape"):
                            _n = int(''.join(ch for ch in _sid[len("shape"):] if ch.isdigit()) or '0')
                            ctx._shape_state_counter = max(ctx._shape_state_counter, _n)
                except Exception:
                    pass
        except Exception:
            pass
    elif key == "import_svg":
        try:
            path = ctx.pick_import_svg_path()
            if path:
                imported = ctx.import_svg(path)
                if imported:
                    ctx._bezier_pen_cancel()
                    ctx.push_undo()
                    ctx.strokes.clear(); ctx.strokes.extend(imported)
                    ctx.selected_strokes.clear(); ctx.selected_point = None
                    ctx.selected_curve = None; ctx.selected_curves.clear()
                    ctx.transform_drag = None; ctx.drag_last = None; ctx.redrawing_curve = None
                    ctx.document_path = None
                    ctx.artboards = []
                    ctx.active_artboard = -1
                    ctx.symbols = {}
                    ctx._symbol_counter = 0
                    ctx.shape_states = {}
                    ctx._shape_state_counter = 0
        except Exception:
            pass
    elif key == "export":
        ctx.export_dialog_open = True
        ctx.help_open = False
    elif key == "quit":
        ctx.running = False
    return True
    return False

def _menu_edit(ctx, key):
    if key == "undo":
        ctx._bezier_pen_cancel()
        if ctx.do_undo():
            ctx.selected_strokes = {i for i in ctx.selected_strokes if 0 <= i < len(ctx.strokes)}
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
    elif key == "redo":
        ctx._bezier_pen_cancel()
        if ctx.do_redo():
            ctx.selected_strokes = {i for i in ctx.selected_strokes if 0 <= i < len(ctx.strokes)}
        ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
    elif key == "select_all":
        ctx.selected_strokes = set(range(len(ctx.strokes)))
        ctx.selected_point = None; ctx.selected_curve = None
    elif key == "duplicate":
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
    elif key == "group":
        if len(ctx.selected_strokes) >= 2:
            ctx.push_undo()
            new_group = ctx.new_group_id()
            for i in sorted(ctx.selected_strokes):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes[i] = ctx.assign_group(ctx.strokes[i], new_group)
    elif key == "ungroup":
        if ctx.selected_strokes:
            ctx.push_undo()
            for i in sorted(ctx.selected_strokes):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes[i] = ctx.clear_group(ctx.strokes[i])
    elif key == "copy":
        if ctx.selected_strokes:
            ctx.clipboard_strokes = [ctx._copy_stroke(ctx.strokes[i]) for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
    elif key == "cut":
        if ctx.selected_strokes:
            ctx.clipboard_strokes = [ctx._copy_stroke(ctx.strokes[i]) for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
            ctx.push_undo()
            for i in sorted(ctx.selected_strokes, reverse=True):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes.pop(i)
            ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
    elif key == "paste":
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
    elif key == "delete":
        if ctx.selected_strokes:
            ctx.push_undo()
            for i in sorted(ctx.selected_strokes, reverse=True):
                if 0 <= i < len(ctx.strokes):
                    ctx.strokes.pop(i)
            ctx.selected_strokes.clear(); ctx.selected_point = None; ctx.transform_drag = None; ctx.selected_curve = None
    return True
    return False


