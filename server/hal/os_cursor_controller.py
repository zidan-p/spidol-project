"""`OsCursorController`: the explicitly opt-in (`--control-os-cursor`)
bridge that moves the real OS mouse cursor to follow the tracked Pen Tip
position, and synthesizes a real left-click press/release on Touch Signal
transitions -- letting the camera-tracked marker genuinely replace the
mouse for interacting with arbitrary on-screen UI, not just this app's own
canvas.

Deliberately separate from the project's actual Touch Signal pipeline
(ADR-0001): the Stylus's own Touch Signal never drives the OS cursor,
specifically to avoid a stray click landing wherever the literal cursor
happens to sit rather than where the pen points. This controller exists
for a different, clearly-labeled use case the user explicitly opts into
knowing that tradeoff -- it is never active unless `--control-os-cursor`
is passed, and nothing else in the pipeline is affected when it isn't.
"""
from pynput.mouse import Button, Controller


class OsCursorController:
    def __init__(self, screen_size: tuple[float, float], mouse_factory=Controller):
        self._screen_width, self._screen_height = screen_size
        self._mouse = mouse_factory()
        self._was_touching = False

    def update(self, x: float, y: float, is_touching: bool, is_detected: bool) -> None:
        """Moves the real OS cursor to `(x, y)` (normalized [0, 1], mapped
        to real screen pixels) and synthesizes a real left-click press on
        the touching rising edge, release on the falling edge.

        A lost-tracking sample (`is_detected=False`) reports a meaningless
        position (often `(0, 0)`) -- ignored entirely, including releasing
        an in-progress press rather than leaving a real mouse button stuck
        down just because tracking dropped out mid-press.
        """
        if not is_detected:
            if self._was_touching:
                self._mouse.release(Button.left)
                self._was_touching = False
            return

        screen_x = int(x * self._screen_width)
        screen_y = int(y * self._screen_height)
        self._mouse.position = (screen_x, screen_y)

        if is_touching and not self._was_touching:
            self._mouse.press(Button.left)
        elif not is_touching and self._was_touching:
            self._mouse.release(Button.left)
        self._was_touching = is_touching
