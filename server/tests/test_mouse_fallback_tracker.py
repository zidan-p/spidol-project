"""Tests for `MouseFallbackPositionTracker`: substitutes the real OS mouse
position for a wrapped tracker's reported position whenever that tracker
hasn't detected anything, so painting still works purely off a real
mouse-down/up gesture regardless of camera detection.
"""
from hal.interfaces import BasePositionTracker
from hal.mouse_fallback_tracker import MouseFallbackPositionTracker


class _FixedTracker(BasePositionTracker):
    def __init__(self, x: float, y: float, is_detected: bool):
        self._x, self._y, self._is_detected = x, y, is_detected

    def get_position(self, frame=None):
        return self._x, self._y, self._is_detected


def test_passes_through_the_inner_position_when_detected():
    inner = _FixedTracker(0.3, 0.4, True)
    tracker = MouseFallbackPositionTracker(
        inner, position_source=lambda: (999, 999), screen_size=(1000, 500)
    )

    assert tracker.get_position() == (0.3, 0.4, True)


def test_substitutes_the_real_mouse_position_when_not_detected():
    inner = _FixedTracker(0.0, 0.0, False)
    tracker = MouseFallbackPositionTracker(
        inner, position_source=lambda: (250, 250), screen_size=(1000, 500)
    )

    x, y, is_detected = tracker.get_position()

    assert (x, y) == (0.25, 0.5)
    assert is_detected is False


def test_clamps_the_mouse_position_into_0_1():
    inner = _FixedTracker(0.0, 0.0, False)
    tracker = MouseFallbackPositionTracker(
        inner, position_source=lambda: (-50, 10000), screen_size=(1000, 500)
    )

    x, y, _ = tracker.get_position()

    assert (x, y) == (0.0, 1.0)


def test_search_region_forwards_to_the_inner_tracker():
    class _TrackerWithRegion(_FixedTracker):
        search_region = "a-region"

    inner = _TrackerWithRegion(0.0, 0.0, True)
    tracker = MouseFallbackPositionTracker(inner, position_source=lambda: (0, 0), screen_size=(1, 1))

    assert tracker.search_region == "a-region"
