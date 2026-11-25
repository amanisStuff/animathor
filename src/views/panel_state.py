"""Typed view-side panel state output (analysis §8).

The view produces one typed output object instead of writing individual rect
fields back through a ctx bag. ``PanelRects`` is the neutral shared contract;
``UiFrameOutput`` is the explicit result of composing one UI frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from panel_rects import PanelRects  # noqa: F401


@dataclass
class UiFrameOutput:
    """Explicit output of one UI frame composition."""

    rects: PanelRects = field(default_factory=PanelRects)
    width: int = 0
    height: int = 0

    @classmethod
    def from_state(cls, state: object) -> "UiFrameOutput":
        rects = PanelRects().update_from_state(state)
        width = getattr(state, "get", lambda *_: 0)("panel_width", 0) or 0
        height = getattr(state, "get", lambda *_: 0)("panel_height", 0) or 0
        return cls(rects=rects, width=int(width), height=int(height))
