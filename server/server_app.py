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

DEVICE_ID = "spidol_main"


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


def _make_handler(server_box: dict, stroke_tracker, image_source, gemini_client, ai_timeout_s):
    async def handler(websocket):
        # TRACK_UPDATE is a pure broadcast stream requiring no per-client
        # request/response behavior; the one message type a client sends
        # *to* the server is the dev-mode AI_TRIGGER hook below.
        async for raw in websocket:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if message.get("type") == "AI_TRIGGER":
                await _fire_ai_trigger(
                    server_box, stroke_tracker, image_source, gemini_client, ai_timeout_s
                )

    return handler


async def _telemetry_loop(
    server, tracker: BasePositionTracker, touch_provider: BaseTouchProvider, stroke_tracker, fps: int
):
    frame_interval = 1 / fps
    last = time.monotonic()
    while True:
        now = time.monotonic()
        instantaneous_fps = 1 / (now - last) if now > last else 0.0
        last = now

        x, y, is_detected = tracker.get_position(frame=None)
        is_touching = touch_provider.is_touching()

        stroke_tracker.ingest(x=x, y=y, is_touching=is_touching, is_detected=is_detected)

        message = build_track_update(
            device_id=DEVICE_ID,
            x=x,
            y=y,
            is_touching=is_touching,
            is_detected=is_detected,
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
    handler = _make_handler(server_box, stroke_tracker, image_source, gemini_client, ai_timeout_s)

    async with serve(handler, host, port) as server:
        server_box["server"] = server
        server.fire_ai_trigger = functools.partial(
            _fire_ai_trigger, server_box, stroke_tracker, image_source, gemini_client, ai_timeout_s
        )
        loop_task = asyncio.create_task(
            _telemetry_loop(server, tracker, touch_provider, stroke_tracker, fps)
        )
        try:
            yield server
        finally:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
