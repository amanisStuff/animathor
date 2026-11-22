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


def pick_import_svg_path():
    return _tk_call(lambda root: tk_filedialog.askopenfilename(
        title="Import SVG",
        filetypes=[("SVG image", "*.svg"), ("All files", "*.*")],
    ))


def pick_save_document_path():
    return _tk_call(lambda root: tk_filedialog.asksaveasfilename(
        title="Save drawing",
        defaultextension=".athors",
        filetypes=[("Animathor drawing", "*.athors"), ("Animathor JSON", "*.anim.json"), ("JSON", "*.json"), ("All files", "*.*")],
    ))


def pick_export_image_path(default_format="png"):
    fmt = str(default_format or "png").lower().lstrip(".")
    ext_map = {
        "png": ".png",
        "svg": ".svg",
        "pdf": ".pdf",
        "eps": ".eps",
        "jpg": ".jpg",
        "jpeg": ".jpg",
        "webp": ".webp",
    }
    defaultextension = ext_map.get(fmt, ".png")
    filetypes = [
        ("PNG image", "*.png"),
        ("SVG image", "*.svg"),
        ("PDF document", "*.pdf"),
        ("EPS document", "*.eps"),
        ("JPEG image", "*.jpg *.jpeg"),
        ("WebP image", "*.webp"),
        ("All files", "*.*"),
    ]
    preferred = {
        "png": ("PNG image", "*.png"),
        "svg": ("SVG image", "*.svg"),
        "pdf": ("PDF document", "*.pdf"),
        "eps": ("EPS document", "*.eps"),
        "jpg": ("JPEG image", "*.jpg *.jpeg"),
        "jpeg": ("JPEG image", "*.jpg *.jpeg"),
        "webp": ("WebP image", "*.webp"),
    }.get(fmt)
    if preferred and preferred in filetypes:
        filetypes = [preferred] + [ft for ft in filetypes if ft != preferred]
    return _tk_call(lambda root: tk_filedialog.asksaveasfilename(
        title="Export image",
        defaultextension=defaultextension,
        filetypes=filetypes,
    ))


def pick_export_png_path():
    return pick_export_image_path()
