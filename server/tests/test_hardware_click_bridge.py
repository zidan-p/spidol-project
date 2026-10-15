"""Tests for `HardwareClickBridgeTouchProvider`: turns a hardware touch
provider's touch signal (ESP32 Stylus switch) into a real OS left-click
(press/release) instead of feeding is_touching()/painting directly.
"""
from hal.hardware_click_bridge import HardwareClickBridgeTouchProvider
from hal.interfaces import BaseTouchProvider


class _FakeMouse:
    def __init__(self):
        self.pressed = []
        self.released = []

    def press(self, button):
        self.pressed.append(button)

    def release(self, button):
        self.released.append(button)


class _ToggleableTouchProvider(BaseTouchProvider):
    def __init__(self):
        self._touching = False

    def set_touching(self, touching: bool) -> None:
        self._touching = touching

    def is_touching(self) -> bool:
        return self._touching


def test_is_touching_always_returns_false():
    hardware = _ToggleableTouchProvider()
    bridge = HardwareClickBridgeTouchProvider(hardware, mouse_factory=_FakeMouse)

    hardware.set_touching(True)
    assert bridge.is_touching() is False


def test_presses_on_the_hardware_touching_rising_edge():
    mouse = _FakeMouse()
    hardware = _ToggleableTouchProvider()
    bridge = HardwareClickBridgeTouchProvider(hardware, mouse_factory=lambda: mouse)

    hardware.set_touching(True)
    bridge.is_touching()

    assert len(mouse.pressed) == 1
    assert mouse.released == []


def test_does_not_press_again_while_still_touching():
    mouse = _FakeMouse()
    hardware = _ToggleableTouchProvider()
    bridge = HardwareClickBridgeTouchProvider(hardware, mouse_factory=lambda: mouse)

    hardware.set_touching(True)
    bridge.is_touching()
    bridge.is_touching()
    bridge.is_touching()

    assert len(mouse.pressed) == 1


def test_releases_on_the_hardware_touching_falling_edge():
    mouse = _FakeMouse()
    hardware = _ToggleableTouchProvider()
    bridge = HardwareClickBridgeTouchProvider(hardware, mouse_factory=lambda: mouse)

    hardware.set_touching(True)
    bridge.is_touching()
    hardware.set_touching(False)
    bridge.is_touching()

    assert len(mouse.pressed) == 1
    assert len(mouse.released) == 1
