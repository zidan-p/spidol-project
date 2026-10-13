"""Tests for `RegionSelector` (docs/specs/0002-adjustable-tracking-region.md,
ticket 2): the pure, cv2-free state machine behind the Adjustable Tracking
Region setup flow (`--adjust-tracking-region`). Tracks a provisional
rectangle through raw mouse-down/move/up events, and resolves it into a
final selection on `confirm()`/`discard()`.

Deliberately has no `cv2` dependency -- the real OpenCV window (mouse
callback wiring, live frame drawing, translating `cv2.waitKey()` codes into
`confirm()`/`discard()` calls) is a separate, untested real-I/O wrapper
around this class (ticket 3), mirroring the existing `DebugPreviewTracker`
(injectable `show_frame`) / `BleTouchProvider` (injectable `client_factory`)
pattern of a tested pure core plus an untested thin real-I/O shell.
"""
from vision.region_selector import Rect, RegionSelector


def test_starts_with_no_provisional_or_confirmed_selection():
    selector = RegionSelector()

    assert selector.provisional is None
    assert selector.confirmed is None


def test_mouse_down_starts_a_zero_size_provisional_rect_at_that_point():
    selector = RegionSelector()

    selector.on_mouse_down(10, 20)

    assert selector.provisional == Rect(x=10, y=20, width=0, height=0)


def test_mouse_move_while_dragging_grows_the_provisional_rect_toward_the_cursor():
    selector = RegionSelector()

    selector.on_mouse_down(10, 20)
    selector.on_mouse_move(50, 80)

    assert selector.provisional == Rect(x=10, y=20, width=40, height=60)


def test_mouse_move_normalizes_a_drag_in_any_direction_to_a_non_negative_rect():
    # Dragging from bottom-right back up to top-left should still produce a
    # valid rect anchored at the min corner, not a negative width/height.
    selector = RegionSelector()

    selector.on_mouse_down(100, 100)
    selector.on_mouse_move(40, 30)

    assert selector.provisional == Rect(x=40, y=30, width=60, height=70)


def test_mouse_move_before_any_mouse_down_is_a_no_op():
    selector = RegionSelector()

    selector.on_mouse_move(50, 50)

    assert selector.provisional is None


def test_mouse_up_finalizes_the_provisional_rect_at_the_release_point():
    selector = RegionSelector()

    selector.on_mouse_down(0, 0)
    selector.on_mouse_move(20, 20)
    selector.on_mouse_up(30, 30)

    assert selector.provisional == Rect(x=0, y=0, width=30, height=30)


def test_mouse_move_after_mouse_up_without_a_new_mouse_down_is_a_no_op():
    selector = RegionSelector()

    selector.on_mouse_down(0, 0)
    selector.on_mouse_up(30, 30)
    selector.on_mouse_move(999, 999)

    assert selector.provisional == Rect(x=0, y=0, width=30, height=30)


def test_confirm_locks_in_the_provisional_rect_as_the_final_selection():
    selector = RegionSelector()

    selector.on_mouse_down(0, 0)
    selector.on_mouse_up(40, 50)
    selector.confirm()

    assert selector.confirmed == Rect(x=0, y=0, width=40, height=50)


def test_confirm_with_no_provisional_rect_is_a_no_op():
    # Matches the "confirm without touching anything -> full camera frame"
    # story: ticket 3's real-I/O wrapper treats `confirmed is None` after
    # the setup loop ends as "use the full-frame default."
    selector = RegionSelector()

    selector.confirm()

    assert selector.confirmed is None


def test_confirm_refuses_a_degenerate_zero_area_rect():
    # A plain click with no drag at all shouldn't be confirmable as a real
    # selection -- same fallback-to-default behavior as never confirming.
    selector = RegionSelector()

    selector.on_mouse_down(10, 10)
    selector.on_mouse_up(10, 10)
    selector.confirm()

    assert selector.confirmed is None


def test_discard_clears_the_provisional_rect_so_the_operator_can_redraw():
    selector = RegionSelector()

    selector.on_mouse_down(0, 0)
    selector.on_mouse_up(40, 50)
    selector.discard()

    assert selector.provisional is None
    assert selector.confirmed is None


def test_discard_after_a_confirm_clears_the_confirmed_selection_too():
    selector = RegionSelector()

    selector.on_mouse_down(0, 0)
    selector.on_mouse_up(40, 50)
    selector.confirm()
    selector.discard()

    assert selector.confirmed is None


def test_a_new_mouse_down_starts_a_fresh_drag_regardless_of_prior_state():
    selector = RegionSelector()

    selector.on_mouse_down(0, 0)
    selector.on_mouse_up(40, 50)
    selector.confirm()

    selector.on_mouse_down(5, 5)

    assert selector.provisional == Rect(x=5, y=5, width=0, height=0)
