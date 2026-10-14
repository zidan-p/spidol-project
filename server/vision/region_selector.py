"""Pure, cv2-free state machine behind the Adjustable Tracking Region setup
flow (docs/specs/0002-adjustable-tracking-region.md, `--adjust-tracking-
region`): tracks four independently-draggable corner handles, and resolves
them into a final quadrilateral selection via `confirm()`/`discard()`.

A general quadrilateral (not just an axis-aligned rectangle) is needed so
the tracked area can match the whiteboard's actual trapezoidal shape in
frame when the camera is off to one side rather than straight-on --
otherwise a rectangle forces a choice between missing part of the board or
including background outside it. This only restricts *where*
`OpticalColorTracker` searches for color; it does not perspective-correct
the *reported* coordinates (that's `vision/homography.py`'s separate,
still-unfinished job).

Deliberately has no `cv2` dependency -- the real OpenCV window (mouse
callback wiring, live frame drawing, translating `cv2.waitKey()` codes into
calls to `confirm()`/`discard()`) is a separate, untested real-I/O wrapper
around this class (`vision/region_picker.py`), mirroring the existing
`vision/debug_preview.py` (injectable `show_frame`) / `hal/providers.py`'s
`BleTouchProvider` (injectable `client_factory`) pattern of a tested pure
core plus an untested thin real-I/O shell.

Named `Quad`, not `Region`, to avoid colliding with the unrelated
`ai/stroke_region.py`'s `Region` (the AI Trigger Region -- a bounding box of
drawn strokes in normalized canvas coordinates, built for an entirely
different purpose: cropping what gets sent to the vision model, not
restricting where `OpticalColorTracker` searches for the Pen Tip).
"""
from dataclasses import dataclass

# How close (pixels) a mouse-down must land to an existing corner handle to
# grab it for dragging -- generous, since precisely hitting a single pixel
# isn't the point; a click further away from every handle than this does
# nothing, rather than always dragging whichever corner happens to be
# nearest regardless of distance.
PICK_RADIUS_PX = 40

# A degenerate (near-zero-area) quad -- e.g. corners dragged on top of each
# other -- is never confirmable; same spirit as the old Rect's `has_area`.
MIN_AREA_PX2 = 100


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Quad:
    """Four corner points (pixel-space), in the order they were placed/
    dragged -- not necessarily axis-aligned, so it can bound a trapezoidal
    board shape as seen from an angled camera.
    """

    points: tuple[Point, Point, Point, Point]

    @property
    def has_area(self) -> bool:
        return _polygon_area(self.points) >= MIN_AREA_PX2


def _distance(a: Point, b: Point) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _polygon_area(points) -> float:
    # Shoelace formula -- works for any simple polygon, not just rectangles.
    area = 0.0
    n = len(points)
    for i in range(n):
        a = points[i]
        b = points[(i + 1) % n]
        area += a.x * b.y - b.x * a.y
    return abs(area) / 2.0


def _default_quad(frame_width: int, frame_height: int) -> tuple[Point, Point, Point, Point]:
    # The full frame's own four corners -- confirming without dragging
    # anything behaves like today's full-frame search (no regression).
    return (
        Point(0, 0),
        Point(frame_width - 1, 0),
        Point(frame_width - 1, frame_height - 1),
        Point(0, frame_height - 1),
    )


class RegionSelector:
    """Drives four corner handles (initially at the full frame's own
    corners) through independent drag gestures.

    `on_mouse_down` grabs whichever handle is within `PICK_RADIUS_PX` of the
    press (or nothing, if none are close enough); `on_mouse_move` follows
    the cursor with whichever handle is currently grabbed; `on_mouse_up`
    releases it. `confirm()` locks in the current four corners as
    `confirmed` (a no-op for a degenerate near-zero-area quad -- same
    fallback-to-full-frame story as before). `discard()` resets all four
    corners back to the full-frame default so the operator can start over,
    without touching an already-`confirm()`ed selection.
    """

    def __init__(self, frame_size: tuple[int, int]) -> None:
        frame_width, frame_height = frame_size
        self._default_points = _default_quad(frame_width, frame_height)
        self._points: list[Point] = list(self._default_points)
        self._dragging_index: int | None = None
        self._confirmed: Quad | None = None

    @property
    def points(self) -> tuple[Point, Point, Point, Point]:
        """The four corners' current (live) positions, in order -- what the
        real-I/O wrapper draws every frame, confirmed or not.
        """
        return tuple(self._points)

    @property
    def confirmed(self) -> Quad | None:
        return self._confirmed

    def on_mouse_down(self, point: Point) -> None:
        nearest_index = min(range(4), key=lambda i: _distance(self._points[i], point))
        if _distance(self._points[nearest_index], point) <= PICK_RADIUS_PX:
            self._dragging_index = nearest_index
            self._points[nearest_index] = point

    def on_mouse_move(self, point: Point) -> None:
        if self._dragging_index is not None:
            self._points[self._dragging_index] = point

    def on_mouse_up(self, point: Point) -> None:
        if self._dragging_index is not None:
            self._points[self._dragging_index] = point
            self._dragging_index = None

    def confirm(self) -> None:
        candidate = Quad(points=tuple(self._points))
        if candidate.has_area:
            self._confirmed = candidate

    def discard(self) -> None:
        """Resets all four corners back to the full-frame default so the
        operator can start over. Leaves an already-confirmed selection
        untouched -- this is about abandoning in-progress edits, not
        un-confirming a prior `confirm()`.
        """
        self._points = list(self._default_points)
        self._dragging_index = None
