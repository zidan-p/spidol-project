"""Tracks the AI Trigger Region server-side (GLOSSARY.md: AI Trigger Region
-- every stroke drawn since the last AI Trigger or canvas clear, tracked by
stroke id/timestamp, not a fixed time window).

Design choice (documented per ticket 04): the server tracks its own stroke
buffer -- mirroring the shape of `view/src/lib/strokeBuffer.js` -- rather
than trusting the frontend to report the region in the trigger message. The
server already owns the authoritative x/y/is_touching/is_detected stream
(it's the source of TRACK_UPDATE), so it can independently reconstruct the
region without an extra wire contract, and this keeps the frontend's stroke
buffer and the server's symmetric-but-independent.
"""
import itertools
import time
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Region:
    """The AI Trigger Region's bounding box (GLOSSARY.md), plus the ids of
    the strokes it covers. A small typed stand-in for the bare dict this used
    to be -- same fields, but `ai/crop.py` and `ai/trigger.py` read them via
    attribute access instead of string keys.
    """

    min_x: float
    max_x: float
    min_y: float
    max_y: float
    stroke_ids: Sequence[int]


class StrokeRegionTracker:
    """Call `ingest(...)` once per telemetry tick (same inputs as a
    TRACK_UPDATE message). Call `mark_trigger()` after an AI Trigger has
    consumed the current region, and `clear()` on canvas clear.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._strokes: list[dict] = []
        self._active: dict | None = None
        self._next_id = itertools.count(1)
        self._boundary_index = 0

    def ingest(self, *, x: float, y: float, is_touching: bool, is_detected: bool) -> None:
        if not is_detected:
            return

        if is_touching:
            if self._active is None:
                self._active = {
                    "id": next(self._next_id),
                    "started_at": self._clock(),
                    "points": [],
                }
            self._active["points"].append((x, y))
        elif self._active is not None:
            self._strokes.append(self._active)
            self._active = None

    def region_since_last_trigger(self) -> Region | None:
        strokes = self._strokes[self._boundary_index:]
        points = [p for stroke in strokes for p in stroke["points"]]
        stroke_ids = [stroke["id"] for stroke in strokes]

        if self._active is not None:
            points = points + self._active["points"]
            stroke_ids = stroke_ids + [self._active["id"]]

        if not points:
            return None

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return Region(
            min_x=min(xs),
            max_x=max(xs),
            min_y=min(ys),
            max_y=max(ys),
            stroke_ids=stroke_ids,
        )

    def mark_trigger(self) -> None:
        self._boundary_index = len(self._strokes)

    def clear(self) -> None:
        self._strokes = []
        self._active = None
        self._boundary_index = 0
