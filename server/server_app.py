"""The WebSocket broadcast server: fans out TRACK_UPDATE messages (SPEC.md
section 4.A) to every connected client at a fixed rate.

Depends only on the HAL ABCs (`BasePositionTracker`, `BaseTouchProvider`), so
swapping `SystemMouseFallbackTracker` for `OpticalColorTracker` -- or
`KeyboardMockProvider` for `BleTouchProvider` -- is a caller-side concern
(see `main.py`), not a change here.
"""
import asyncio
import time
from contextlib import asynccontextmanager

from websockets.asyncio.server import serve, broadcast

from hal.interfaces import BasePositionTracker, BaseTouchProvider
from telemetry import build_track_update

DEVICE_ID = "spidol_main"


async def _noop_handler(websocket):
    # TRACK_UPDATE is a pure broadcast stream -- no per-client request/response
    # behavior is needed, so the handler just keeps the connection open.
    await websocket.wait_closed()


async def _telemetry_loop(server, tracker: BasePositionTracker, touch_provider: BaseTouchProvider, fps: int):
    frame_interval = 1 / fps
    last = time.monotonic()
    while True:
        now = time.monotonic()
        instantaneous_fps = 1 / (now - last) if now > last else 0.0
        last = now

        x, y, is_detected = tracker.get_position(frame=None)
        is_touching = touch_provider.is_touching()

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
):
    """Starts the WebSocket server and its telemetry broadcast loop together.

    Usage:
        async with create_server(tracker, touch_provider) as server:
            await server.wait_closed()
    """
    async with serve(_noop_handler, host, port) as server:
        loop_task = asyncio.create_task(_telemetry_loop(server, tracker, touch_provider, fps))
        try:
            yield server
        finally:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
