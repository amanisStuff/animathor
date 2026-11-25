"""View menu commands (fit, zoom, guides, artboards, symbols, panel)."""
from controllers.commands import ids as CMD  # noqa: E402
import copy
import math
import pygame
import config as cfg



def dispatch_view_commands(ctx, key):
    if key == CMD.FIT:
        if ctx.strokes:
            bb = ctx.combined_bbox(ctx.strokes, list(range(len(ctx.strokes))))
            if bb is not None:
                bw = max(1.0, bb[2] - bb[0]); bh = max(1.0, bb[3] - bb[1])
                vh = ctx.cfg.canvas_viewport_height()
                z = min((ctx.cfg.CANVAS_W - 40) / bw, (vh - 40) / bh)
                ctx.cfg.VIEW_ZOOM = max(0.1, min(20.0, z))
                ctx.cfg.VIEW_PAN_X = (ctx.cfg.CANVAS_W - bw * ctx.cfg.VIEW_ZOOM) / 2 - bb[0] * ctx.cfg.VIEW_ZOOM
                ctx.cfg.VIEW_PAN_Y = (vh - bh * ctx.cfg.VIEW_ZOOM) / 2 - bb[1] * ctx.cfg.VIEW_ZOOM
        else:
            ctx.cfg.VIEW_ZOOM = 1.0; ctx.cfg.VIEW_PAN_X = 0.0; ctx.cfg.VIEW_PAN_Y = 0.0
    elif key == CMD.ACTUAL_SIZE:
        ctx.cfg.VIEW_ZOOM = 1.0; ctx.cfg.VIEW_PAN_X = 0.0; ctx.cfg.VIEW_PAN_Y = 0.0
    elif key == CMD.TOGGLE_PANEL:
        ctx.panel_collapsed = not ctx.panel_collapsed
        ctx.state["panel_collapsed"] = ctx.panel_collapsed
        ctx.relayout()
    elif key == CMD.TOGGLE_SNAP:
        ctx.snap_enabled = not ctx.snap_enabled
    elif key == CMD.TOGGLE_GRID:
        ctx.cfg.SHOW_GRID = not getattr(ctx.cfg, "SHOW_GRID", False)
        ctx.state["show_grid"] = ctx.cfg.SHOW_GRID
    elif key == CMD.TOGGLE_RULERS:
        ctx.cfg.SHOW_RULERS = not getattr(ctx.cfg, "SHOW_RULERS", False)
        ctx.state["show_rulers"] = ctx.cfg.SHOW_RULERS
    elif key == CMD.TOGGLE_GRID_SNAP:
        ctx.cfg.SNAP_TO_GRID = not getattr(ctx.cfg, "SNAP_TO_GRID", False)
        ctx.state["snap_to_grid"] = ctx.cfg.SNAP_TO_GRID
    elif key == CMD.CLEAR_GUIDES:
        guides = []
    return False


def dispatch_artboard_commands(ctx, key):
    if key == CMD.ARTBOARD_ADD:
        try:
            w = float(getattr(ctx.cfg, "CANVAS_W", 800))
            h = float(getattr(ctx.cfg, "canvas_viewport_height", lambda: getattr(ctx.cfg, "CANVAS_H", 600))())
        except Exception:
            w, h = 800.0, 600.0
        ctx.artboards.append({"name": f"Artboard {len(ctx.artboards)+1}", "x": 0.0, "y": 0.0, "w": max(1.0, w), "h": max(1.0, h)})
        ctx.active_artboard = len(ctx.artboards) - 1
    elif key == CMD.ARTBOARD_FIT_SELECTION:
        sel = [i for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
        bb = ctx.combined_bbox(ctx.strokes, sel) if sel else None
        if bb is None and ctx.strokes:
            bb = ctx.combined_bbox(ctx.strokes, list(range(len(ctx.strokes))))
        if bb is not None:
            x0, y0, x1, y1 = bb
            pad = 20.0
            ab = {"name": f"Artboard {len(ctx.artboards)+1}", "x": float(x0 - pad), "y": float(y0 - pad),
                  "w": float(max(1.0, (x1 - x0) + pad*2)), "h": float(max(1.0, (y1 - y0) + pad*2))}
            if 0 <= ctx.active_artboard < len(ctx.artboards):
                ab["name"] = ctx.artboards[ctx.active_artboard].get("name", ab["name"])
                ctx.artboards[ctx.active_artboard] = ab
            else:
                ctx.artboards.append(ab)
                ctx.active_artboard = len(ctx.artboards) - 1
    elif key == CMD.ARTBOARD_REMOVE:
        if 0 <= ctx.active_artboard < len(ctx.artboards):
            ctx.artboards.pop(ctx.active_artboard)
            if not ctx.artboards:
                ctx.active_artboard = -1
            else:
                ctx.active_artboard = min(ctx.active_artboard, len(ctx.artboards) - 1)
    elif key == CMD.ARTBOARD_NEXT:
        if ctx.artboards:
            ctx.active_artboard = (ctx.active_artboard + 1) % len(ctx.artboards)
        else:
            ctx.active_artboard = -1
    return False


def dispatch_symbol_commands(ctx, key):
    if key == CMD.SYMBOL_CREATE:
        sel = [i for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
        if sel:
            ctx.push_undo()
            ctx._symbol_counter += 1
            sid = f"sym{ctx._symbol_counter}"
            # Capture definition from selection (as a reusable master set).
            def_strokes = [ctx.copy.deepcopy(ctx.strokes[i]) for i in sel]
            # Normalize definition origin to (0,0) relative to its bbox top-left for stable placement.
            bb = ctx.combined_bbox(ctx.strokes, sel)
            ox, oy = (bb[0], bb[1]) if bb else (0.0, 0.0)
            norm_def = []
            for st in def_strokes:
                st.pop("symbol_id", None); st.pop("symbol_is_master", None); st.pop("symbol_instance_id", None)
                norm_def.append(ctx.translate_stroke(st, -ox, -oy))
            ctx.symbols[sid] = {"name": f"Symbol {ctx._symbol_counter}", "strokes": norm_def, "origin": [float(ox), float(oy)]}
            inst_id = f"{sid}:master"
            for i in sel:
                ctx.strokes[i]["symbol_id"] = sid
                ctx.strokes[i]["symbol_is_master"] = True
                ctx.strokes[i]["symbol_instance_id"] = inst_id
    elif key == CMD.SYMBOL_INSERT:
        # Choose symbol: from selection if present, else most recent/any available.
        sid = None
        for i in sorted(ctx.selected_strokes):
            if 0 <= i < len(ctx.strokes) and isinstance(ctx.strokes[i], dict) and ctx.strokes[i].get("symbol_id"):
                sid = ctx.strokes[i].get("symbol_id")
                break
        if sid is None and ctx.symbols:
            # prefer last created
            sid = list(ctx.symbols.keys())[-1]
        sdef = ctx.symbols.get(sid) if sid else None
        def_strokes = (sdef or {}).get("strokes") if isinstance(sdef, dict) else None
        if sid and isinstance(def_strokes, list) and def_strokes:
            ctx.push_undo()
            # Place offset from selection bbox or definition origin.
            offx = offy = 24.0
            if ctx.selected_strokes:
                bb = ctx.combined_bbox(ctx.strokes, [i for i in ctx.selected_strokes if 0 <= i < len(ctx.strokes)])
                if bb:
                    offx = (bb[2] - bb[0]) * 0.2 + 24.0
                    offy = (bb[3] - bb[1]) * 0.2 + 24.0
            origin = (sdef.get("origin") or [0.0, 0.0]) if isinstance(sdef, dict) else [0.0, 0.0]
            try:
                ox, oy = float(origin[0]), float(origin[1])
            except Exception:
                ox, oy = 0.0, 0.0
            ctx._symbol_counter += 1
            inst_id = f"{sid}:i{ctx._symbol_counter}"
            new_indices = []
            base = len(ctx.strokes)
            for st in ctx.copy.deepcopy(def_strokes):
                if not isinstance(st, dict):
                    continue
                nst = ctx.translate_stroke(st, ox + offx, oy + offy)
                nst["symbol_id"] = sid
                nst["symbol_is_master"] = False
                nst["symbol_instance_id"] = inst_id
                ctx.strokes.append(nst)
                new_indices.append(base)
                base += 1
            if new_indices:
                ctx.selected_strokes = set(new_indices)
                ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
    elif key == CMD.SYMBOL_UPDATE:
        # Update definition from master ctx.strokes of target symbol and propagate to instances.
        target_sid = None
        for i in sorted(ctx.selected_strokes):
            if 0 <= i < len(ctx.strokes) and isinstance(ctx.strokes[i], dict) and ctx.strokes[i].get("symbol_id"):
                target_sid = ctx.strokes[i].get("symbol_id")
                break
        if target_sid and target_sid in ctx.symbols:
            master_idx = [i for i, st in enumerate(ctx.strokes) if isinstance(st, dict) and st.get("symbol_id") == target_sid and st.get("symbol_is_master")]
            if not master_idx:
                # fall back to selected ctx.strokes if they belong to symbol
                master_idx = [i for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes) and isinstance(ctx.strokes[i], dict) and ctx.strokes[i].get("symbol_id") == target_sid]
            if master_idx:
                ctx.push_undo()
                mbb = ctx.combined_bbox(ctx.strokes, master_idx)
                mox, moy = (mbb[0], mbb[1]) if mbb else (0.0, 0.0)
                new_def = []
                for i in master_idx:
                    st = ctx.copy.deepcopy(ctx.strokes[i])
                    st.pop("symbol_id", None); st.pop("symbol_is_master", None); st.pop("symbol_instance_id", None)
                    new_def.append(ctx.translate_stroke(st, -mox, -moy))
                sdef = ctx.symbols.get(target_sid) or {}
                sdef = dict(sdef)
                sdef["strokes"] = new_def
                sdef["origin"] = [float(mox), float(moy)]
                ctx.symbols[target_sid] = sdef
                # Propagate to instance groups (preserve each instance bbox top-left).
                inst_groups = {}
                for i, st in enumerate(ctx.strokes):
                    if not isinstance(st, dict):
                        continue
                    if st.get("symbol_id") == target_sid and not st.get("symbol_is_master"):
                        iid = st.get("symbol_instance_id") or f"_idx_{i}"
                        inst_groups.setdefault(iid, []).append(i)
                # Replace from highest indices down to keep indices stable during removal.
                for iid, idxs in list(inst_groups.items()):
                    idxs = sorted(idxs)
                    if not idxs:
                        continue
                    ibb = ctx.combined_bbox(ctx.strokes, idxs)
                    ix, iy = (ibb[0], ibb[1]) if ibb else (mox, moy)
                    # remove old instance ctx.strokes
                    for j in reversed(idxs):
                        if 0 <= j < len(ctx.strokes):
                            ctx.strokes.pop(j)
                    # insert updated copies
                    insert_at = min(idxs) if idxs else len(ctx.strokes)
                    for st in ctx.copy.deepcopy(new_def):
                        if not isinstance(st, dict):
                            continue
                        nst = ctx.translate_stroke(st, ix, iy)
                        nst["symbol_id"] = target_sid
                        nst["symbol_is_master"] = False
                        nst["symbol_instance_id"] = iid
                        ctx.strokes.insert(insert_at, nst)
                        insert_at += 1
                # keep selection reasonable
                ctx.selected_strokes = set(master_idx) if master_idx else set()
                ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear()
    elif key == CMD.SYMBOL_DETACH:
        sel = [i for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
        if sel:
            ctx.push_undo()
            for i in sel:
                if isinstance(ctx.strokes[i], dict):
                    ctx.strokes[i].pop("symbol_id", None)
                    ctx.strokes[i].pop("symbol_is_master", None)
                    ctx.strokes[i].pop("symbol_instance_id", None)
    return False


def dispatch_shape_state_commands(ctx, key):
    if key == CMD.SHAPE_STATE_SAVE:
        sel = [i for i in sorted(ctx.selected_strokes) if 0 <= i < len(ctx.strokes)]
        if sel:
            ctx.push_undo()
            sid, _sc = ctx._capture_shape_state(ctx.strokes, sel, ctx.shape_states, ctx._shape_state_counter)
            ctx._shape_state_counter = _sc
    elif key == CMD.SHAPE_STATE_INSERT:
        ctx.push_undo()
        new_indices, _sc = ctx._insert_shape_state(ctx.strokes, ctx.shape_states, ctx._shape_state_counter, sorted(ctx.selected_strokes))
        ctx._shape_state_counter = _sc
        if new_indices:
            ctx.selected_strokes = set(new_indices)
            ctx.selected_point = None; ctx.selected_curve = None; ctx.selected_curves.clear(); ctx.redrawing_curve = None
    elif key == CMD.SHAPE_STATE_DELETE:
        sid = None
        for i in sorted(ctx.selected_strokes):
            if 0 <= i < len(ctx.strokes) and isinstance(ctx.strokes[i], dict) and ctx.strokes[i].get("shape_state_id"):
                sid = ctx.strokes[i].get("shape_state_id")
                break
        if sid is None and ctx.shape_states:
            sid = list(ctx.shape_states.keys())[-1]
        if sid and sid in ctx.shape_states:
            ctx.push_undo()
            ctx._delete_shape_state(ctx.shape_states, sid, ctx.strokes)
    return False


def _menu_view(ctx, key):

    for handler in (dispatch_view_commands, dispatch_artboard_commands,

                    dispatch_symbol_commands, dispatch_shape_state_commands):

        if handler(ctx, key):

            return True

    return True
