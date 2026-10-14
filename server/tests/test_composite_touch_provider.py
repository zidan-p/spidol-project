"""Tests for `CompositeTouchProvider`: OR-combines multiple touch-signal
sources (e.g. a real mouse click and the ESP32 Stylus's own switch) so
either one can independently paint the board, instead of the two being
mutually exclusive.
"""
from hal.interfaces import BaseTouchProvider
from hal.providers import CompositeTouchProvider, KeyboardMockProvider


class _FixedTouchProvider(BaseTouchProvider):
    def __init__(self, touching: bool):
        self._touching = touching

    def is_touching(self) -> bool:
        return self._touching


def test_composite_touch_provider_is_a_base_touch_provider():
    provider = CompositeTouchProvider(_FixedTouchProvider(False))
    assert isinstance(provider, BaseTouchProvider)


def test_is_touching_false_when_no_source_is_touching():
    provider = CompositeTouchProvider(_FixedTouchProvider(False), _FixedTouchProvider(False))
    assert provider.is_touching() is False


def test_is_touching_true_when_any_single_source_is_touching():
    provider = CompositeTouchProvider(_FixedTouchProvider(False), _FixedTouchProvider(True))
    assert provider.is_touching() is True


def test_is_touching_true_when_all_sources_are_touching():
    provider = CompositeTouchProvider(_FixedTouchProvider(True), _FixedTouchProvider(True))
    assert provider.is_touching() is True


def test_reflects_a_real_mouse_touch_provider_as_one_of_its_sources():
    mouse = KeyboardMockProvider()
    provider = CompositeTouchProvider(_FixedTouchProvider(False), mouse)

    assert provider.is_touching() is False
    mouse.set_touching(True)
    assert provider.is_touching() is True
