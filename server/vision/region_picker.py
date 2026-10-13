"""Real-I/O wrapper around `RegionSelector` for the Adjustable Tracking
Region setup flow (docs/specs/0002-adjustable-tracking-region.md, ticket 3):
`--adjust-tracking-region` pops this up before the normal server starts,
showing the live camera feed with a draggable rectangle overlay. Confirming
(Enter/Space) or closing the window without confirming resolves to a
`Rect | None` (`None` means "use the full camera frame" -- the pre-this-
feature default), which `main.py` applies to the `OpticalColorTracker` via
`set_search_region` before continuing into the normal run, all within the
same process/invocation (no persistence, no second command).

`draw_region_overlay` is pure (just pixel drawing) and fully unit-tested,
same as `vision/debug_preview.py`'s `draw_debug_overlay`. `pick_tracking_
region`'s interactive loop (`cv2.namedWindow`/`imshow`/`waitKey`/
`setMouseCallback`) is real OpenCV GUI I/O and, same as that module's
`DebugPreviewTracker`, is not unit tested -- verified manually.
"""
import cv2
import numpy as np

from vision.region_selector import Point, Rect, RegionSelector

DEFAULT_WINDOW_NAME = "SPIDOL - Adjust Tracking Region"
OVERLAY_COLOR = (0, 255, 255)  # BGR yellow -- distinct from debug_preview's green/red
OVERLAY_THICKNESS = 2

# cv2.waitKey returns the raw key code (platform-dependent for non-ASCII
# keys, but Enter/Space/Esc are stable across platforms); masked to the low
# byte by the caller before comparing, same as any other cv2.waitKey usage.
_CONFIRM_KEYS = {13, 10, 32}  # Enter (CR and/or LF depending on platform), Space
_DISCARD_KEY = 27  # Esc


def draw_region_overlay(frame: np.ndarray, rect: Rect | None) -> np.ndarray:
    """Returns a copy of `frame` with `rect` drawn as a rectangle, or an
    unmodified copy if `rect` is `None` (nothing dragged yet) -- never
    mutates the original, same convention as `draw_debug_overlay`.
    """
    annotated = frame.copy()
    if rect is not None:
        cv2.rectangle(
            annotated,
            (rect.x, rect.y),
            (rect.x + rect.width, rect.y + rect.height),
            OVERLAY_COLOR,
            OVERLAY_THICKNESS,
        )
    return annotated


def pick_tracking_region(capture_frame, window_name: str = DEFAULT_WINDOW_NAME) -> Rect | None:
    """Opens a live preview window and lets the operator drag out a
    rectangle; returns the resolved selection once they press Enter/Space
    (which always ends the setup step -- `RegionSelector.confirm()` is a
    no-op for a never-dragged or degenerate selection, so confirming
    without touching anything correctly resolves to `None` here too, per
    the "confirm without touching anything -> full camera frame" story).
    Esc discards the current drag so the operator can redraw instead of
    exiting. Closing the window via the OS controls (not a keypress) also
    resolves to `None`.

    `capture_frame` is a zero-arg callable returning the next frame (e.g.
    `BaseImageSource.capture_frame`) -- injected so the real camera is
    never opened twice; `main.py` passes the same `image_source` it
    already constructed for the telemetry loop.
    """
    selector = RegionSelector()
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
            frame = capture_frame()
            cv2.imshow(window_name, draw_region_overlay(frame, selector.provisional))

            key = cv2.waitKey(1) & 0xFF
            if key in _CONFIRM_KEYS:
                selector.confirm()
                return selector.confirmed
            if key == _DISCARD_KEY:
                selector.discard()

            # Closed via the OS window-close control, not a keypress.
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                return None
    finally:
        cv2.destroyWindow(window_name)
