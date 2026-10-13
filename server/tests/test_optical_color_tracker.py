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
from vision.region_selector import Rect

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Pure blue in BGR -> HSV hue ~120, squarely inside the tracker's default
# blue Pen Tip color range.
PEN_TIP_BGR = (255, 0, 0)


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
    # A red blob should not trigger the default blue-tuned tracker.
    tracker = OpticalColorTracker()
    frame = make_frame_with_blob((FRAME_WIDTH // 2, FRAME_HEIGHT // 2), color=(0, 0, 255))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_accepts_custom_hsv_range_for_different_pen_tip_colors():
    # A magenta pen tip can be configured via custom HSV bounds.
    magenta_bgr = (255, 0, 255)
    tracker = OpticalColorTracker(hsv_lower=(140, 80, 80), hsv_upper=(170, 255, 255))
    frame = make_frame_with_blob((200, 150), color=magenta_bgr)

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True
    assert x == pytest.approx(200 / FRAME_WIDTH, abs=0.01)
    assert y == pytest.approx(150 / FRAME_HEIGHT, abs=0.01)


# Adjustable Tracking Region (docs/specs/0002-adjustable-tracking-region.md,
# ticket 1): restricting the color/contour search to a configured sub-region
# of the frame, so a stray blob elsewhere in the room is never detected.


def test_optical_color_tracker_detects_blob_inside_configured_region():
    region = Rect(x=50, y=50, width=200, height=200)
    tracker = OpticalColorTracker(search_region=region)
    px, py = 100, 100  # inside the region
    frame = make_frame_with_blob((px, py))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is True
    assert x == pytest.approx(px / FRAME_WIDTH, abs=0.01)
    assert y == pytest.approx(py / FRAME_HEIGHT, abs=0.01)


def test_optical_color_tracker_ignores_blob_outside_configured_region():
    region = Rect(x=50, y=50, width=100, height=100)  # covers x:50-150, y:50-150
    tracker = OpticalColorTracker(search_region=region)
    frame = make_frame_with_blob((500, 400))  # well outside the region

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False


def test_optical_color_tracker_reports_full_frame_normalized_position_even_when_restricted_to_a_region():
    # The reported x/y must stay normalized against the FULL frame, not the
    # cropped sub-region -- otherwise downstream consumers (homography,
    # canvas mapping) would see a position silently shifted/scaled.
    region = Rect(x=200, y=150, width=300, height=250)
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

    tracker.set_search_region(Rect(x=0, y=0, width=100, height=100))
    _, _, is_detected_after = tracker.get_position(frame)
    assert is_detected_after is False


def test_optical_color_tracker_set_search_region_none_restores_full_frame_search():
    tracker = OpticalColorTracker(search_region=Rect(x=0, y=0, width=100, height=100))
    frame = make_frame_with_blob((500, 400))

    tracker.set_search_region(None)
    _, _, is_detected = tracker.get_position(frame)

    assert is_detected is True


def test_optical_color_tracker_search_region_property_reflects_constructor_and_setter():
    tracker = OpticalColorTracker()
    assert tracker.search_region is None

    region = Rect(x=1, y=2, width=3, height=4)
    tracker.set_search_region(region)
    assert tracker.search_region == region


def test_optical_color_tracker_handles_a_region_entirely_outside_the_frame_without_crashing():
    tracker = OpticalColorTracker(search_region=Rect(x=10000, y=10000, width=50, height=50))
    frame = make_frame_with_blob((100, 100))

    x, y, is_detected = tracker.get_position(frame)

    assert is_detected is False
