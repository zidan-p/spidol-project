"""Tests for the AI Trigger Region tracker: the server-side record of "every
stroke drawn since the last AI Trigger or canvas clear" (GLOSSARY.md: AI
Trigger Region), tracked by stroke id/timestamp rather than a fixed time
window.
"""
from ai.stroke_region import StrokeRegionTracker


def test_region_is_none_before_any_strokes():
    tracker = StrokeRegionTracker()
    assert tracker.region_since_last_trigger() is None


def test_region_covers_bounding_box_of_a_single_completed_stroke():
    tracker = StrokeRegionTracker()
    tracker.ingest(x=0.2, y=0.3, is_touching=True, is_detected=True)
    tracker.ingest(x=0.4, y=0.1, is_touching=True, is_detected=True)
    tracker.ingest(x=0.4, y=0.1, is_touching=False, is_detected=True)

    region = tracker.region_since_last_trigger()

    assert region.min_x == 0.2
    assert region.max_x == 0.4
    assert region.min_y == 0.1
    assert region.max_y == 0.3
    assert len(region.stroke_ids) == 1


def test_mid_formula_pause_does_not_clip_region_across_multiple_strokes():
    tracker = StrokeRegionTracker()
    # First stroke.
    tracker.ingest(x=0.1, y=0.1, is_touching=True, is_detected=True)
    tracker.ingest(x=0.1, y=0.1, is_touching=False, is_detected=True)
    # A pause (pen-up), then a second stroke -- both must be included, since
    # the region is "everything since the last trigger/clear", not a time
    # window that would clip the pause.
    tracker.ingest(x=0.9, y=0.9, is_touching=True, is_detected=True)
    tracker.ingest(x=0.9, y=0.9, is_touching=False, is_detected=True)

    region = tracker.region_since_last_trigger()

    assert region.min_x == 0.1
    assert region.max_x == 0.9
    assert len(region.stroke_ids) == 2


def test_mark_trigger_excludes_strokes_recorded_before_it():
    tracker = StrokeRegionTracker()
    tracker.ingest(x=0.1, y=0.1, is_touching=True, is_detected=True)
    tracker.ingest(x=0.1, y=0.1, is_touching=False, is_detected=True)

    tracker.mark_trigger()

    assert tracker.region_since_last_trigger() is None

    tracker.ingest(x=0.5, y=0.5, is_touching=True, is_detected=True)
    tracker.ingest(x=0.5, y=0.5, is_touching=False, is_detected=True)
    region = tracker.region_since_last_trigger()
    assert region.min_x == 0.5
    assert len(region.stroke_ids) == 1


def test_clear_resets_everything_including_prior_boundary():
    tracker = StrokeRegionTracker()
    tracker.ingest(x=0.1, y=0.1, is_touching=True, is_detected=True)
    tracker.ingest(x=0.1, y=0.1, is_touching=False, is_detected=True)
    tracker.clear()

    assert tracker.region_since_last_trigger() is None

    tracker.ingest(x=0.3, y=0.3, is_touching=True, is_detected=True)
    tracker.ingest(x=0.3, y=0.3, is_touching=False, is_detected=True)
    region = tracker.region_since_last_trigger()
    assert region.min_x == 0.3


def test_undetected_points_are_ignored():
    tracker = StrokeRegionTracker()
    tracker.ingest(x=0.9, y=0.9, is_touching=True, is_detected=False)
    assert tracker.region_since_last_trigger() is None


def test_in_progress_stroke_is_included_so_a_trigger_mid_stroke_still_captures_it():
    tracker = StrokeRegionTracker()
    tracker.ingest(x=0.2, y=0.2, is_touching=True, is_detected=True)
    # No pen-up yet -- the stroke is still active when AI Trigger fires.
    region = tracker.region_since_last_trigger()
    assert region.min_x == 0.2
    assert len(region.stroke_ids) == 1
