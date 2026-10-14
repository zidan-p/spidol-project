"""Position-tracker drivers.

v1 ships `SystemMouseFallbackTracker` and `OpticalColorTracker`, both
implementing the same `BasePositionTracker` ABC (Open-Closed Principle: the
telemetry loop depends only on the ABC, never on either concrete class).
"""
from typing import Callable

import cv2
import numpy as np

from hal.interfaces import BasePositionTracker
from vision.region_selector import Quad


def _default_position_source() -> tuple[int, int]:
    # Imported lazily so environments without a display (CI, headless
    # servers) can still import this module without pynput touching X11/Win32.
    from pynput.mouse import Controller

    controller = Controller()
    return controller.position


def detect_screen_size() -> tuple[float, float]:
    """Real display resolution in pixels -- shared by `SystemMouseFallback
    Tracker` (normalizing the real cursor's position) and
    `hal.os_cursor_controller.OsCursorController` (mapping a normalized
    tracked position back out to real screen pixels), so both agree on the
    same screen regardless of which one actually detects it.
    """
    from pynput.mouse import Controller as _Unused  # noqa: F401 -- ensures pynput import errors surface early
    import ctypes

    try:
        user32 = ctypes.windll.user32
        return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    except AttributeError:
        # Non-Windows fallback: a reasonable default; real multi-platform
        # screen-size detection is out of scope for this tracer bullet.
        return (1920, 1080)


class SystemMouseFallbackTracker(BasePositionTracker):
    """Reports the real OS mouse cursor position, normalized to [0, 1].

    Used as the input source for ticket 01's mouse-driven tracer bullet, and
    as a no-camera-required fallback/dev mode going forward.
    """

    def __init__(
        self,
        position_source: Callable[[], tuple[float, float]] | None = None,
        screen_size: tuple[float, float] | None = None,
    ):
        self._position_source = position_source or _default_position_source
        self._screen_size = screen_size or detect_screen_size()

    def get_position(self, frame=None) -> tuple[float, float, bool]:
        raw_x, raw_y = self._position_source()
        width, height = self._screen_size

        x = _clamp(raw_x / width, 0.0, 1.0)
        y = _clamp(raw_y / height, 0.0, 1.0)

        return x, y, True


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class OpticalColorTracker(BasePositionTracker):
    """Locates the Pen Tip in a camera frame by HSV color/blob detection.

    GLOSSARY: `OpticalColorTracker` is the only position-tracking driver
    shipping in v1 (`ArucoMarkerTracker` is out of scope). It thresholds the
    frame to a configurable HSV range, finds the largest matching contour,
    and reports its centroid as the Pen Tip position. The default range is
    tuned for the actual physical Pen Tip (a teal/cyan-blue 3D-printed
    marker) -- measured directly from a real photo of it (hue ~90-120,
    median ~100; this reads as "blue" to the eye but sits closer to cyan
    than pure blue's hue ~120 in OpenCV's 0-179 scale), not a generic "blue"
    guess. Pass `hsv_lower`/`hsv_upper` for a different Pen Tip color.

    `hsv_lower2`/`hsv_upper2` (optional, unused by default) let a caller
    supply a *second* HSV band, OR'd in alongside the first -- needed for a
    color like red, which sits at the very ends of OpenCV's hue space and
    wraps around (e.g. ~170-179 back to 0-10), so a single contiguous
    `cv2.inRange` band can't express it the way one band works fine for
    blue/green/the current default. Never auto-applied; only takes effect
    if explicitly passed, alongside a matching custom `hsv_lower`/`hsv_upper`.

    Coordinates returned are normalized to the camera frame's own [0, 1]
    space -- mapping that into canvas space for an angled camera is the
    homography module's job (`vision/homography.py`), not this class's.

    `search_region` (docs/specs/0002-adjustable-tracking-region.md) is an
    arbitrary quadrilateral (not just an axis-aligned box) restricting the
    color/contour search to inside it, so a stray blob elsewhere in the
    room is never detected at all -- and so the tracked area can match a
    trapezoidal board shape when the camera is off to one side rather than
    straight-on. Unset (the default), the entire frame is searched,
    unchanged from before this feature existed. Independent of, and
    untouched by, `vision/homography.py`'s Calibration Hotkey: restricting
    *where this class searches* and dewarping *detected coordinates* are
    separate, non-interacting concerns that happen to both involve a
    camera-frame overlay.
    """

    # Measured from a real photo of the physical Pen Tip (teal/cyan-blue 3D-
    # printed marker): sampling its body gave hue 90-115 (5th-95th
    # percentile 95-100), saturation 50-225 (5th-95th 122-206), value
    # 55-109 (5th-95th 60-91) under dim indoor lighting. Widened a bit
    # beyond that sample for lighting variation across sessions, while
    # staying tight enough to exclude background: validated against the
    # full photo (not just the sampled patch) to confirm one single clean
    # contour, no stray noise elsewhere in frame.
    DEFAULT_HSV_LOWER = (90, 80, 40)
    DEFAULT_HSV_UPPER = (120, 255, 255)

    def __init__(
        self,
        hsv_lower: tuple[int, int, int] | None = None,
        hsv_upper: tuple[int, int, int] | None = None,
        hsv_lower2: tuple[int, int, int] | None = None,
        hsv_upper2: tuple[int, int, int] | None = None,
        min_contour_area: float = 20.0,
        search_region: Quad | None = None,
    ):
        self._hsv_lower = np.array(hsv_lower or self.DEFAULT_HSV_LOWER, dtype=np.uint8)
        self._hsv_upper = np.array(hsv_upper or self.DEFAULT_HSV_UPPER, dtype=np.uint8)

        if hsv_lower2 is not None and hsv_upper2 is not None:
            self._hsv_lower2 = np.array(hsv_lower2, dtype=np.uint8)
            self._hsv_upper2 = np.array(hsv_upper2, dtype=np.uint8)
        else:
            self._hsv_lower2 = None
            self._hsv_upper2 = None

        self._min_contour_area = min_contour_area
        self._search_region = search_region
        self._region_mask: np.ndarray | None = None
        self._region_mask_shape: tuple[int, int] | None = None

    def set_search_region(self, region: Quad | None) -> None:
        """Applied by `main.py`'s `--adjust-tracking-region` setup flow
        once the operator confirms a selection (or leaves it `None` to
        search the full frame, the pre-this-feature default).
        """
        self._search_region = region
        self._region_mask = None
        self._region_mask_shape = None

    @property
    def search_region(self) -> Quad | None:
        return self._search_region

    def _get_region_mask(self, height: int, width: int) -> np.ndarray:
        # Built once per (region, frame shape) and cached -- cv2.fillPoly
        # isn't free, and the frame shape/region rarely change tick to tick.
        if self._region_mask is not None and self._region_mask_shape == (height, width):
            return self._region_mask
        polygon = np.array([[p.x, p.y] for p in self._search_region.points], dtype=np.int32)
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(mask, [polygon], 255)
        self._region_mask = mask
        self._region_mask_shape = (height, width)
        return mask

    def get_position(self, frame: np.ndarray | None) -> tuple[float, float, bool]:
        if frame is None or frame.size == 0:
            return 0.0, 0.0, False

        height, width = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self._hsv_lower, self._hsv_upper)
        if self._hsv_lower2 is not None:
            # Red's wrap-around second band (see class docstring) -- OR'd
            # into the first band's mask, not replacing it.
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, self._hsv_lower2, self._hsv_upper2))

        if self._search_region is not None:
            # A polygon mask (rather than cropping to an enclosing
            # rectangle) so an arbitrary quadrilateral is respected exactly,
            # and the centroid below is already in full-frame pixel space --
            # no offset math needed, unlike a crop-based approach.
            mask = cv2.bitwise_and(mask, self._get_region_mask(height, width))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return 0.0, 0.0, False

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < self._min_contour_area:
            return 0.0, 0.0, False

        moments = cv2.moments(largest)
        if moments["m00"] == 0:
            return 0.0, 0.0, False

        centroid_x = moments["m10"] / moments["m00"]
        centroid_y = moments["m01"] / moments["m00"]

        x = _clamp(centroid_x / width, 0.0, 1.0)
        y = _clamp(centroid_y / height, 0.0, 1.0)

        return x, y, True
