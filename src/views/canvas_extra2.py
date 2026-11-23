"""View: cairo canvas rendering and reference image handling."""

import math
import os

try:
    import cairo  # pycairo (often bundles Cairo on Windows)
    CAIRO_BACKEND = "pycairo"
except Exception:
    import cairocffi as cairo  # type: ignore
    CAIRO_BACKEND = "cairocffi"

import pygame

import config as cfg
from config import *
from bezier import stroke_to_beziers, fit_single_cubic_bezier, cubic_bezier_point, cubic_bezier_derivative

import models as _dep
_PLUMBING = {'_m', '_n', '_mod', '_name', 'cfg', 'math', 'copy', 'pygame', 'cairo', '_models', '_views', '_m_geometry', '_m_strokes', '_m_waves', '_v_canvas', 'geometry', 'strokes', 'waves', 'interaction', 'canvas', 'panel', 'toolbar', 'widgets', 'dialogs', 'app_controller', 'coordinates'}
for _n in dir(_dep):
    if _n.startswith('__') or _n in _PLUMBING:
        continue
    globals().setdefault(_n, getattr(_dep, _n))




def _resolve_export_artboard(artboard, size, view_zoom, view_pan):
    """Return (base_size, view_zoom, view_pan) adjusted for an active artboard."""
    if isinstance(artboard, dict):
        try:
            ax = float(artboard.get("x", 0.0)); ay = float(artboard.get("y", 0.0))
            aw = float(artboard.get("w", 0.0)); ah = float(artboard.get("h", 0.0))
            if aw > 0 and ah > 0:
                return (max(1, int(round(aw))), max(1, int(round(ah)))), 1.0, (-ax, -ay)
        except Exception:
            pass
    return _export_base_size(size), view_zoom, view_pan

def _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=None):
    draw_scene(surf, strokes, ref_img=ref_img, view_zoom=view_zoom,
               view_pan=view_pan, for_export=True, export_scale=scale)

def _raster_surface(w, h, scale):
    sw = max(1, int(round(w * scale)))
    sh = max(1, int(round(h * scale)))
    return make_cairo_surface(sw, sh)

def _png_bytes(surf):
    import io
    buf = io.BytesIO()
    surf.write_to_png(buf)
    buf.seek(0)
    return buf

def export_scene_png(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, dpi=None, artboard=None):
    """Export the current scene to a PNG file (viewport- or artboard-sized)."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    surf = _raster_surface(w, h, scale)
    _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=artboard)
    if dpi:
        # Cairo does not embed pHYs metadata; Pillow does.
        from PIL import Image
        img = Image.open(_png_bytes(surf)).convert("RGBA")
        img.save(path, "PNG", dpi=(float(dpi), float(dpi)))
    else:
        surf.write_to_png(path)

def export_scene_svg(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, artboard=None):
    """Export the current scene to an SVG file (viewport- or artboard-sized)."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    surf = cairo.SVGSurface(str(path), w * scale, h * scale)
    try:
        _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=artboard)
        try:
            surf.flush()
        except Exception:
            pass
    finally:
        try:
            surf.finish()
        except Exception:
            pass

def export_scene_pdf(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, dpi=None, artboard=None):
    """Export to PDF. ``dpi`` sets the physical page size (72 pt/in)."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    factor = 72.0 / float(dpi) if dpi and float(dpi) > 0 else 1.0
    surf = cairo.PDFSurface(str(path), w * factor, h * factor)
    try:
        _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale * factor, artboard=artboard)
    finally:
        try:
            surf.finish()
        except Exception:
            pass

def export_scene_eps(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                     size=None, scale=1.0, dpi=None, artboard=None):
    """Export to Encapsulated PostScript. ``dpi`` sets the page size."""
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    factor = 72.0 / float(dpi) if dpi and float(dpi) > 0 else 1.0
    surf = cairo.PSSurface(str(path), w * factor, h * factor)
    try:
        try:
            surf.set_eps(True)
        except Exception:
            pass
        _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale * factor, artboard=artboard)
    finally:
        try:
            surf.finish()
        except Exception:
            pass

def export_scene_raster(path, strokes, fmt, ref_img=None, view_zoom=1.0,
                        view_pan=(0.0, 0.0), size=None, scale=1.0, dpi=None, quality=92, artboard=None):
    """Export to JPEG or WebP via Pillow (Cairo only writes PNG natively)."""
    from PIL import Image
    (w, h), view_zoom, view_pan = _resolve_export_artboard(artboard, size, view_zoom, view_pan)
    scale = normalize_export_scale(scale)
    surf = _raster_surface(w, h, scale)
    _draw_export(surf, strokes, ref_img, view_zoom, view_pan, scale, artboard=artboard)
    img = Image.open(_png_bytes(surf)).convert("RGBA")
    save_kwargs = {"quality": int(quality)}
    if fmt == "JPEG":
        # JPEG has no alpha channel: flatten onto white.
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    if dpi:
        save_kwargs["dpi"] = (float(dpi), float(dpi))
    img.save(path, fmt, **save_kwargs)

def export_scene_image(path, strokes, ref_img=None, view_zoom=1.0, view_pan=(0.0, 0.0),
                       size=None, scale=1.0, dpi=None, artboard=None):
    """Export the scene using the file extension to select the format.

    Supported: PNG, SVG, PDF, EPS, JPG/JPEG, WebP. Unknown extensions raise
    ``ValueError`` instead of silently writing PNG bytes under a wrong name.
    If ``artboard`` is provided, export is cropped/sized to that artboard.
    """
    fmt = export_format_for(path)
    if fmt is None:
        raise ValueError(f"Unsupported export format: {path}")
    kwargs = dict(ref_img=ref_img, view_zoom=view_zoom, view_pan=view_pan,
                  size=size, scale=scale, artboard=artboard)
    if fmt in ("PNG", "PDF", "EPS", "JPEG", "WEBP"):
        kwargs["dpi"] = dpi
    if fmt == "PNG":
        export_scene_png(path, strokes, **kwargs)
    elif fmt == "SVG":
        export_scene_svg(path, strokes, **kwargs)
    elif fmt == "PDF":
        export_scene_pdf(path, strokes, **kwargs)
    elif fmt == "EPS":
        export_scene_eps(path, strokes, **kwargs)
    else:
        export_scene_raster(path, strokes, fmt, **kwargs)

def _pygame_image_to_cairo_surface(path):
    """Load any pygame-supported image and copy its pixels into a cairo surface.

    Returns a cairo.ImageSurface (ARGB32) or None. The pixels are copied into
    the surface's own buffer, so there is no external buffer whose lifetime we
    have to track. (pycairo surfaces are C objects and cannot hold a reference
    to a Python buffer as an attribute, which previously made every non-PNG
    load fail silently.)
    """
    try:
        img = pygame.image.load(path)
    except Exception:
        return None
    try:
        img = img.convert_alpha()
    except Exception:
        # No display / conversion unavailable: use the loaded surface as-is.
        pass
    w, h = img.get_size()
    if w <= 0 or h <= 0:
        return None
    try:
        data = pygame.image.tobytes(img, "BGRA")
    except AttributeError:  # older pygame
        data = pygame.image.tostring(img, "BGRA")
    try:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        view = surf.get_data()
        view[:len(data)] = data
        # We wrote straight into the surface's buffer, so tell cairo the pixels
        # changed. Without this it can keep painting a stale (blank) snapshot.
        try:
            surf.mark_dirty()
        except Exception:
            pass
        return surf
    except Exception:
        return None

def load_reference_image(path):
    """Load image file into a cairo ImageSurface (ARGB32) for reference drawing.

    PNG uses cairo's native loader (fast and exact). Everything else — and any
    PNG cairo cannot decode — goes through pygame, so JPG/JPEG/BMP/GIF/WEBP all
    work consistently. Returns None only if the file genuinely cannot be read.
    """
    if not path:
        return None
    surf = None
    # Prefer cairo's PNG loader when possible.
    if str(path).lower().endswith(".png"):
        try:
            surf = cairo.ImageSurface.create_from_png(path)
        except Exception:
            surf = None
    # Fall back to pygame for other formats and unreadable PNGs.
    if surf is None:
        surf = _pygame_image_to_cairo_surface(path)
        if surf is None:
            return None
    w, h = surf.get_width(), surf.get_height()
    return {"surface": surf, "w": w, "h": h, "x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 0.5, "visible": True, "path": path}

