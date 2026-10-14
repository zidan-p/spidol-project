"""Real-I/O wrapper around `RegionSelector` for the Adjustable Tracking
Region setup flow (docs/specs/0002-adjustable-tracking-region.md):
`--adjust-tracking-region` pops this up before the normal server starts,
showing the live camera feed with a draggable 4-corner quadrilateral
overlay. Confirming (Enter/Space) or closing the window without confirming
resolves to a `Quad | None` (`None` means "use the full camera frame" --
the pre-this-feature default), which `main.py` applies to the
`OpticalColorTracker` via `set_search_region` before continuing into the
normal run, all within the same process/invocation (no persistence, no
second command).

`draw_region_overlay` is pure (just pixel drawing) and fully unit-tested,
same as `vision/debug_preview.py`'s `draw_debug_overlay`. `pick_tracking_
region`'s interactive loop (`cv2.namedWindow`/`imshow`/`waitKey`/
`setMouseCallback`) is real OpenCV GUI I/O and, same as that module's
`DebugPreviewTracker`, is not unit tested -- verified manually.
"""
import cv2
import numpy as np

from vision.region_selector import Point, Quad, RegionSelector

DEFAULT_WINDOW_NAME = "SPIDOL - Adjust Tracking Region"
OVERLAY_COLOR = (0, 255, 255)  # BGR yellow -- distinct from debug_preview's green/red
OVERLAY_THICKNESS = 2
CORNER_HANDLE_RADIUS = 8

# cv2.waitKey returns the raw key code (platform-dependent for non-ASCII
# keys, but Enter/Space/Esc are stable across platforms); masked to the low
# byte by the caller before comparing, same as any other cv2.waitKey usage.
_CONFIRM_KEYS = {13, 10, 32}  # Enter (CR and/or LF depending on platform), Space
_DISCARD_KEY = 27  # Esc


def draw_region_overlay(frame: np.ndarray, points) -> np.ndarray:
    """Returns a copy of `frame` with the quadrilateral connecting `points`
    (closing back to the first) plus a small filled circle at each corner
    handle -- never mutates the original, same convention as
    `draw_debug_overlay`. `points` is always the selector's current four
    corners (`RegionSelector.points`), live-updating every frame while
    dragging.
    """
    annotated = frame.copy()
    pixel_points = [(p.x, p.y) for p in points]
    for i in range(len(pixel_points)):
        start = pixel_points[i]
        end = pixel_points[(i + 1) % len(pixel_points)]
        cv2.line(annotated, start, end, OVERLAY_COLOR, OVERLAY_THICKNESS)
    for point in pixel_points:
        cv2.circle(annotated, point, CORNER_HANDLE_RADIUS, OVERLAY_COLOR, thickness=-1)
    return annotated


def pick_tracking_region(capture_frame, window_name: str = DEFAULT_WINDOW_NAME) -> Quad | None:
    """Opens a live preview window with four draggable corner handles
    (initially at the frame's own corners); returns the resolved selection
    once the operator presses Enter/Space (which always ends the setup step
    -- `RegionSelector.confirm()` is a no-op for a degenerate near-zero-area
    quad, so confirming without touching anything correctly resolves to the
    full-frame quad, matching the "confirm without touching anything ->
    full camera frame" story... except it's never `None` here since the
    default quad already covers the full frame -- `None` only happens if
    the window is closed via the OS controls instead). Esc resets all four
    corners back to the full-frame default so the operator can redraw
    instead of exiting.

    `capture_frame` is a zero-arg callable returning the next frame (e.g.
    `BaseImageSource.capture_frame`) -- injected so the real camera is
    never opened twice; `main.py` passes the same `image_source` it
    already constructed for the telemetry loop. The first captured frame
    also determines the frame size the default (full-frame) quad is based
    on.
    """
    frame = capture_frame()
    height, width = frame.shape[:2]
    selector = RegionSelector(frame_size=(width, height))

    cv2.namedWindow(window_name)

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            selector.on_mouse_down(Point(x, y))
        elif event == cv2.EVENT_MOUSEMOVE:
            selector.on_mouse_move(Point(x, y))
        elif event == cv2.EVENT_LBUTTONUP:
            selector.on_mouse_up(Point(x, y))

    cv2.setMouseCallback(window_name, on_mouse)

    try:
        while True:
            cv2.imshow(window_name, draw_region_overlay(frame, selector.points))

            key = cv2.waitKey(1) & 0xFF
            if key in _CONFIRM_KEYS:
                selector.confirm()
                return selector.confirmed
            if key == _DISCARD_KEY:
                selector.discard()

            # Closed via the OS window-close control, not a keypress.
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                return None

            frame = capture_frame()
    finally:
        cv2.destroyWindow(window_name)
