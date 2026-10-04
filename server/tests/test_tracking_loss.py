"""Tests for Tracking Loss bridging (`vision/tracking_loss.py`).

GLOSSARY / SPEC 3.2.C: a brief (under ~150ms) failure of `OpticalColorTracker`
to locate the Pen Tip -- most commonly the writer's own hand/wrist occluding
it -- is bridged by linear interpolation between the last-known and
reacquired points. Beyond the threshold, the stroke ends (pen-up) instead of
guessing across a longer gap.

Exercised with a fake sample sequence carrying explicit timestamps, so gap
duration is deterministic and doesn't depend on a real clock or real frames.
"""
import pytest

from vision.tracking_loss import TrackedSample, TrackingLossBridge


def detected(t, x, y):
    return TrackedSample(timestamp=t, x=x, y=y, is_detected=True)


def lost(t):
    return TrackedSample(timestamp=t, x=0.0, y=0.0, is_detected=False)


def test_live_detected_samples_pass_through_unchanged():
    bridge = TrackingLossBridge(loss_threshold_s=0.15)

    out1 = bridge.push(detected(0.0, 0.1, 0.1))
    out2 = bridge.push(detected(0.016, 0.12, 0.1))

    assert out1 == [detected(0.0, 0.1, 0.1)]
    assert out2 == [detected(0.016, 0.12, 0.1)]


def test_short_gap_under_threshold_is_bridged_by_linear_interpolation():
    bridge = TrackingLossBridge(loss_threshold_s=0.15)

    bridge.push(detected(0.0, 0.0, 0.0))
    # Pen Tip occluded by the writer's hand for two frames...
    assert bridge.push(lost(0.03)) == []
    assert bridge.push(lost(0.06)) == []
    # ...then reacquired 90ms after it was last seen (under the 150ms bridge).
    resolved = bridge.push(detected(0.09, 0.9, 0.9))

    assert len(resolved) == 3
    # Interpolated point at t=0.03 is 1/3 of the way from (0,0) to (0.9,0.9).
    assert resolved[0].is_detected is True
    assert resolved[0].x == pytest.approx(0.3, abs=1e-6)
    assert resolved[0].y == pytest.approx(0.3, abs=1e-6)
    # Interpolated point at t=0.06 is 2/3 of the way.
    assert resolved[1].is_detected is True
    assert resolved[1].x == pytest.approx(0.6, abs=1e-6)
    assert resolved[1].y == pytest.approx(0.6, abs=1e-6)
    # The reacquired point itself passes through unchanged.
    assert resolved[2] == detected(0.09, 0.9, 0.9)


def test_gap_beyond_threshold_ends_the_stroke_with_pen_up_instead_of_interpolating():
    bridge = TrackingLossBridge(loss_threshold_s=0.15)

    bridge.push(detected(0.0, 0.0, 0.0))
    assert bridge.push(lost(0.05)) == []
    assert bridge.push(lost(0.10)) == []
    # Gap crosses the 150ms threshold before reacquisition -- pen-up fires
    # immediately rather than waiting indefinitely for the tip to reappear.
    resolved = bridge.push(lost(0.20))

    assert len(resolved) == 3
    assert all(sample.is_detected is False for sample in resolved)


def test_detection_after_a_pen_up_starts_a_fresh_stroke_without_interpolating_the_old_gap():
    bridge = TrackingLossBridge(loss_threshold_s=0.15)

    bridge.push(detected(0.0, 0.0, 0.0))
    bridge.push(lost(0.05))
    bridge.push(lost(0.30))  # exceeds threshold -> pen-up already fired

    resolved = bridge.push(detected(0.50, 0.5, 0.5))

    # No stale buffered samples get retroactively stitched in; it's just the
    # fresh, newly-detected point starting a new stroke.
    assert resolved == [detected(0.50, 0.5, 0.5)]


def test_never_detected_yet_passes_lost_samples_through_without_buffering():
    bridge = TrackingLossBridge(loss_threshold_s=0.15)

    resolved = bridge.push(lost(0.0))

    assert resolved == [lost(0.0)]
