"""Tests for `OpticalColorTracker` (GLOSSARY: Pen Tip, OpticalColorTracker).

Exercises only the public `BasePositionTracker.get_position` seam, feeding
synthetic numpy BGR frames with a known colored blob at known pixel
coordinates -- no real camera/RemoteCam hardware required.
"""
import cv2
import numpy as np
import pytest

from hal.interfaces import BasePositionTracker
from hal.trackers import OpticalColorTracker
from vision.region_selector import Point, Quad

FRAME_WIDTH = 640
FRAME_HEIGHT = 480


def rect_quad(x, y, width, height) -> Quad:
    """An axis-aligned rectangle expressed as a Quad, for tests that don't
    care about non-rectangular shapes specifically."""
    return Quad(
        points=(
            Point(x, y),
            Point(x + width, y),
            Point(x + width, y + height),
            Point(x, y + height),
        )
    )

# hue=100, sat=200, val=120 in BGR -- comfortably inside the tracker's
# default teal/cyan-blue Pen Tip color range (measured from a real photo
# of the physical marker, see DEFAULT_HSV_LOWER/UPPER's comment).
PEN_TIP_BGR = (120, 89, 26)


def make_frame_with_blob(center_xy, radius=15, color=PEN_TIP_BGR):
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.circle(frame, center_xy, radius, color, thickness=-1)
    return frame


def test_optical_color_tracker_is_a_base_position_tracker():
    tracker = OpticalColorTracker()
    assert isinstance(tracker, BasePositionTracker)


def test_optical_color_tracker_locates_blob_at_center_of_frame():
    tracker = OpticalColorTracker()
    frame = make_frame_with_blob((FRAME_WIDTH // 2, FRAME_HEIGHT // 2))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True
    assert x == pytest.approx(0.5, abs=0.01)
    assert y == pytest.approx(0.5, abs=0.01)


def test_optical_color_tracker_locates_blob_off_center():
    tracker = OpticalColorTracker()
    px, py = 100, 360
    frame = make_frame_with_blob((px, py))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True
    assert x == pytest.approx(px / FRAME_WIDTH, abs=0.01)
    assert y == pytest.approx(py / FRAME_HEIGHT, abs=0.01)


def test_optical_color_tracker_reports_not_detected_when_no_blob_present():
    tracker = OpticalColorTracker()
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_reports_not_detected_for_none_frame():
    tracker = OpticalColorTracker()

    x, y, is_detected = tracker.get_position(None)

    assert is_detected is False


def test_optical_color_tracker_ignores_colors_outside_configured_range():
    # A pure red blob (hue 0) should not trigger the default teal/blue-tuned
    # tracker (hue 90-120).
    tracker = OpticalColorTracker()
    frame = make_frame_with_blob((FRAME_WIDTH // 2, FRAME_HEIGHT // 2), color=(0, 0, 255))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_ignores_a_washed_out_screen_sharing_the_same_hue():
    # Regression: a wall-mounted TV/monitor showing bluish-white content
    # was live-observed to false-positive-detect as the Pen Tip -- it
    # shares a similar hue to the marker, but is far more washed-out
    # (low saturation, bright) than the solid plastic marker.
    tracker = OpticalColorTracker()
    washed_out_bgr = (180, 166, 138)  # hue~100, sat~60, val~180
    frame = make_frame_with_blob((FRAME_WIDTH // 2, FRAME_HEIGHT // 2), color=washed_out_bgr)

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_second_hsv_band_is_unused_by_default():
    # The default color (teal/cyan-blue) doesn't wrap around hue 0/179, so
    # nothing should be auto-applied for hsv_lower2/upper2 -- a color that
    # would only match a red-style wrap-around band (hue near 179) must
    # stay undetected unless that second band is explicitly configured.
    tracker = OpticalColorTracker()
    hsv_wraparound_red = np.uint8([[[175, 200, 200]]])
    bgr = cv2.cvtColor(hsv_wraparound_red, cv2.COLOR_HSV2BGR)[0, 0].tolist()
    frame = make_frame_with_blob((FRAME_WIDTH // 2, FRAME_HEIGHT // 2), color=bgr)

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_accepts_an_explicit_second_hsv_band_for_wrap_around_colors():
    # A caller can opt into a second band explicitly -- e.g. to support a
    # red marker, which needs both ends of OpenCV's hue space.
    tracker = OpticalColorTracker(
        hsv_lower=(0, 80, 80),
        hsv_upper=(10, 255, 255),
        hsv_lower2=(170, 80, 80),
        hsv_upper2=(179, 255, 255),
    )
    hsv_wraparound_red = np.uint8([[[175, 200, 200]]])
    bgr = cv2.cvtColor(hsv_wraparound_red, cv2.COLOR_HSV2BGR)[0, 0].tolist()
    frame = make_frame_with_blob((FRAME_WIDTH // 2, FRAME_HEIGHT // 2), color=bgr)

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True


def test_optical_color_tracker_accepts_custom_hsv_range_for_different_pen_tip_colors():
    # A magenta pen tip can be configured via custom HSV bounds.
    magenta_bgr = (255, 0, 255)
    tracker = OpticalColorTracker(hsv_lower=(140, 80, 80), hsv_upper=(170, 255, 255))
    frame = make_frame_with_blob((200, 150), color=magenta_bgr)

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True
    assert x == pytest.approx(200 / FRAME_WIDTH, abs=0.01)
    assert y == pytest.approx(150 / FRAME_HEIGHT, abs=0.01)


# Adjustable Tracking Region (docs/specs/0002-adjustable-tracking-region.md):
# restricting the color/contour search to a configured quadrilateral region
# of the frame, so a stray blob elsewhere in the room is never detected --
# and so an arbitrary (non-rectangular) shape can match a trapezoidal board
# as seen from an angled camera.


def test_optical_color_tracker_detects_blob_inside_configured_region():
    region = rect_quad(50, 50, 200, 200)
    tracker = OpticalColorTracker(search_region=region)
    px, py = 100, 100  # inside the region
    frame = make_frame_with_blob((px, py))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True
    assert x == pytest.approx(px / FRAME_WIDTH, abs=0.01)
    assert y == pytest.approx(py / FRAME_HEIGHT, abs=0.01)


def test_optical_color_tracker_ignores_blob_outside_configured_region():
    region = rect_quad(50, 50, 100, 100)  # covers x:50-150, y:50-150
    tracker = OpticalColorTracker(search_region=region)
    frame = make_frame_with_blob((500, 400))  # well outside the region

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_detects_blob_inside_a_non_rectangular_quad():
    # A trapezoid (narrower at the top), the shape a straight-edged board
    # takes in frame when the camera is off to one side rather than
    # straight-on -- not expressible as an axis-aligned rectangle at all.
    region = Quad(points=(Point(200, 50), Point(400, 50), Point(500, 400), Point(100, 400)))
    tracker = OpticalColorTracker(search_region=region)
    frame = make_frame_with_blob((300, 300))  # inside the trapezoid

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True


def test_optical_color_tracker_ignores_blob_outside_a_non_rectangular_quad():
    # Same trapezoid as above -- a point that would be inside its enclosing
    # bounding box, but outside the trapezoid itself (its narrow top).
    region = Quad(points=(Point(200, 50), Point(400, 50), Point(500, 400), Point(100, 400)))
    tracker = OpticalColorTracker(search_region=region)
    frame = make_frame_with_blob((120, 60))  # inside the bbox, outside the trapezoid

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_reports_full_frame_normalized_position_even_when_restricted_to_a_region():
    # The reported x/y must stay normalized against the FULL frame, not
    # shifted/scaled relative to the region -- a polygon mask (rather than
    # cropping) means this is inherently always full-frame now, but worth
    # pinning explicitly since downstream consumers (homography, canvas
    # mapping) depend on it.
    region = rect_quad(200, 150, 300, 250)
    tracker = OpticalColorTracker(search_region=region)
    px, py = 350, 300  # inside the region, far from the region's own origin
    frame = make_frame_with_blob((px, py))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True
    assert x == pytest.approx(px / FRAME_WIDTH, abs=0.01)
    assert y == pytest.approx(py / FRAME_HEIGHT, abs=0.01)


def test_optical_color_tracker_set_search_region_restricts_search_after_construction():
    tracker = OpticalColorTracker()
    frame = make_frame_with_blob((500, 400))

    _, _, is_detected_before = tracker.get_position(frame)
    assert is_detected_before is True

    tracker.set_search_region(rect_quad(0, 0, 100, 100))
    _, _, is_detected_after = tracker.get_position(frame)
    assert is_detected_after is False


def test_optical_color_tracker_set_search_region_none_restores_full_frame_search():
    tracker = OpticalColorTracker(search_region=rect_quad(0, 0, 100, 100))
    frame = make_frame_with_blob((500, 400))

    tracker.set_search_region(None)
    _, _, is_detected = tracker.get_position(frame)

    assert is_detected is True


def test_optical_color_tracker_search_region_property_reflects_constructor_and_setter():
    tracker = OpticalColorTracker()
    assert tracker.search_region is None

    region = rect_quad(1, 2, 3, 4)
    tracker.set_search_region(region)
    assert tracker.search_region == region


def test_optical_color_tracker_handles_a_region_entirely_outside_the_frame_without_crashing():
    tracker = OpticalColorTracker(search_region=rect_quad(10000, 10000, 50, 50))
    frame = make_frame_with_blob((100, 100))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False
