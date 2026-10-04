"""Tests for the Hardware Abstraction Layer (HAL): tracker and touch-provider seams.

These tests exercise only the public ABC-defined methods (`get_position`,
`is_touching`) so that later tickets can swap in OpticalColorTracker /
BleTouchProvider without changing a single assertion here.
"""
import numpy as np
import pytest

from hal.interfaces import BasePositionTracker, BaseTouchProvider
from hal.trackers import SystemMouseFallbackTracker
from hal.providers import KeyboardMockProvider


def test_base_position_tracker_is_abstract():
    with pytest.raises(TypeError):
        BasePositionTracker()


def test_base_touch_provider_is_abstract():
    with pytest.raises(TypeError):
        BaseTouchProvider()


def test_system_mouse_fallback_tracker_is_a_base_position_tracker():
    tracker = SystemMouseFallbackTracker()
    assert isinstance(tracker, BasePositionTracker)


def test_system_mouse_fallback_tracker_reports_normalized_position_from_injected_source():
    # Inject a fake position source instead of touching the real OS cursor,
    # so the test is deterministic and doesn't depend on screen geometry.
    tracker = SystemMouseFallbackTracker(
        position_source=lambda: (960, 540),
        screen_size=(1920, 1080),
    )

    x, y, is_detected = tracker.get_position(frame=None)

    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.5)
    assert is_detected is True


def test_system_mouse_fallback_tracker_clamps_out_of_bounds_coordinates():
    tracker = SystemMouseFallbackTracker(
        position_source=lambda: (-50, 2000),
        screen_size=(1920, 1080),
    )

    x, y, is_detected = tracker.get_position(frame=None)

    assert x == pytest.approx(0.0)
    assert y == pytest.approx(1.0)
    assert is_detected is True


def test_keyboard_mock_provider_is_a_base_touch_provider():
    provider = KeyboardMockProvider()
    assert isinstance(provider, BaseTouchProvider)


def test_keyboard_mock_provider_defaults_to_not_touching():
    provider = KeyboardMockProvider()
    assert provider.is_touching() is False


def test_keyboard_mock_provider_reflects_set_touching_state():
    provider = KeyboardMockProvider()

    provider.set_touching(True)
    assert provider.is_touching() is True

    provider.set_touching(False)
    assert provider.is_touching() is False
