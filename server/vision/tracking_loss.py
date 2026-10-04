"""Tracking Loss bridging (SPEC 3.2.C, GLOSSARY: Tracking Loss).

A brief (under ~150ms) failure of `OpticalColorTracker` to locate the Pen
Tip -- most commonly the writer's own hand/wrist occluding it during normal
strokes -- is bridged by linearly interpolating between the last-known and
reacquired points, so the resulting stroke looks continuous. Beyond that
threshold, buffered samples are released as pen-up (is_detected=False)
instead of guessing across a longer gap.

`TrackingLossBridge` sits between a `BasePositionTracker` and the telemetry
broadcast loop: raw per-frame samples go in via `push`, and zero or more
resolved samples come out, released only once their fate (interpolated vs.
pen-up) is known. It deliberately does not implement `BasePositionTracker`
itself, since one input sample can resolve to zero, one, or several output
samples once a gap closes -- a shape the one-call-per-frame ABC can't
express.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TrackedSample:
    timestamp: float
    x: float
    y: float
    is_detected: bool


class TrackingLossBridge:
    """Buffers samples during a Tracking Loss gap and resolves them once the
    gap either closes (interpolate) or expires (pen-up)."""

    def __init__(self, loss_threshold_s: float = 0.15):
        self._loss_threshold_s = loss_threshold_s
        self._last_known: TrackedSample | None = None
        self._pending: list[TrackedSample] = []
        self._gap_already_ended: bool = False

    def push(self, sample: TrackedSample) -> list[TrackedSample]:
        """Feeds one raw sample; returns zero or more resolved samples, in order."""
        if sample.is_detected:
            return self._handle_detected(sample)
        return self._handle_lost(sample)

    def _handle_detected(self, sample: TrackedSample) -> list[TrackedSample]:
        if self._pending and self._last_known is not None:
            resolved = [
                self._interpolate(self._last_known, sample, buffered.timestamp)
                for buffered in self._pending
            ] + [sample]
        else:
            resolved = [sample]

        self._pending = []
        self._gap_already_ended = False
        self._last_known = sample
        return resolved

    def _handle_lost(self, sample: TrackedSample) -> list[TrackedSample]:
        if self._last_known is None:
            # Never detected yet -- nothing to bridge, pass through as-is.
            return [sample]

        if self._gap_already_ended:
            # Stroke already ended for this gap; no more buffering needed
            # until the Pen Tip is detected again.
            return [sample]

        self._pending.append(sample)
        gap_duration = sample.timestamp - self._last_known.timestamp

        if gap_duration > self._loss_threshold_s:
            resolved = [replace(buffered, is_detected=False) for buffered in self._pending]
            self._pending = []
            self._gap_already_ended = True
            return resolved

        # Still within the bridging window -- hold, nothing released yet.
        return []

    @staticmethod
    def _interpolate(start: TrackedSample, end: TrackedSample, at_timestamp: float) -> TrackedSample:
        span = end.timestamp - start.timestamp
        fraction = 0.0 if span == 0 else (at_timestamp - start.timestamp) / span
        return TrackedSample(
            timestamp=at_timestamp,
            x=start.x + fraction * (end.x - start.x),
            y=start.y + fraction * (end.y - start.y),
            is_detected=True,
        )
