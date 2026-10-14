"""Tests for `RegionSelector` (docs/specs/0002-adjustable-tracking-region.md):
the pure, cv2-free state machine behind the Adjustable Tracking Region setup
flow (`--adjust-tracking-region`). Drives four independently-draggable
corner handles (not just an axis-aligned rectangle), so the tracked area
can match a trapezoidal board shape seen from an angled camera.

Deliberately has no `cv2` dependency -- the real OpenCV window (mouse
callback wiring, live frame drawing, translating `cv2.waitKey()` codes into
`confirm()`/`discard()` calls) is a separate, untested real-I/O wrapper
around this class (`vision/region_picker.py`), mirroring the existing
`DebugPreviewTracker` (injectable `show_frame`) / `BleTouchProvider`
(injectable `client_factory`) pattern of a tested pure core plus an
untested thin real-I/O shell.
"""
from vision.region_selector import Point, Quad, RegionSelector


def test_starts_with_corners_at_the_full_frame_and_no_confirmed_selection():
    selector = RegionSelector(frame_size=(100, 50))

    assert selector.points == (
        Point(0, 0),
        Point(99, 0),
        Point(99, 49),
        Point(0, 49),
    )
    assert selector.confirmed is None


def test_mouse_down_near_a_corner_grabs_and_moves_it():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(5, 5))  # close to the top-left corner (0,0)

    assert selector.points[0] == Point(5, 5)
    # The other three corners are untouched.
    assert selector.points[1] == Point(99, 0)
    assert selector.points[2] == Point(99, 49)
    assert selector.points[3] == Point(0, 49)


def test_mouse_down_far_from_every_corner_grabs_nothing():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(50, 25))  # dead center, far from all 4 corners

    assert selector.points == (
        Point(0, 0),
        Point(99, 0),
        Point(99, 49),
        Point(0, 49),
    )


def test_mouse_move_follows_the_grabbed_corner():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(2, 2))  # grabs top-left
    selector.on_mouse_move(Point(20, 15))

    assert selector.points[0] == Point(20, 15)


def test_mouse_move_without_a_grabbed_corner_is_a_no_op():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_move(Point(20, 15))

    assert selector.points[0] == Point(0, 0)


def test_mouse_up_releases_the_corner_so_further_moves_do_not_affect_it():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(2, 2))
    selector.on_mouse_up(Point(20, 15))
    selector.on_mouse_move(Point(60, 40))

    assert selector.points[0] == Point(20, 15)


def test_dragging_a_different_corner_does_not_affect_others():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(97, 2))  # near top-right (99, 0)
    selector.on_mouse_move(Point(80, 10))
    selector.on_mouse_up(Point(80, 10))

    assert selector.points == (
        Point(0, 0),
        Point(80, 10),
        Point(99, 49),
        Point(0, 49),
    )


def test_confirm_locks_in_the_current_four_corners():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(2, 2))
    selector.on_mouse_up(Point(10, 10))
    selector.confirm()

    assert selector.confirmed == Quad(
        points=(Point(10, 10), Point(99, 0), Point(99, 49), Point(0, 49))
    )


def test_confirm_without_touching_anything_still_confirms_the_full_frame():
    # Matches the "confirm without touching anything -> full camera frame"
    # story: the default quad already covers the full frame.
    selector = RegionSelector(frame_size=(100, 50))

    selector.confirm()

    assert selector.confirmed == Quad(
        points=(Point(0, 0), Point(99, 0), Point(99, 49), Point(0, 49))
    )


def test_confirm_refuses_a_degenerate_near_zero_area_quad():
    selector = RegionSelector(frame_size=(100, 50))

    # Collapse all four corners onto roughly the same point.
    for i, point in enumerate([Point(50, 25), Point(51, 25), Point(51, 26), Point(50, 26)]):
        # Grab each corner in turn by starting a drag near its current spot.
        selector.on_mouse_down(selector.points[i])
        selector.on_mouse_up(point)

    selector.confirm()

    assert selector.confirmed is None


def test_discard_resets_all_four_corners_to_the_full_frame_default():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(2, 2))
    selector.on_mouse_up(Point(40, 30))
    selector.discard()

    assert selector.points == (
        Point(0, 0),
        Point(99, 0),
        Point(99, 49),
        Point(0, 49),
    )


def test_discard_does_not_clear_an_already_confirmed_selection():
    selector = RegionSelector(frame_size=(100, 50))

    selector.on_mouse_down(Point(2, 2))
    selector.on_mouse_up(Point(10, 10))
    selector.confirm()
    confirmed_before = selector.confirmed

    selector.discard()

    assert selector.confirmed == confirmed_before
