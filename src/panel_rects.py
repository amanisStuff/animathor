"""Shared panel rect contract (neutral module for views and controllers).

Rect keys are mapped to the semantic panel domain that produces and consumes
them, so rect production (views) and hit handling (controllers/panel/*) share
one typed contract instead of ad-hoc string keys in a state dict.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from config import MIN_ELEMENT_SPACING


@dataclass
class PanelRects:
    """Typed cache of panel hit rects keyed by semantic rect name."""

    rects: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.rects.get(key, default)

    def set(self, key: str, rect: Any) -> None:
        self.rects[key] = rect

    def update_from_state(self, state: Any) -> "PanelRects":
        """Collect ``*_rect`` / ``*_rects`` entries from a view state mapping."""
        if isinstance(state, dict):
            for key, value in state.items():
                if key.endswith("_rect") or key.endswith("_rects"):
                    self.rects[key] = value
        return self


def rects_from_state(state: Any) -> PanelRects:
    """Build a typed rect cache from a view state dict."""
    return PanelRects().update_from_state(state)


def hit_rect(ctx: Any, name: str, default: Any = None) -> Any:
    """Resolve a panel hit rect through the shared typed rect contract."""
    state = getattr(ctx, "state", None)
    return rects_from_state(state).get(name, default)


# Semantic ownership of each panel rect key: (producer view section, domain).
RECT_DOMAINS = {
    # fill / color picker
    "tab_stroke_rect": "fill_picker", "tab_fill_rect": "fill_picker",
    "sv_rect": "fill_picker", "hue_rect": "fill_picker",
    "nofill_rect": "fill_picker", "alpha_rect": "fill_picker",
    "swatch_rects": "fill_picker",
    "picker_rects": "fill_picker", "bucket_sv_rect": "fill_picker",
    "bucket_hue_rect": "fill_picker", "bucket_swatch_rects": "fill_picker",
    # gradient stops / fill type
    "fill_type_prev_rect": "gradient_stops", "fill_type_next_rect": "gradient_stops",
    "fill_stop_rects": "gradient_stops", "fill_stop_add_rect": "gradient_stops",
    "fill_stop_remove_rect": "gradient_stops", "fill_stop_pos_rect": "gradient_stops",
    "pattern_type_rect": "gradient_stops",
    "pattern_size_minus_rect": "gradient_stops", "pattern_size_plus_rect": "gradient_stops",
    # stroke style
    "marker_start_rect": "stroke_style", "marker_end_rect": "stroke_style",
    "marker_dropdown_rect": "stroke_style", "marker_dropdown_item_rects": "stroke_style",
    "width_profile_prev_rect": "stroke_style", "width_profile_next_rect": "stroke_style",
    "cap_prev_rect": "stroke_style", "cap_next_rect": "stroke_style",
    "join_prev_rect": "stroke_style", "join_next_rect": "stroke_style",
    "dash_prev_rect": "stroke_style", "dash_next_rect": "stroke_style",
    "obj_opacity_rect": "stroke_style", "shadow_toggle_rect": "stroke_style",
    "shadow_blur_minus_rect": "stroke_style", "shadow_blur_plus_rect": "stroke_style",
    # effects (wave / displacement / repeat)
    "wave_toggle_rect": "effects_wave", "wave_add_rect": "effects_wave",
    "wave_remove_rect": "effects_wave", "wave_bake_rect": "effects_wave",
    "wave_formula_rect": "effects_wave", "wave_custom_box_rect": "effects_wave",
    "wave_row_rects": "effects_wave", "wave_slider_rects": "effects_wave",
    # tool options
    "draw_tool_pen_rect": "tool_options", "draw_tool_eraser_rect": "tool_options",
    "draw_tool_bucket_rect": "tool_options", "draw_tool_cutter_rect": "tool_options",
    "draw_shape_rects": "tool_options", "snap_toggle_rect": "tool_options",
    "trace_algo_prev_rect": "tool_options", "trace_algo_next_rect": "tool_options",
    # transform inspector
    "xform_x_rect": "transform_inspector", "xform_y_rect": "transform_inspector",
    "xform_w_rect": "transform_inspector", "xform_h_rect": "transform_inspector",
    "xform_r_rect": "transform_inspector",
    # selection actions
    "elev_front_rect": "selection_actions", "bool_union_rect": "selection_actions",
    "distribute_h_rect": "selection_actions", "align_left_rect": "selection_actions",
    "mirror_h_rect": "selection_actions", "path_close_rect": "selection_actions",
}


def domain_of(key: str) -> str | None:
    """Return the semantic domain owning a panel rect key (if known)."""
    return RECT_DOMAINS.get(key)


def publish_rect(state: dict, key: str, rect: Any) -> None:
    """Publish a rect produced by a view into state through the shared contract."""
    state[key] = rect


@dataclass(frozen=True)
class SpacingViolation:
    """One pair of published elements that breaks the 8px spacing rule."""

    key_a: str
    rect_a: Any
    key_b: str
    rect_b: Any
    gap: int
    horizontal: int
    vertical: int
    axis: str


def _is_rect(value: Any) -> bool:
    """Duck-type check so this module stays independent of pygame."""
    return all(hasattr(value, attr) for attr in ("left", "right", "top", "bottom"))


def _visible(value: Any) -> bool:
    return getattr(value, "w", getattr(value, "width", 0)) > 0 and getattr(
        value, "h", getattr(value, "height", 0)) > 0


def visible_rects_from_state(state: Any) -> dict[str, Any]:
    """Flatten visible published ``*_rect`` / ``*_rects`` values from a view state.

    Collection entries are named ``key[index]`` (or ``key[key]`` for dicts).
    Tuple-wrapped rects, such as ``wave_slider_rects`` and ``wave_row_rects``,
    are named ``key[index][position]``.
    """
    rects: dict[str, Any] = {}
    if not isinstance(state, Mapping):
        return rects
    for key, value in state.items():
        if not (key.endswith("_rect") or key.endswith("_rects")):
            continue
        if _is_rect(value):
            if _visible(value):
                rects[key] = value
            continue
        if isinstance(value, Mapping):
            items = value.items()
        elif isinstance(value, (list, tuple)):
            items = enumerate(value)
        else:
            continue
        for index, item in items:
            name = f"{key}[{index}]"
            if _is_rect(item):
                if _visible(item):
                    rects[name] = item
            elif isinstance(item, (list, tuple)):
                for inner_index, inner in enumerate(item):
                    inner_name = f"{name}[{inner_index}]"
                    if _is_rect(inner) and _visible(inner):
                        rects[inner_name] = inner
    return rects


def _contains(outer: Any, inner: Any) -> bool:
    return (outer.left <= inner.left and outer.right >= inner.right
            and outer.top <= inner.top and outer.bottom >= inner.bottom)


def spacing_violations(rects: Mapping[str, Any], minimum: int | None = None) -> list[SpacingViolation]:
    """Return element pairs whose published rects are closer than ``minimum``.

    Contained children are treated as part of their composite parent and are
    skipped. Overlapping or touching siblings are reported with ``gap = 0``.
    """
    minimum = MIN_ELEMENT_SPACING if minimum is None else minimum
    items = [(name, rect) for name, rect in rects.items()
             if _is_rect(rect) and _visible(rect)]
    violations: list[SpacingViolation] = []
    for i, (name_a, a) in enumerate(items):
        for name_b, b in items[i + 1:]:
            if _contains(a, b) or _contains(b, a):
                continue
            h = max(0, b.left - a.right, a.left - b.right)
            v = max(0, b.top - a.bottom, a.top - b.bottom)
            overlap_x = min(a.right, b.right) - max(a.left, b.left)
            overlap_y = min(a.bottom, b.bottom) - max(a.top, b.top)
            overlapping = overlap_x > 0 and overlap_y > 0
            gap = 0 if overlapping else max(h, v)
            if gap >= minimum:
                continue
            if overlapping:
                axis = "overlap"
            elif h > v:
                axis = "horizontal"
            elif v > h:
                axis = "vertical"
            else:
                axis = "touching"
            violations.append(SpacingViolation(
                key_a=name_a, rect_a=a, key_b=name_b, rect_b=b,
                gap=gap, horizontal=h, vertical=v, axis=axis,
            ))
    return sorted(violations, key=lambda item: (item.gap, item.key_a, item.key_b))


def panel_spacing_violations(state: Any, minimum: int | None = None) -> list[SpacingViolation]:
    """Validate every visible published rect in a rendered panel state."""
    return spacing_violations(visible_rects_from_state(state), minimum)
