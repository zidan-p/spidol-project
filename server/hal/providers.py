"""Touch-signal provider drivers.

v1 ships `KeyboardMockProvider` as the mouse-click-based touch stub (this
ticket binds it to the left mouse button in main.py). `BleTouchProvider`
(real GATT notify consumer) is a later ticket's concern and slots in here as
a sibling class implementing the same `BaseTouchProvider` ABC.
"""
from hal.interfaces import BaseTouchProvider


class KeyboardMockProvider(BaseTouchProvider):
    """A settable touch-state stub, driven by mouse-down/up (or keyboard) events.

    Despite the name (kept for parity with the spec's HAL file layout), this
    ticket wires it to mouse button state rather than a literal keyboard key
    -- either is "not real BLE hardware", which is the property that matters.
    """

    def __init__(self):
        self._touching = False

    def set_touching(self, touching: bool) -> None:
        self._touching = touching

    def is_touching(self) -> bool:
        return self._touching
