"""Base drag session contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DragSession:
    """Base class for an active pointer drag interaction."""

    name: str = "drag"

    def begin(self, ctx, event) -> None:
        """Initialize drag state on mouse down."""

    def move(self, ctx, event) -> bool:
        """Handle mouse motion. Return True if consumed."""
        return False

    def end(self, ctx, event) -> bool:
        """Handle mouse up. Return True if consumed/committed."""
        return False

    def cancel(self, ctx) -> None:
        """Cancel drag (e.g., Escape)."""


@dataclass
class DragManager:
    """Tracks the currently active drag session on ctx."""

    active: DragSession | None = None

    def begin(self, session: DragSession, ctx, event) -> None:
        self.active = session
        session.begin(ctx, event)

    def move(self, ctx, event) -> bool:
        if self.active is None:
            return False
        return bool(self.active.move(ctx, event))

    def end(self, ctx, event) -> bool:
        if self.active is None:
            return False
        handled = bool(self.active.end(ctx, event))
        self.active = None
        return handled

    def cancel(self, ctx) -> None:
        if self.active is not None:
            self.active.cancel(ctx)
            self.active = None

    def modal_motion(self, session: DragSession, ctx, event) -> bool:
        """Handle a modal/hover drag session that may begin on motion.

        Used for interactions like bezier pen preview where motion can claim
        the active drag when the session reports it is applicable.
        """
        if self.active is not None and self.active.name != session.name:
            return False
        active_session = self.active if (self.active is not None and self.active.name == session.name) else session
        consumed = bool(active_session.move(ctx, event))
        if consumed:
            if self.active is None:
                self.begin(active_session, ctx, event)
            return True
        if self.active is not None and self.active.name == session.name:
            self.end(ctx, event)
        return False
