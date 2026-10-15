"""Bridges a hardware touch provider's touch signal (the ESP32 Stylus's
switch, reported over BLE or WiFi) into a real OS left mouse-click, rather
than that signal feeding `is_touching()`/painting directly.

Why: a direct touch signal only ever means "paint here." A real click
means "activate whatever is under the cursor" -- which also paints when
the cursor sits over the canvas, but additionally lets the ESP board's
switch interact with on-screen UI (sliders, buttons) the same way a
physical mouse click would, especially alongside `--control-os-cursor`'s
camera-tracked cursor. So the ESP board's own touch edges synthesize a
real press/release via `pynput.mouse.Controller` here; the resulting
(real or synthetic) click is picked up by the same global
`pynput.mouse.Listener` that already feeds `KeyboardMockProvider` for a
genuine mouse click (see `main.py`'s `run()`) -- one single touch pathway
downstream of this class, not two.
"""
from pynput.mouse import Button, Controller

from hal.interfaces import BaseTouchProvider


class HardwareClickBridgeTouchProvider(BaseTouchProvider):
    def __init__(self, hardware_provider: BaseTouchProvider, mouse_factory=Controller):
        self._hardware_provider = hardware_provider
        self._mouse = mouse_factory()
        self._was_touching = False

    def is_touching(self) -> bool:
        """Polls the wrapped hardware provider and synthesizes a real
        press/release on each touch edge -- but always returns `False`
        itself. The resulting click (consumed by the global mouse
        listener, same as any other click) is what actually drives Touch
        Signal downstream, not this method's return value.
        """
        touching = self._hardware_provider.is_touching()
        if touching and not self._was_touching:
            self._mouse.press(Button.left)
        elif not touching and self._was_touching:
            self._mouse.release(Button.left)
        self._was_touching = touching
        return False
