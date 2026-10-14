"""Tests for `SmoothingPositionTracker`: wraps any `BasePositionTracker`,
applying an exponential moving average (EMA) to its reported (x, y)
position to suppress small frame-to-frame jitter (color-detection/centroid
noise inherent to `OpticalColorTracker`) while staying responsive to real
movement -- mirrors `DebugPreviewTracker`'s "wrap any BasePositionTracker,
transparent to callers" pattern.
"""
from hal.interfaces import BasePositionTracker
from hal.smoothing_tracker import SmoothingPositionTracker


class _FakeTracker:
    def __init__(self, positions):
        self._positions = iter(positions)

    def get_position(self, frame=None):
        return next(self._positions)


def test_is_a_base_position_tracker():
    tracker = SmoothingPositionTracker(_FakeTracker([(0.5, 0.5, True)]))
    assert isinstance(tracker, BasePositionTracker)


def test_first_detected_sample_passes_through_unsmoothed():
    # Nothing to average against yet -- the very first detection should
    # report exactly where it is, not blended toward some default.
    tracker = SmoothingPositionTracker(_FakeTracker([(0.3, 0.7, True)]))

    x, y, is_detected = tracker.get_position()

    assert (x, y, is_detected) == (0.3, 0.7, True)


def test_smooths_small_jitter_between_consecutive_detected_samples():
    inner = _FakeTracker([(0.5, 0.5, True), (0.52, 0.48, True)])
    tracker = SmoothingPositionTracker(inner, alpha=0.3)

    tracker.get_position()
    x, y, is_detected = tracker.get_position()

    # Blended partway between the previous smoothed value (0.5, 0.5) and
    # the new raw sample (0.52, 0.48) -- not jumping straight to the raw
    # value, and not staying put either.
    assert is_detected is True
    assert 0.5 < x < 0.52
    assert 0.48 < y < 0.5


def test_higher_alpha_tracks_closer_to_the_raw_value():
    raw_sequence = [(0.0, 0.0, True), (1.0, 1.0, True)]
    low_alpha = SmoothingPositionTracker(_FakeTracker(list(raw_sequence)), alpha=0.1)
    high_alpha = SmoothingPositionTracker(_FakeTracker(list(raw_sequence)), alpha=0.9)

    low_alpha.get_position()
    x_low, _, _ = low_alpha.get_position()
    high_alpha.get_position()
    x_high, _, _ = high_alpha.get_position()

    assert x_high > x_low


def test_resets_smoothing_state_when_tracking_is_lost():
    # A lost-tracking sample must not leave a stale smoothed position that
    # then blends with whatever comes after reacquiring -- the next fresh
    # detection should report exactly where it is, same as the very first
    # detection ever would.
    inner = _FakeTracker([(0.9, 0.9, True), (0.0, 0.0, False), (0.1, 0.1, True)])
    tracker = SmoothingPositionTracker(inner, alpha=0.3)

    tracker.get_position()
    tracker.get_position()  # tracking lost
    x, y, is_detected = tracker.get_position()

    assert (x, y, is_detected) == (0.1, 0.1, True)


def test_not_detected_sample_is_passed_through_unchanged():
    inner = _FakeTracker([(0.0, 0.0, False)])
    tracker = SmoothingPositionTracker(inner)

    x, y, is_detected = tracker.get_position()

    assert (x, y, is_detected) == (0.0, 0.0, False)


def test_passes_the_frame_argument_through_to_the_inner_tracker():
    received = []

    class _RecordingTracker:
        def get_position(self, frame=None):
            received.append(frame)
            return (0.5, 0.5, True)

    tracker = SmoothingPositionTracker(_RecordingTracker())
    sentinel_frame = object()
    tracker.get_position(sentinel_frame)

    assert received == [sentinel_frame]


def test_inner_property_exposes_the_wrapped_tracker():
    inner = _FakeTracker([(0.5, 0.5, True)])
    tracker = SmoothingPositionTracker(inner)

    assert tracker.inner is inner


def test_search_region_property_forwards_to_the_wrapped_tracker():
    class _TrackerWithRegion:
        def __init__(self):
            self.search_region = "a-region-value"

        def get_position(self, frame=None):
            return (0.5, 0.5, True)

    inner = _TrackerWithRegion()
    tracker = SmoothingPositionTracker(inner)

    assert tracker.search_region == "a-region-value"
