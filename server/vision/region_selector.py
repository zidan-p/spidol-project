"""Pure, cv2-free state machine behind the Adjustable Tracking Region setup
flow (docs/specs/0002-adjustable-tracking-region.md, `--adjust-tracking-
region`): tracks a provisional rectangle through raw mouse-down/move/up
events, and resolves it into a final selection via `confirm()`/`discard()`.

Deliberately has no `cv2` dependency -- the real OpenCV window (mouse
callback wiring, live frame drawing, translating `cv2.waitKey()` codes into
calls to `confirm()`/`discard()`) is a separate, untested real-I/O wrapper
around this class (ticket 3), mirroring the existing `vision/debug_preview.py`
(injectable `show_frame`) / `hal/providers.py`'s `BleTouchProvider`
(injectable `client_factory`) pattern of a tested pure core plus an untested
thin real-I/O shell.

Named `Rect`, not `Region`, to avoid colliding with the unrelated
`ai/stroke_region.py`'s `Region` (the AI Trigger Region -- a bounding box of
drawn strokes in normalized canvas coordinates, built for an entirely
different purpose: cropping what gets sent to the vision model, not
restricting where `OpticalColorTracker` searches for the Pen Tip).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """A pixel-space rectangle in the camera frame: `(x, y)` is the
    top-left corner, always the min corner of whatever two points the
    operator actually dragged between (see `_rect_from_corners`).
    """

    x: int
    y: int
    width: int
    height: int


def _rect_from_corners(a: tuple[int, int], b: tuple[int, int]) -> Rect:
    x = min(a[0], b[0])
    y = min(a[1], b[1])
    width = abs(a[0] - b[0])
    height = abs(a[1] - b[1])
    return Rect(x=x, y=y, width=width, height=height)


class RegionSelector:
    """Drives the provisional/confirmed rectangle through a drag gesture.

    `on_mouse_down`/`on_mouse_move`/`on_mouse_up` track a rectangle being
    dragged out (normalized to a non-negative width/height regardless of
    drag direction); `confirm()` locks the current provisional rectangle in
    as `confirmed`, and `discard()` clears both so the operator can redraw.
    """

    def __init__(self) -> None:
        self._dragging = False
        self._drag_start: tuple[int, int] | None = None
        self._provisional: Rect | None = None
        self._confirmed: Rect | None = None

    @property
    def provisional(self) -> Rect | None:
        return self._provisional

    @property
    def confirmed(self) -> Rect | None:
        return self._confirmed

    def on_mouse_down(self, x: int, y: int) -> None:
        # Always starts a fresh drag, regardless of any prior
        # provisional/confirmed state -- in the real flow a new drag only
        # ever happens after a `discard()` (ticket 3's wrapper exits its
        # loop immediately on `confirm()`), but this stays well-defined
        # even if called again anyway.
        self._dragging = True
        self._drag_start = (x, y)
        self._provisional = Rect(x=x, y=y, width=0, height=0)

    def on_mouse_move(self, x: int, y: int) -> None:
        if not self._dragging or self._drag_start is None:
            return
        self._provisional = _rect_from_corners(self._drag_start, (x, y))

    def on_mouse_up(self, x: int, y: int) -> None:
        if not self._dragging:
            return
        self._dragging = False
        if self._drag_start is not None:
            self._provisional = _rect_from_corners(self._drag_start, (x, y))

    def confirm(self) -> None:
        """Locks in the current provisional rectangle, if any. A no-op --
        leaving `confirmed` as `None` -- when nothing was ever dragged, or
        the drag was a degenerate zero-area click: both cases fall back to
        the full-frame default in ticket 3's real-I/O wrapper, matching the
        "confirm without touching anything" story.
        """
        if self._provisional is not None and self._provisional.width > 0 and self._provisional.height > 0:
            self._confirmed = self._provisional

    def discard(self) -> None:
        """Clears the provisional rectangle (and any prior confirmation)
        so the operator can redraw from scratch.
        """
        self._provisional = None
        self._confirmed = None
