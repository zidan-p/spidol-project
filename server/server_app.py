"""The WebSocket broadcast server: fans out TRACK_UPDATE messages (SPEC.md
section 4.A) to every connected client at a fixed rate, and handles the
AI Trigger hook (SPEC.md 3.2.D / ticket 04).

Depends only on the HAL ABCs (`BasePositionTracker`, `BaseTouchProvider`,
`BaseImageSource`), so swapping `SystemMouseFallbackTracker` for
`OpticalColorTracker` -- or `KeyboardMockProvider` for `BleTouchProvider`,
or `BlankCanvasImageSource` for a real camera source -- is a caller-side
concern (see `main.py`), not a change here.

Trigger-hook mechanism (ticket 04 decision, extended by ticket 05): the AI
Trigger is exposed as a WebSocket message, `{"type": "AI_TRIGGER"}`, that
*any* connected client can send -- not only a literal keyboard shortcut.
This matches "an abstracted AI Trigger event hook any input source can
call". For this ticket, the frontend's dev-mode "trigger" affordance (a
keyboard shortcut) just sends this WS message -- documented in
`view/src/App.jsx`.

Ticket 05 adds a second, direct call path to the *same* underlying logic:
the object yielded by `create_server`'s `async with` block exposes an async
`server.fire_ai_trigger()` method. This exists because the real Stylus body
button fires over a BLE GATT notification (see `hal.providers.BleTouchProvider`),
handled by a callback registered directly with `bleak` inside the running
server process -- it is already server-side code, running in the same
asyncio loop as this module, with no WebSocket client in the picture at all.
Routing it through "connect a WebSocket client to ourselves and send
`{"type": "AI_TRIGGER"}`" would be a pointless, fragile round-trip (extra
socket, extra JSON encode/decode, a new failure mode if that self-connection
ever couldn't be established). Instead, `main.py` wires
`touch_provider = BleTouchProvider(..., on_ai_trigger=server.fire_ai_trigger)`
once the server is up, so the BLE notification calls directly into the same
`handle_ai_trigger` + broadcast logic the WS path also uses -- `_fire_ai_trigger`
below is the single shared implementation; both call paths are thin wrappers
around it.

Region-tracking mechanism (ticket 04 decision): the server tracks strokes
itself via `ai.stroke_region.StrokeRegionTracker`, fed from the same
x/y/is_touching/is_detected values the telemetry loop already computes each
tick -- rather than trusting the frontend to report the region in the
trigger message. See `ai/stroke_region.py`'s docstring for the full
reasoning.

Camera-tracker wiring (ticket 02, closing a known gap): when `main.py`
selects `--tracker=optical-color`, it passes a real `image_source` (a
`CameraImageSource`), a `homography` (`HomographyCalibrator`), and a
`loss_bridge` (`TrackingLossBridge`) into `create_server`. The telemetry loop
below always captures a frame from `image_source` and hands it to
`tracker.get_position(frame=...)` -- harmless for `SystemMouseFallbackTracker`,
which ignores the frame, and exactly the "one-line swap" `hal/image_source.py`
always documented for a real camera tracker. `homography` and `loss_bridge`
default to `None`, in which case tracker output is broadcast exactly as
before (mouse/dev-mode path, unchanged).

Calibration Hotkey mechanism (ticket 02, closing a known gap): `{"type":
"CALIBRATE"}` is a second WS message any client can send (same "abstracted
hook" shape as `AI_TRIGGER`). The frontend's dev-mode stand-in is a keyboard
shortcut ("C", see `view/src/App.jsx`) with no real 4-corner point-picking UX
yet -- this is a documented dev-mode stub, not a finished calibration flow --
so the handler recalibrates against a fixed identity correspondence
(`DEFAULT_CALIBRATION_POINTS`) unless the message itself carries
`src_points`/`dst_points`, which a future real point-picking UI can supply
without any server-side change. If no `homography` was constructed (mouse
mode), this message is a no-op.

Canvas Clear wiring (closing a known gap): `{"type": "CANVAS_CLEAR"}` calls
`stroke_tracker.clear()` so a frontend Clear also resets the server-side AI
Trigger Region, matching `ai/stroke_region.py`'s documented `clear()` contract
-- previously nothing called it from the live server.
"""
import asyncio
import functools
import json
import time
from contextlib import asynccontextmanager

from websockets.asyncio.server import serve, broadcast

from ai.stroke_region import StrokeRegionTracker
from ai.trigger import handle_ai_trigger
from hal.image_source import BaseImageSource, BlankCanvasImageSource
from hal.interfaces import BasePositionTracker, BaseTouchProvider
from telemetry import build_track_update
from vision.homography import HomographyCalibrator
from vision.tracking_loss import TrackedSample, TrackingLossBridge

DEVICE_ID = "spidol_main"

# Dev-mode Calibration Hotkey stub (see module docstring): an identity
# correspondence, used only when a CALIBRATE message supplies no explicit
# points. A real 4-corner point-picking UI can override this per-message.
DEFAULT_CALIBRATION_POINTS = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


async def _fire_ai_trigger(server_box: dict, stroke_tracker, image_source, gemini_client, ai_timeout_s):
    """The single shared implementation behind both AI-trigger call paths
    (see this module's docstring): runs one `handle_ai_trigger` cycle and
    broadcasts the resulting widget message to every connected client.

    `handle_ai_trigger` itself is synchronous (it does its own internal
    blocking/timeout handling around the Gemini call -- see ai/trigger.py),
    so this wrapper's only job is picking the current `server.connections`
    out of `server_box` (populated once `serve()` has started, see
    `create_server` below) and broadcasting.
    """
    widget_message = handle_ai_trigger(
        stroke_tracker=stroke_tracker,
        image_source=image_source,
        gemini_client=gemini_client,
        timeout_s=ai_timeout_s,
    )
    broadcast(server_box["server"].connections, widget_message)


def _make_handler(
    server_box: dict, stroke_tracker, image_source, gemini_client, ai_timeout_s, homography=None
):
    async def handler(websocket):
        # TRACK_UPDATE is a pure broadcast stream requiring no per-client
        # request/response behavior; the message types a client sends *to*
        # the server are the dev-mode AI_TRIGGER, CALIBRATE, and CANVAS_CLEAR
        # hooks below.
        async for raw in websocket:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            message_type = message.get("type")

            if message_type == "AI_TRIGGER":
                await _fire_ai_trigger(
                    server_box, stroke_tracker, image_source, gemini_client, ai_timeout_s
                )
            elif message_type == "CANVAS_CLEAR":
                stroke_tracker.clear()
            elif message_type == "CALIBRATE" and homography is not None:
                src_points = message.get("src_points") or DEFAULT_CALIBRATION_POINTS
                dst_points = message.get("dst_points") or DEFAULT_CALIBRATION_POINTS
                homography.recalibrate(src_points, dst_points)

    return handler


async def _telemetry_loop(
    server,
    tracker: BasePositionTracker,
    touch_provider: BaseTouchProvider,
    stroke_tracker,
    fps: int,
    image_source: BaseImageSource,
    homography: HomographyCalibrator | None = None,
    loss_bridge: TrackingLossBridge | None = None,
):
    frame_interval = 1 / fps
    last = time.monotonic()
    while True:
        now = time.monotonic()
        instantaneous_fps = 1 / (now - last) if now > last else 0.0
        last = now

        frame = image_source.capture_frame()
        raw_x, raw_y, is_detected = tracker.get_position(frame=frame)
        is_touching = touch_provider.is_touching()

        if homography is not None and homography.is_calibrated and is_detected:
            raw_x, raw_y = homography.transform((raw_x, raw_y))

        if loss_bridge is not None:
            resolved = loss_bridge.push(
                TrackedSample(timestamp=now, x=raw_x, y=raw_y, is_detected=is_detected)
            )
        else:
            resolved = [TrackedSample(timestamp=now, x=raw_x, y=raw_y, is_detected=is_detected)]

        for sample in resolved:
            stroke_tracker.ingest(
                x=sample.x, y=sample.y, is_touching=is_touching, is_detected=sample.is_detected
            )

            message = build_track_update(
                device_id=DEVICE_ID,
                x=sample.x,
                y=sample.y,
                is_touching=is_touching,
                is_detected=sample.is_detected,
                fps=round(instantaneous_fps, 1),
            )
            broadcast(server.connections, message)

        await asyncio.sleep(frame_interval)


@asynccontextmanager
async def create_server(
    tracker: BasePositionTracker,
    touch_provider: BaseTouchProvider,
    host: str = "127.0.0.1",
    port: int = 8765,
    fps: int = 60,
    stroke_tracker: StrokeRegionTracker | None = None,
    image_source: BaseImageSource | None = None,
    gemini_client=None,
    ai_timeout_s: float = 3.0,
    homography: HomographyCalibrator | None = None,
    loss_bridge: TrackingLossBridge | None = None,
):
    """Starts the WebSocket server, its telemetry broadcast loop, and the AI
    Trigger hook together.

    `gemini_client` is optional and defaults to `None` (no live API calls --
    every AI Trigger serves the Cached Fallback Schema instead; see
    `ai/gemini_pipeline.py`), so tests and dev runs without a configured
    GEMINI_API_KEY still work end-to-end.

    Usage:
        async with create_server(tracker, touch_provider) as server:
            await server.wait_closed()

    The yielded `server` also gets a `fire_ai_trigger()` async method
    attached (ticket 05's direct call path -- see this module's docstring):

        async with create_server(tracker, touch_provider) as server:
            await server.fire_ai_trigger()  # no WebSocket client involved
    """
    stroke_tracker = stroke_tracker or StrokeRegionTracker()
    image_source = image_source or BlankCanvasImageSource()

    server_box: dict = {}
    handler = _make_handler(
        server_box, stroke_tracker, image_source, gemini_client, ai_timeout_s, homography=homography
    )

    async with serve(handler, host, port) as server:
        server_box["server"] = server
        server.fire_ai_trigger = functools.partial(
            _fire_ai_trigger, server_box, stroke_tracker, image_source, gemini_client, ai_timeout_s
        )
        loop_task = asyncio.create_task(
            _telemetry_loop(
                server,
                tracker,
                touch_provider,
                stroke_tracker,
                fps,
                image_source,
                homography=homography,
                loss_bridge=loss_bridge,
            )
        )
        try:
            yield server
        finally:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
