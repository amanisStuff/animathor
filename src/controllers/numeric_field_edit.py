"""Double-click text entry for draggable numeric panel fields.

A single click keeps the existing scrub behavior. A second click on the same
field within ``DOUBLE_CLICK_MS`` opens an inline editor: digits, ``.`` and ``-``
replace/append to the buffer, Enter commits and Escape cancels. The editor is a
modal input state so global shortcuts cannot fire while a value is being typed.
"""

from __future__ import annotations

import math

import pygame

from models.appearance import (
    get_appearance as _default_get_appearance,
    set_appearance as _default_set_appearance,
)
from models.geometry import (
    clamp as _default_clamp,
    color_alpha as _default_color_alpha,
    get_gradient_stop_color as _default_get_gradient_stop_color,
    set_color_alpha as _default_set_color_alpha,
    set_gradient_stop_color as _default_set_gradient_stop_color,
)
from models.strokes import _stroke_components as _default_stroke_components
from models.waves import _get_distortion_style as _default_get_distortion_style

DOUBLE_CLICK_MS = 400
DOUBLE_CLICK_DIST = 8

# Wave parameters that the scrub path quantises to whole numbers.
_WAVE_INTEGER_KEYS = frozenset({
    "amplitude", "noise", "phase", "seed", "amount",
    "location", "handle_rotate", "handle_length",
})


def _rect(value):
    return pygame.Rect(value) if value is not None else pygame.Rect(0, 0, 0, 0)


def _clamp(ctx, value, lo, hi):
    fn = getattr(ctx, "clamp", _default_clamp)
    return float(fn(value, lo, hi))


def _selected_component(ctx):
    """Return ``(si, comp_i, comps)`` for the active curve component."""
    curve = getattr(ctx, "selected_curve", None)
    selected = getattr(ctx, "selected_strokes", None) or set()
    if not curve or len(curve) < 2 or curve[0] not in selected:
        return None
    si, comp_i = curve[0], curve[1]
    strokes = getattr(ctx, "strokes", None) or []
    if not (0 <= si < len(strokes)):
        return None
    comps_fn = getattr(ctx, "_stroke_components", _default_stroke_components)
    comps = comps_fn(strokes[si])
    if not (0 <= comp_i < len(comps)):
        return None
    return si, comp_i, comps


def _wave_value(ctx, comps, comp_i, key, lo):
    wi = int((getattr(ctx, "state", None) or {}).get("wave_active_index", 0) or 0)
    getter = getattr(ctx, "_get_distortion_style", _default_get_distortion_style)
    wave = getter(comps[comp_i], wi)
    return float(wave.get(key, lo) or 0.0)


def _opacity_value(ctx, kind):
    strokes = getattr(ctx, "strokes", None) or []
    selected = sorted(int(i) for i in (getattr(ctx, "selected_strokes", None) or set()))
    primary = selected[0] if selected else -1
    if not (0 <= primary < len(strokes)):
        return 1.0
    stroke = strokes[primary]
    if kind == "ref_opacity":
        ref = getattr(ctx, "reference_image", None)
        return float(ref.get("opacity", 0.5)) if ref is not None else 0.5
    getter = getattr(ctx, "get_appearance", _default_get_appearance)
    return float(getter(stroke).get("opacity", 1.0))


def _alpha_value(ctx):
    state = getattr(ctx, "state", None) or {}
    strokes = getattr(ctx, "strokes", None) or []
    color_alpha_fn = getattr(ctx, "color_alpha", _default_color_alpha)
    target = state.get("color_target", getattr(ctx, "color_target", "stroke"))
    selected = sorted(int(i) for i in (getattr(ctx, "selected_strokes", None) or set()))
    primary = selected[0] if selected else -1
    curve_style = None
    if (getattr(ctx, "selection_submode", None) == "curve"
            and getattr(ctx, "selected_curve", None)
            and len(selected) == 1 and selected[0] in selected):
        comp = _selected_component(ctx)
        if comp is not None:
            si, comp_i, comps = comp
            fn = getattr(ctx, "_effective_component_style", None)
            if callable(fn):
                curve_style = fn(strokes[si], comp_i)[0]
    if curve_style is not None:
        return float(color_alpha_fn(curve_style, 1.0))
    if not (0 <= primary < len(strokes)):
        return 1.0
    stroke = strokes[primary]
    if target == "stroke":
        return float(color_alpha_fn(stroke.get("stroke_color"), 1.0))
    gradient_fn = getattr(ctx, "get_fill_gradient", None)
    fg = gradient_fn(stroke) if callable(gradient_fn) else None
    if fg is not None:
        stop_fn = getattr(ctx, "get_gradient_stop_color", _default_get_gradient_stop_color)
        stop_i = int(state.get("fill_gradient_stop", 0) or 0)
        return float(color_alpha_fn(stop_fn(fg, stop_i), 1.0))
    return float(color_alpha_fn(stroke.get("fill_color"), 1.0))


def _make_spec(kind, key, rect, lo, hi, value, *, step=None, decimals=None,
               scale=1.0, suffix="", label="", identity=None):
    return {
        "id": identity or f"{kind}:{key or ''}",
        "kind": kind,
        "key": key,
        "rect": _rect(rect),
        "lo": float(lo),
        "hi": float(hi),
        "value": float(value),
        "step": step,
        "decimals": decimals,
        "scale": float(scale),
        "suffix": suffix,
        "label": label,
    }


def specifications(ctx):
    """List editable numeric fields currently visible in the panel."""
    state = getattr(ctx, "state", None) or {}
    specs = []

    slider = getattr(ctx, "slider", None)
    if slider is not None and getattr(slider, "enabled", True) and slider.rect.w > 0:
        specs.append(_make_spec(
            "points", None, slider.rect, slider.min_v, slider.max_v,
            slider.value, step=1.0, label="Points", identity="points",
        ))

    cut = getattr(ctx, "cut_gap_slider", None)
    if cut is not None and cut.rect.w > 0:
        specs.append(_make_spec(
            "cut_gap", None, cut.rect, cut.min_v, cut.max_v, cut.value,
            step=1.0, label="Cut gap", identity="cut_gap",
        ))

    width = getattr(ctx, "width_slider", None)
    if width is not None and getattr(width, "enabled", True) and width.rect.w > 0:
        specs.append(_make_spec(
            "stroke_width", None, width.rect, width.min_v, width.max_v,
            width.value, label="Stroke width", identity="stroke_width",
        ))

    comp = _selected_component(ctx)
    if comp is not None:
        _si, comp_i, comps = comp
        for key, entry in (state.get("wave_slider_rects") or {}).items():
            if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                continue
            rect, lo, hi = entry
            if not _rect(rect).w:
                continue
            integer = key in _WAVE_INTEGER_KEYS
            specs.append(_make_spec(
                "wave", key, rect, lo, hi,
                _wave_value(ctx, comps, comp_i, key, lo),
                step=1.0 if integer else None,
                decimals=0 if integer else 2,
                label=str(key).replace("_", " ").title(),
                identity=f"wave:{key}",
            ))

    if _rect(state.get("obj_opacity_rect")).w > 0 and getattr(ctx, "selected_strokes", None):
        specs.append(_make_spec(
            "obj_opacity", None, state["obj_opacity_rect"], 0.0, 1.0,
            _opacity_value(ctx, "obj_opacity"), decimals=0, scale=100.0,
            suffix="%", label="Opacity", identity="obj_opacity",
        ))

    if (_rect(state.get("ref_opacity_rect")).w > 0
            and getattr(ctx, "reference_image", None) is not None):
        specs.append(_make_spec(
            "ref_opacity", None, state["ref_opacity_rect"], 0.0, 1.0,
            _opacity_value(ctx, "ref_opacity"), decimals=0, scale=100.0,
            suffix="%", label="Opacity", identity="ref_opacity",
        ))

    if _rect(state.get("alpha_rect")).w > 0 and getattr(ctx, "selected_strokes", None):
        specs.append(_make_spec(
            "alpha", None, state["alpha_rect"], 0.0, 1.0, _alpha_value(ctx),
            decimals=0, scale=100.0, suffix="%", label="Opacity", identity="alpha",
        ))

    return specs


def field_at(ctx, pos):
    """Return the visible numeric field under ``pos``, if any."""
    for spec in specifications(ctx):
        if spec["rect"].collidepoint(pos):
            return spec
    return None


def _set_edit(ctx, edit):
    ctx.drag_field_edit = edit
    state = getattr(ctx, "state", None)
    if isinstance(state, dict):
        state["drag_field_edit"] = edit


def buffer_text(spec):
    """Numeric text shown when editing starts (no unit suffix)."""
    value = float(spec.get("value", 0.0)) * float(spec.get("scale", 1.0) or 1.0)
    decimals = spec.get("decimals")
    if decimals is None:
        return f"{value:g}"
    return f"{value:.{int(decimals)}f}"


def display_text(spec):
    """Complete overlay text, including the unit suffix."""
    return buffer_text(spec) + str(spec.get("suffix", ""))


def _cancel_active_drags(ctx):
    """An edit session takes over from any scrub that the clicks started."""
    for name in ("wave_slider_drag", "wave_custom_drag", "bucket_picker_drag",
                 "picker_drag_alpha", "obj_opacity_drag", "ref_opacity_drag",
                 "fill_stop_pos_drag", "picker_drag_sv", "picker_drag_hue"):
        if hasattr(ctx, name):
            if name in ("wave_slider_drag", "wave_custom_drag", "bucket_picker_drag"):
                setattr(ctx, name, None)
            else:
                setattr(ctx, name, False)
    for name in ("slider", "width_slider", "cut_gap_slider"):
        field = getattr(ctx, name, None)
        if field is not None and hasattr(field, "dragging"):
            field.dragging = False
    state = getattr(ctx, "state", None)
    if isinstance(state, dict):
        for name in ("picker_drag_alpha", "obj_opacity_drag", "ref_opacity_drag",
                     "fill_stop_pos_drag", "picker_drag_sv", "picker_drag_hue"):
            if name in state:
                state[name] = False
        for name in ("wave_slider_drag", "wave_custom_drag", "bucket_picker_drag"):
            if name in state:
                state[name] = None


def begin(ctx, spec):
    """Open an inline editor for ``spec`` and return ``True``."""
    _cancel_active_drags(ctx)
    edit = dict(spec)
    edit["buffer"] = buffer_text(spec)
    edit["replace_on_type"] = True
    _set_edit(ctx, edit)
    return True


def cancel(ctx):
    """Close the editor without applying the buffer."""
    if getattr(ctx, "drag_field_edit", None) is None:
        return False
    _set_edit(ctx, None)
    ctx.drag_field_last_click = None
    return True


def _replace_buffer(ctx, edit, buffer):
    updated = dict(edit)
    updated["buffer"] = buffer
    _set_edit(ctx, updated)


def handle_keys(ctx, event):
    """Consume keys while an inline numeric editor is open."""
    edit = getattr(ctx, "drag_field_edit", None)
    if edit is None:
        return None
    key = getattr(event, "key", None)
    if key == pygame.K_ESCAPE:
        cancel(ctx)
    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        commit(ctx)
    elif key == pygame.K_BACKSPACE:
        _replace_buffer(ctx, edit, str(edit.get("buffer", ""))[:-1])
    elif key == pygame.K_DELETE:
        _replace_buffer(ctx, edit, "")
    else:
        ch = getattr(event, "unicode", "") or ""
        if ch.isdigit() or ch in ".-":
            buffer = "" if edit.get("replace_on_type") else str(edit.get("buffer", ""))
            if len(buffer) < 24:
                updated = dict(edit)
                updated["buffer"] = buffer + ch
                updated["replace_on_type"] = False
                _set_edit(ctx, updated)
    # Modal input mode: never let a global shortcut fire while typing.
    return 'continue'


def handle_mousedown(ctx, event):
    """Detect double-clicks and manage focus for the inline editor.

    Returns ``'continue'`` when the click was consumed by edit mode so the
    caller skips ordinary drag/button handling. The first click of a pair is
    deliberately *not* consumed, preserving single-click scrub behavior.
    """
    pos = tuple(event.pos)
    edit = getattr(ctx, "drag_field_edit", None)
    state = getattr(ctx, "state", None) or {}

    if edit is not None:
        rect = _rect(resolve_rect(state, edit))
        if rect.collidepoint(pos):
            return 'continue'
        commit(ctx)
        return None

    spec = field_at(ctx, pos)
    last = getattr(ctx, "drag_field_last_click", None)
    now = pygame.time.get_ticks()
    ctx.drag_field_last_click = None
    if spec is not None:
        double = (isinstance(last, dict)
                  and last.get("id") == spec["id"]
                  and now - int(last.get("time", 0)) <= DOUBLE_CLICK_MS
                  and math.hypot(pos[0] - float(last.get("pos", (0, 0))[0]),
                                 pos[1] - float(last.get("pos", (0, 0))[1]))
                  <= DOUBLE_CLICK_DIST)
        if double:
            begin(ctx, spec)
            return 'continue'
        ctx.drag_field_last_click = {"id": spec["id"], "time": now, "pos": pos}
    return None


def resolve_rect(state, edit):
    """Re-read a field's rect from live state so scrolling cannot strand it."""
    if not isinstance(state, dict):
        return _rect(edit.get("rect"))
    kind = edit.get("kind")
    if kind == "wave":
        entry = (state.get("wave_slider_rects") or {}).get(edit.get("key"))
        if isinstance(entry, (tuple, list)) and len(entry) == 3:
            return _rect(entry[0])
    keys = {
        "points": "slider", "cut_gap": "cut_gap_slider",
        "stroke_width": "width_slider", "obj_opacity": "obj_opacity_rect",
        "ref_opacity": "ref_opacity_rect", "alpha": "alpha_rect",
    }
    key = keys.get(kind)
    if key is None:
        return _rect(edit.get("rect"))
    value = state.get(key)
    if hasattr(value, "rect"):
        return _rect(value.rect)
    return _rect(value) if value is not None else _rect(edit.get("rect"))


def _apply_stroke_width(ctx, value):
    width_slider = getattr(ctx, "width_slider", None)
    if width_slider is not None:
        width_slider.value = float(value)
    if getattr(ctx, "tool_mode", None) != "selection":
        return
    strokes = getattr(ctx, "strokes", None) or []
    selected = getattr(ctx, "selected_strokes", None) or set()
    submode = getattr(ctx, "selection_submode", None)

    comp_target = None
    if (submode == "curve" and getattr(ctx, "selected_curve", None)
            and len(selected) == 1 and ctx.selected_curve[0] in selected):
        comp_target = (ctx.selected_curve[0], ctx.selected_curve[1])

    point_target = None
    if submode == "nodes" and getattr(ctx, "selected_point", None) and len(selected) == 1:
        si = next(iter(selected))
        seg_i, pname = ctx.selected_point
        if pname in ("p0", "p3") and 0 <= si < len(strokes):
            point_target = (si, seg_i, pname)

    if submode == "transform":
        for si in sorted(selected):
            if 0 <= si < len(strokes):
                strokes[si]["stroke_width"] = float(value)
    elif comp_target is not None:
        si, ci = comp_target
        if 0 <= si < len(strokes):
            comps_fn = getattr(ctx, "_stroke_components", _default_stroke_components)
            comps = comps_fn(strokes[si])
            if 0 <= ci < len(comps):
                comps[ci]["stroke_width"] = float(value)
                strokes[si]["components"] = comps
    elif point_target is not None:
        si, seg_i, pname = point_target
        setter = getattr(ctx, "set_point_width", None)
        if callable(setter):
            setter(strokes[si], seg_i, pname, float(value))


def _apply_alpha(ctx, value):
    state = getattr(ctx, "state", None) or {}
    strokes = getattr(ctx, "strokes", None) or []
    selected = sorted(int(i) for i in (getattr(ctx, "selected_strokes", None) or set()))
    target = state.get("color_target", getattr(ctx, "color_target", "stroke"))
    color_alpha_fn = getattr(ctx, "color_alpha", _default_color_alpha)
    set_alpha_fn = getattr(ctx, "set_color_alpha", _default_set_color_alpha)
    stroke_comps = getattr(ctx, "_stroke_components", _default_stroke_components)
    curve_style = None
    if (getattr(ctx, "selection_submode", None) == "curve"
            and getattr(ctx, "selected_curve", None)
            and len(selected) == 1 and selected[0] in selected):
        si, comp_i = ctx.selected_curve
        if 0 <= si < len(strokes):
            comps = stroke_comps(strokes[si])
            if 0 <= comp_i < len(comps):
                fn = getattr(ctx, "_effective_component_style", None)
                if callable(fn):
                    curve_style = (si, comp_i, comps, fn(strokes[si], comp_i)[0])
    if curve_style is not None:
        si, comp_i, comps, current = curve_style
        color_rgb_fn = getattr(ctx, "color_rgb", None)
        rgb = color_rgb_fn(current, (0.1, 0.1, 0.15)) if callable(color_rgb_fn) else (0.1, 0.1, 0.15)
        comps[comp_i]["stroke_color"] = (rgb[0], rgb[1], rgb[2], value)
        strokes[si]["components"] = comps
        return
    gradient_fn = getattr(ctx, "get_fill_gradient", None)
    stop_get = getattr(ctx, "get_gradient_stop_color", _default_get_gradient_stop_color)
    stop_set = getattr(ctx, "set_gradient_stop_color", _default_set_gradient_stop_color)
    stop_i = int(state.get("fill_gradient_stop", 0) or 0)
    for si in selected:
        if not (0 <= si < len(strokes)):
            continue
        if target == "stroke":
            strokes[si]["stroke_color"] = set_alpha_fn(
                strokes[si].get("stroke_color", (0.1, 0.1, 0.15, 1.0)), value)
            continue
        fg = gradient_fn(strokes[si]) if callable(gradient_fn) else None
        if fg is not None:
            cstop = stop_get(fg, stop_i)
            strokes[si]["fill_gradient"] = stop_set(
                fg, stop_i, (cstop[0], cstop[1], cstop[2], value))
        elif strokes[si].get("fill_color") is not None:
            strokes[si]["fill_color"] = set_alpha_fn(strokes[si]["fill_color"], value)


def _apply(ctx, edit, value):
    kind = edit.get("kind")
    state = getattr(ctx, "state", None) or {}
    if kind == "points":
        points = int(round(value))
        ctx.max_points_per_curve = points
        slider = getattr(ctx, "slider", None)
        if slider is not None:
            slider.value = points
    elif kind == "cut_gap":
        gap = int(round(value))
        ctx.cut_gap = gap
        state["cut_gap"] = gap
        slider = getattr(ctx, "cut_gap_slider", None)
        if slider is not None:
            slider.value = gap
    elif kind == "stroke_width":
        _apply_stroke_width(ctx, value)
    elif kind == "wave":
        comp = _selected_component(ctx)
        if comp is not None:
            si, comp_i, comps = comp
            comps[comp_i] = dict(comps[comp_i])
            wi = int(state.get("wave_active_index", 0) or 0)
            getter = getattr(ctx, "_get_distortion_style", _default_get_distortion_style)
            setter = getattr(ctx, "_set_distortion_style", None)
            wave = getter(comps[comp_i], wi)
            wave[edit["key"]] = value
            if callable(setter):
                setter(comps[comp_i], wave, wi)
            strokes = getattr(ctx, "strokes", None) or []
            strokes[si]["components"] = comps
    elif kind == "obj_opacity":
        setter = getattr(ctx, "set_appearance", _default_set_appearance)
        strokes = getattr(ctx, "strokes", None) or []
        for si in sorted(int(i) for i in (getattr(ctx, "selected_strokes", None) or set())):
            if 0 <= si < len(strokes):
                strokes[si] = setter(strokes[si], opacity=value)
    elif kind == "ref_opacity":
        ref = getattr(ctx, "reference_image", None)
        if ref is not None:
            ref["opacity"] = value
    elif kind == "alpha":
        _apply_alpha(ctx, value)


def commit(ctx):
    """Parse, clamp and apply the typed value; close the editor."""
    edit = getattr(ctx, "drag_field_edit", None)
    if edit is None:
        return False
    _set_edit(ctx, None)
    ctx.drag_field_last_click = None
    buffer = str(edit.get("buffer", "")).strip()
    if buffer in ("", "-", ".", "-."):
        return False
    try:
        value = float(buffer)
    except (TypeError, ValueError):
        return False
    value /= float(edit.get("scale", 1.0) or 1.0)
    lo, hi = float(edit.get("lo", 0.0)), float(edit.get("hi", 1.0))
    value = _clamp(ctx, value, lo, hi)
    step = edit.get("step")
    if step:
        value = round(value / float(step)) * float(step)
        value = _clamp(ctx, value, lo, hi)
    _apply(ctx, edit, value)
    return True
