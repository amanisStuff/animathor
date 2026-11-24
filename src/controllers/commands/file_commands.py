"""File menu commands."""

from controllers.commands import ids as CMD  # noqa: E402
import copy
import config as cfg


def handle_file_command(ctx, key):
    if key == CMD.NEW:
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
        return True
    if key == CMD.SAVE:
        try:
            if ctx.document_path is None:
                ctx.document_path = ctx.pick_save_document_path()
            if ctx.document_path:
                ctx.save_document(ctx.document_path, ctx.strokes, {"view": {"zoom": ctx.cfg.VIEW_ZOOM, "pan": [ctx.cfg.VIEW_PAN_X, ctx.cfg.VIEW_PAN_Y]}, "artboards": list(ctx.artboards or []), "active_artboard": int(ctx.active_artboard), "symbols": copy.deepcopy(ctx.symbols), "shape_states": copy.deepcopy(ctx.shape_states)})
        except Exception:
            pass
        return True
    if key == CMD.SAVE_AS:
        try:
            path = ctx.pick_save_document_path()
            if path:
                ctx.document_path = path
                ctx.save_document(ctx.document_path, ctx.strokes, {"view": {"zoom": ctx.cfg.VIEW_ZOOM, "pan": [ctx.cfg.VIEW_PAN_X, ctx.cfg.VIEW_PAN_Y]}, "artboards": list(ctx.artboards or []), "active_artboard": int(ctx.active_artboard), "symbols": copy.deepcopy(ctx.symbols), "shape_states": copy.deepcopy(ctx.shape_states)})
        except Exception:
            pass
        return True
    if key == CMD.OPEN:
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
                ctx.symbols = copy.deepcopy(_syms) if isinstance(_syms, dict) else {}
                ctx._symbol_counter = 0
                try:
                    for _sid in ctx.symbols.keys():
                        if isinstance(_sid, str) and _sid.startswith("sym"):
                            _n = int(''.join(ch for ch in _sid[3:] if ch.isdigit()) or '0')
                            ctx._symbol_counter = max(ctx._symbol_counter, _n)
                except Exception:
                    pass
                _ssts = meta.get("shape_states")
                ctx.shape_states = copy.deepcopy(_ssts) if isinstance(_ssts, dict) else {}
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
        return True
    if key == CMD.IMPORT_SVG:
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
        return True
    if key == CMD.EXPORT:
        ctx.export_dialog_open = True
        ctx.help_open = False
        return True
    if key == CMD.QUIT:
        ctx.running = False
        return True
    return False
