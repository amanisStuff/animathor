"""View: native file dialogs (tkinter)."""

try:
    import tkinter as tk
    from tkinter import filedialog as tk_filedialog
except Exception:
    tk = None
    tk_filedialog = None


def pick_reference_image_path():
    if tk is None or tk_filedialog is None:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        path = tk_filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp"), ("All files", "*.*")],
        )
        root.destroy()
        return path or None
    except Exception:
        return None
