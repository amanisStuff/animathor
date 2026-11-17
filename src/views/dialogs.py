"""View: native file dialogs (tkinter)."""

try:
    import tkinter as tk
    from tkinter import filedialog as tk_filedialog
except Exception:
    tk = None
    tk_filedialog = None


def _tk_call(fn):
    if tk is None or tk_filedialog is None:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        try:
            path = fn(root)
        finally:
            try:
                root.destroy()
            except Exception:
                pass
        return path or None
    except Exception:
        return None


def pick_reference_image_path():
    return _tk_call(lambda root: tk_filedialog.askopenfilename(
        title="Select reference image",
        filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All files", "*.*")],
    ))


def pick_open_document_path():
    return _tk_call(lambda root: tk_filedialog.askopenfilename(
        title="Open drawing",
        filetypes=[("Animathor drawing", "*.athors"), ("Animathor JSON", "*.anim.json;*.json"), ("All files", "*.*")],
    ))


def pick_save_document_path():
    return _tk_call(lambda root: tk_filedialog.asksaveasfilename(
        title="Save drawing",
        defaultextension=".athors",
        filetypes=[("Animathor drawing", "*.athors"), ("Animathor JSON", "*.anim.json"), ("JSON", "*.json"), ("All files", "*.*")],
    ))


def pick_export_image_path():
    return _tk_call(lambda root: tk_filedialog.asksaveasfilename(
        title="Export image",
        defaultextension=".png",
        filetypes=[("PNG image", "*.png"), ("SVG image", "*.svg"), ("All files", "*.*")],
    ))


def pick_export_png_path():
    return pick_export_image_path()
