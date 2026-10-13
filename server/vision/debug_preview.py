"""Camera debug preview (dev-only aid, `main.py --debug-camera`): shows the
live camera feed with the tracker's current detection burned onto it (a
crosshair at the detected position, or a "NO TARGET" label when nothing's
found) in a local OpenCV window on the machine running the server -- the
fastest way to confirm `OpticalColorTracker` is actually seeing the Pen Tip
before trusting the drawing-based proof (ink following the object on the
whiteboard canvas).

`draw_debug_overlay` is pure (just pixel drawing, fully unit-tested).
`DebugPreviewTracker` wraps any `BasePositionTracker` and calls
`show_frame` (defaulting to a thin `cv2.imshow`/`cv2.waitKey` wrapper) with
the annotated frame on every `get_position` call -- `show_frame` is
injectable so tests never need a real display/GUI backend, mirroring
`CameraImageSource`'s `capture_factory` / `BleTouchProvider`'s
`client_factory` seams.
"""
import cv2
import numpy as np

DETECTED_COLOR = (0, 255, 0)  # BGR green
NOT_DETECTED_COLOR = (0, 0, 255)  # BGR red
MARKER_RADIUS = 12
DEFAULT_WINDOW_NAME = "SPIDOL Camera Debug"


def draw_debug_overlay(frame: np.ndarray, x: float, y: float, is_detected: bool) -> np.ndarray:
    """Returns a copy of `frame` with the detection state drawn on it --
    never mutates the original, since the same frame may still be used
    elsewhere in the telemetry loop (homography, tracking-loss bridging).
    """
    annotated = frame.copy()
    height, width = annotated.shape[:2]

    if is_detected:
        center = (int(x * width), int(y * height))
        cv2.drawMarker(
            annotated, center, DETECTED_COLOR, markerType=cv2.MARKER_CROSS, markerSize=MARKER_RADIUS * 2, thickness=2
        )
        cv2.circle(annotated, center, MARKER_RADIUS, DETECTED_COLOR, 2)
        label, color = "DETECTED", DETECTED_COLOR
    else:
        label, color = "NO TARGET", NOT_DETECTED_COLOR

    cv2.putText(annotated, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return annotated


def show_frame(window_name: str, frame: np.ndarray) -> None:
    """Real GUI side effect -- not unit-tested (no display in CI), kept
    minimal on purpose. `waitKey(1)` is required for OpenCV's HighGUI event
    loop to actually paint the window and process input; the 1ms wait is
    negligible against the telemetry loop's ~16ms/frame budget.
    """
    cv2.imshow(window_name, frame)
    cv2.waitKey(1)


class DebugPreviewTracker:
    """Wraps any `BasePositionTracker`, showing a live annotated preview of
    its detection on every call without changing its return value --
    transparent to callers (`main.py`'s telemetry loop doesn't need to know
    whether debug preview is enabled).
    """

    def __init__(self, inner, show_frame=show_frame, window_name: str = DEFAULT_WINDOW_NAME):
        self._inner = inner
        self._show_frame = show_frame
        self._window_name = window_name

    @property
    def inner(self):
        """The wrapped tracker -- exposed so tests (and any other caller
        that needs to reach through the wrapper) can introspect the real
        tracker underneath, e.g. asserting an Adjustable Tracking Region
        (docs/specs/0002-...) was applied to it. `main.py` itself doesn't
        need this: it applies that region to the raw `OpticalColorTracker`
        *before* any `--debug-camera` wrapping happens.
        """
        return self._inner

    def get_position(self, frame: np.ndarray | None) -> tuple[float, float, bool]:
        x, y, is_detected = self._inner.get_position(frame)
        if frame is not None:
            annotated = draw_debug_overlay(frame, x, y, is_detected)
            self._show_frame(self._window_name, annotated)
        return x, y, is_detected
