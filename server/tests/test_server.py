"""Integration test for the WebSocket broadcast seam: a real server, a real
client connection, asserting the TRACK_UPDATE contract documented in
SPEC.md section 4.A arrives over the wire at the advertised rate.
"""
import asyncio
import json

import pytest
import websockets

from server_app import create_server
from hal.image_source import BlankCanvasImageSource
from hal.interfaces import BasePositionTracker
from hal.trackers import SystemMouseFallbackTracker
from hal.providers import KeyboardMockProvider
from vision.homography import HomographyCalibrator
from vision.tracking_loss import TrackingLossBridge


async def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_client_receives_track_update_messages_matching_contract():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (100, 50), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            raw = await asyncio.wait_for(client.recv(), timeout=1)
            payload = json.loads(raw)

    assert payload["type"] == "TRACK_UPDATE"
    assert payload["device_id"] == "spidol_main"
    assert payload["x"] == pytest.approx(0.1)
    assert payload["y"] == pytest.approx(0.05)
    assert payload["is_touching"] is False
    assert payload["is_detected"] is True
    assert isinstance(payload["fps"], (int, float))


@pytest.mark.asyncio
async def test_touch_provider_state_is_reflected_in_next_broadcast():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()
    touch_provider.set_touching(True)

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            raw = await asyncio.wait_for(client.recv(), timeout=1)
            payload = json.loads(raw)

    assert payload["is_touching"] is True


@pytest.mark.asyncio
async def test_multiple_clients_all_receive_broadcasts():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client_a, websockets.connect(
            f"ws://127.0.0.1:{port}"
        ) as client_b:
            raw_a = await asyncio.wait_for(client_a.recv(), timeout=1)
            raw_b = await asyncio.wait_for(client_b.recv(), timeout=1)

    assert json.loads(raw_a)["type"] == "TRACK_UPDATE"
    assert json.loads(raw_b)["type"] == "TRACK_UPDATE"


class _FixedCameraTracker(BasePositionTracker):
    """Reports a fixed camera-space point, ignoring whatever frame it's
    handed -- stands in for `OpticalColorTracker` so homography wiring can be
    tested without a real camera frame."""

    def __init__(self, x, y, is_detected=True):
        self._x, self._y, self._is_detected = x, y, is_detected

    def get_position(self, frame=None):
        return self._x, self._y, self._is_detected


@pytest.mark.asyncio
async def test_homography_is_applied_to_tracker_output_before_broadcast():
    port = await _free_port()
    # Camera-space (100, 50) in a 200x100 rectangle maps to canvas-space
    # center (0.5, 0.5) -- see test_homography.py's identical fixture.
    tracker = _FixedCameraTracker(100, 50)
    touch_provider = KeyboardMockProvider()
    homography = HomographyCalibrator()
    homography.calibrate(
        src_points=[(0, 0), (200, 0), (200, 100), (0, 100)],
        dst_points=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    )

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=60, homography=homography
    ):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            raw = await asyncio.wait_for(client.recv(), timeout=1)
            payload = json.loads(raw)

    assert payload["x"] == pytest.approx(0.5, abs=1e-6)
    assert payload["y"] == pytest.approx(0.5, abs=1e-6)


@pytest.mark.asyncio
async def test_without_homography_tracker_output_is_broadcast_unchanged():
    port = await _free_port()
    tracker = _FixedCameraTracker(0.3, 0.7)
    touch_provider = KeyboardMockProvider()

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            raw = await asyncio.wait_for(client.recv(), timeout=1)
            payload = json.loads(raw)

    assert payload["x"] == pytest.approx(0.3)
    assert payload["y"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_telemetry_loop_feeds_a_real_frame_from_image_source_to_the_tracker():
    port = await _free_port()
    seen_frames = []

    class _FrameRecordingTracker(BasePositionTracker):
        def get_position(self, frame=None):
            seen_frames.append(frame)
            return 0.0, 0.0, True

    tracker = _FrameRecordingTracker()
    touch_provider = KeyboardMockProvider()
    image_source = BlankCanvasImageSource(width=16, height=12)

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=60, image_source=image_source
    ):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            await asyncio.wait_for(client.recv(), timeout=1)

    assert len(seen_frames) >= 1
    assert seen_frames[0].shape == (12, 16, 3)


@pytest.mark.asyncio
async def test_loss_bridge_interpolates_a_brief_tracking_loss_before_broadcast():
    port = await _free_port()

    # Detected at (0,0), one "lost" tick, then reacquired and held at (1,1)
    # forever -- the resolved stream should include an interpolated detected
    # sample for the lost tick instead of ever broadcasting is_detected=False,
    # mirroring test_tracking_loss.py's short-gap-under-threshold behavior.
    # fps is deliberately slow (one tick per 200ms) so the test client's
    # connect always completes well within the first tick, instead of racing
    # a 60fps loop that starts ticking before the client subscribes.
    readings = [(0.0, 0.0, True), (0.0, 0.0, False), (1.0, 1.0, True)]

    class _ScriptedTracker(BasePositionTracker):
        def __init__(self):
            self._index = 0

        def get_position(self, frame=None):
            reading = readings[min(self._index, len(readings) - 1)]
            self._index += 1
            return reading

    tracker = _ScriptedTracker()
    touch_provider = KeyboardMockProvider()
    loss_bridge = TrackingLossBridge(loss_threshold_s=10.0)  # generous: avoid flaky real-clock gaps

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=5, loss_bridge=loss_bridge
    ):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            messages = []
            for _ in range(4):
                raw = await asyncio.wait_for(client.recv(), timeout=2)
                messages.append(json.loads(raw))

    # The lost tick is never broadcast as pen-up (is_detected=False); it's
    # either held back pending reacquisition, or resolved into an
    # interpolated detected sample once (1,1) is reacquired.
    assert all(m["is_detected"] for m in messages)
    interpolated = [m for m in messages if 0.0 < m["x"] < 1.0]
    assert len(interpolated) == 1
    assert interpolated[0]["x"] == pytest.approx(interpolated[0]["y"])


@pytest.mark.asyncio
async def test_canvas_clear_message_resets_the_server_side_stroke_region_tracker():
    from ai.stroke_region import StrokeRegionTracker

    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (100, 100), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()
    touch_provider.set_touching(True)
    stroke_tracker = StrokeRegionTracker()

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=60, stroke_tracker=stroke_tracker
    ):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            # Let a couple of telemetry ticks ingest a stroke server-side,
            # then release the (mouse-stand-in) pen so the stroke completes
            # instead of staying active indefinitely.
            await asyncio.wait_for(client.recv(), timeout=1)
            await asyncio.wait_for(client.recv(), timeout=1)
            touch_provider.set_touching(False)
            await asyncio.wait_for(client.recv(), timeout=1)
            assert stroke_tracker.region_since_last_trigger() is not None

            await client.send(json.dumps({"type": "CANVAS_CLEAR"}))
            await asyncio.sleep(0.05)

    assert stroke_tracker.region_since_last_trigger() is None


@pytest.mark.asyncio
async def test_calibrate_message_triggers_homography_recalibration():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()
    homography = HomographyCalibrator()
    assert homography.is_calibrated is False

    async with create_server(
        tracker, touch_provider, host="127.0.0.1", port=port, fps=60, homography=homography
    ):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            await asyncio.wait_for(client.recv(), timeout=1)
            await client.send(json.dumps({"type": "CALIBRATE"}))
            await asyncio.sleep(0.05)

    assert homography.is_calibrated is True


@pytest.mark.asyncio
async def test_calibrate_message_is_a_no_op_when_no_homography_was_configured():
    port = await _free_port()
    tracker = SystemMouseFallbackTracker(position_source=lambda: (0, 0), screen_size=(1000, 1000))
    touch_provider = KeyboardMockProvider()

    async with create_server(tracker, touch_provider, host="127.0.0.1", port=port, fps=60):
        async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
            await asyncio.wait_for(client.recv(), timeout=1)
            await client.send(json.dumps({"type": "CALIBRATE"}))
            await asyncio.sleep(0.05)
            # Still connected / no crash -- the message is silently ignored.
            await asyncio.wait_for(client.recv(), timeout=1)
