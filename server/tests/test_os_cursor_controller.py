"""Tests for `OsCursorController` -- the explicitly opt-in (`--control-os-
cursor`) bridge that moves the real OS mouse cursor to follow the tracked
Pen Tip, and synthesizes a real left-click on Touch Signal transitions.

Deliberately separate from, and never used by default alongside, the
project's actual Touch Signal pipeline (ADR-0001: the Stylus's own Touch
Signal never drives the OS cursor, specifically to avoid a stray click
landing wherever the literal cursor happens to sit). This controller is a
different, clearly-labeled capability the user explicitly opts into.

`mouse_factory` is injected (mirroring `BleTouchProvider`'s `client_factory`
seam) so these tests never move the real cursor or click anything on the
machine running them.
"""
from hal.os_cursor_controller import OsCursorController


class _FakeMouse:
    def __init__(self):
        self.position = (0, 0)
        self.pressed = []
        self.released = []

    def press(self, button):
        self.pressed.append(button)

    def release(self, button):
        self.released.append(button)


def test_update_moves_the_cursor_to_the_normalized_position_mapped_to_screen_pixels():
    mouse = _FakeMouse()
    controller = OsCursorController(screen_size=(1000, 500), mouse_factory=lambda: mouse)

    controller.update(x=0.25, y=0.5, is_touching=False, is_detected=True)

    assert mouse.position == (250, 250)


def test_update_presses_on_the_touching_rising_edge():
    mouse = _FakeMouse()
    controller = OsCursorController(screen_size=(1000, 500), mouse_factory=lambda: mouse)

    controller.update(x=0.1, y=0.1, is_touching=True, is_detected=True)

    assert len(mouse.pressed) == 1
    assert mouse.released == []


def test_update_does_not_press_again_while_still_touching():
    mouse = _FakeMouse()
    controller = OsCursorController(screen_size=(1000, 500), mouse_factory=lambda: mouse)

    controller.update(x=0.1, y=0.1, is_touching=True, is_detected=True)
    controller.update(x=0.2, y=0.2, is_touching=True, is_detected=True)
    controller.update(x=0.3, y=0.3, is_touching=True, is_detected=True)

    assert len(mouse.pressed) == 1


def test_update_releases_on_the_touching_falling_edge():
    mouse = _FakeMouse()
    controller = OsCursorController(screen_size=(1000, 500), mouse_factory=lambda: mouse)

    controller.update(x=0.1, y=0.1, is_touching=True, is_detected=True)
    controller.update(x=0.1, y=0.1, is_touching=False, is_detected=True)

    assert len(mouse.pressed) == 1
    assert len(mouse.released) == 1


def test_update_ignores_samples_where_tracking_is_lost():
    # A lost-tracking sample reports a meaningless (often (0, 0)) position --
    # must never move the cursor or synthesize a click from that garbage.
    mouse = _FakeMouse()
    controller = OsCursorController(screen_size=(1000, 500), mouse_factory=lambda: mouse)

    controller.update(x=0.5, y=0.5, is_touching=False, is_detected=True)
    controller.update(x=0.0, y=0.0, is_touching=True, is_detected=False)

    assert mouse.position == (500, 250)
    assert mouse.pressed == []


def test_update_releases_if_tracking_is_lost_while_touching():
    # Safety: never leave a real mouse button stuck "down" just because
    # tracking dropped out mid-press.
    mouse = _FakeMouse()
    controller = OsCursorController(screen_size=(1000, 500), mouse_factory=lambda: mouse)

    controller.update(x=0.1, y=0.1, is_touching=True, is_detected=True)
    controller.update(x=0.0, y=0.0, is_touching=True, is_detected=False)

    assert len(mouse.pressed) == 1
    assert len(mouse.released) == 1
