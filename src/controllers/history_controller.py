"""Controller: undo/redo history (extracted from app_controller for SRP)."""
import copy


def push_undo(undo_stack, redo_stack, strokes, max_undo=100):
    try:
        undo_stack.append(copy.deepcopy(strokes))
    except Exception:
        undo_stack.append(list(strokes))
    if len(undo_stack) > max_undo:
        del undo_stack[0:len(undo_stack) - max_undo]
    redo_stack.clear()


def do_undo(undo_stack, redo_stack, strokes):
    if not undo_stack:
        return False
    try:
        redo_stack.append(copy.deepcopy(strokes))
    except Exception:
        redo_stack.append(list(strokes))
    restored = undo_stack.pop()
    strokes.clear()
    strokes.extend(restored)
    return True


def do_redo(undo_stack, redo_stack, strokes):
    if not redo_stack:
        return False
    try:
        undo_stack.append(copy.deepcopy(strokes))
    except Exception:
        undo_stack.append(list(strokes))
    restored = redo_stack.pop()
    strokes.clear()
    strokes.extend(restored)
    return True
