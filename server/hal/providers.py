"""Touch-signal provider drivers.

v1 ships `KeyboardMockProvider` as the mouse-click-based touch stub (this
ticket binds it to the left mouse button in main.py). `BleTouchProvider`
(ticket 05, real GATT notify consumer) and `WifiTouchProvider` (the
WiFi/TCP firmware variant, spidol/spidol_firmware.ino's WiFiClient-based
main.cpp) slot in here as sibling classes implementing the same
`BaseTouchProvider` ABC.
"""
import asyncio
import logging

from bleak import BleakClient

from hal.interfaces import BaseTouchProvider

logger = logging.getLogger(__name__)


class KeyboardMockProvider(BaseTouchProvider):
    """A settable touch-state stub, driven by mouse-down/up (or keyboard) events.

    Despite the name (kept for parity with the spec's HAL file layout), this
    ticket wires it to mouse button state rather than a literal keyboard key
    -- either is "not real BLE hardware", which is the property that matters.
    """

    def __init__(self):
        self._touching = False

    def set_touching(self, touching: bool) -> None:
        self._touching = touching

    def is_touching(self) -> bool:
        return self._touching


class BleTouchProvider(BaseTouchProvider):
    """Real-hardware touch-signal source (ticket 05): subscribes to the
    Stylus firmware's custom GATT `touching` characteristic over BLE via
    `bleak`, and bridges its async notification callback into the
    synchronous `is_touching()` seam the 60fps telemetry loop calls every
    tick (see spidol-research-notes.md section 3 -- bleak's notify API is
    callback-based with no synchronous "read latest value" primitive, so the
    callback just writes into a plain instance variable and `is_touching()`
    reads it back).

    Also subscribes to the second GATT characteristic the same firmware
    exposes -- the AI Trigger button notification -- and invokes an injected
    `on_ai_trigger` callback when it fires. This keeps `BleTouchProvider`
    decoupled from how the AI Trigger pipeline is actually wired (that's
    `server_app.py`'s `fire_ai_trigger` concern); this class only knows "a
    GATT characteristic notified, call back out."

    `client_factory` defaults to `bleak.BleakClient` but is a constructor
    parameter precisely so tests can inject a fake client (no real BLE radio
    needed) that captures the `start_notify` callback and lets a test invoke
    it directly to simulate a GATT notification.
    """

    def __init__(
        self,
        device_address: str,
        touch_char_uuid: str,
        ai_trigger_char_uuid: str,
        on_ai_trigger=None,
        client_factory=BleakClient,
    ):
        self._device_address = device_address
        self._touch_char_uuid = touch_char_uuid
        self._ai_trigger_char_uuid = ai_trigger_char_uuid
        self._on_ai_trigger = on_ai_trigger
        self._client_factory = client_factory

        self._touching = False
        self._client = None

    def set_on_ai_trigger(self, callback) -> None:
        """Wires (or re-wires) the AI-trigger callback after construction.

        Needed because of a startup-order constraint in main.py: this
        provider must be constructed before `server_app.create_server`
        starts (the telemetry loop needs a touch provider from its first
        tick), but the callback we actually want to wire -- the server's
        `fire_ai_trigger()` -- only exists on the `server` object `serve()`
        yields, which only exists after the server has started. So
        construction happens with `on_ai_trigger=None`, and main.py calls
        this setter once `server` exists.
        """
        self._on_ai_trigger = callback

    async def connect(self) -> None:
        """Connects to the Stylus and subscribes to both GATT
        characteristics. Must be awaited once (e.g. from an
        `asyncio.create_task` at server startup -- see research notes
        section 3) before `is_touching()` reports real hardware state.
        """
        self._client = self._client_factory(self._device_address)
        await self._client.connect()
        await self._client.start_notify(self._touch_char_uuid, self._on_touch_notify)
        await self._client.start_notify(self._ai_trigger_char_uuid, self._on_ai_trigger_notify)

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()

    async def run_forever(self, retry_delay_s: float = 1.0) -> None:
        """Connects and then reconnects on disconnect, forever. BLE
        disconnects are routine on commodity hardware (research notes
        section 3 gotchas) -- this keeps one bad link from killing the
        whole server process. Intended to be run as its own
        `asyncio.create_task` at server startup, in parallel with the
        telemetry loop, exactly like `connect()` alone would be.
        """
        while True:
            try:
                await self.connect()
                # bleak keeps notifying via callbacks on this same event
                # loop; just idle here until the connection drops.
                while self._client is not None and self._client.is_connected:
                    await asyncio.sleep(retry_delay_s)
            except Exception:
                logger.exception("BleTouchProvider connection lost; retrying")
            await asyncio.sleep(retry_delay_s)

    def _on_touch_notify(self, _characteristic, data: bytearray) -> None:
        # Called back on bleak's asyncio loop. Keep fast/non-blocking: just
        # a variable assignment, per the bridge pattern in the research
        # notes -- `is_touching()` reads this synchronously, no awaiting.
        self._touching = bool(data[0])

    def _on_ai_trigger_notify(self, _characteristic, _data: bytearray) -> None:
        if self._on_ai_trigger is None:
            return
        try:
            if asyncio.iscoroutinefunction(self._on_ai_trigger):
                asyncio.create_task(self._on_ai_trigger())
            else:
                self._on_ai_trigger()
        except Exception:
            # A notification callback must never raise back into bleak's
            # event loop -- a crash here would otherwise tear down the BLE
            # connection (or the whole process) over an AI-trigger-handling
            # bug, which is strictly worse than just logging and continuing.
            logger.exception("on_ai_trigger callback raised")

    def is_touching(self) -> bool:
        # Synchronous, cheap, callable from the 60fps telemetry loop without
        # awaiting anything -- the whole point of the bridge above.
        return self._touching


class WifiTouchProvider(BaseTouchProvider):
    """Touch-signal source for the WiFi/TCP firmware variant
    (spidol/spidol_firmware.ino's `WiFiClient`-based main.cpp): instead of
    this process connecting out over BLE, the ESP32 connects out to *this*
    process as a plain TCP client and sends newline-terminated ASCII "1"/"0"
    lines on each Tip Contact Switch transition (TTP223 touch module -> HIGH
    = pressed). No AI Trigger notification exists in that firmware today --
    unlike `BleTouchProvider`, there's no `on_ai_trigger` here.

    Mirrors `BleTouchProvider`'s shape otherwise: a background
    `run_forever()` coroutine (intended to run as its own
    `asyncio.create_task` at server startup) bridging the async socket read
    loop into the synchronous `is_touching()` seam the 60fps telemetry loop
    calls every tick.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self._host = host
        self._port = port
        self._touching = False
        self._server = None

    def is_touching(self) -> bool:
        return self._touching

    async def run_forever(self) -> None:
        """Starts listening for the Stylus's incoming TCP connection and
        serves forever, accepting reconnects (the firmware retries its own
        connection on drop, same as BLE disconnects are routine).
        """
        self._server = await asyncio.start_server(self._handle_client, self._host, self._port)
        async with self._server:
            await self._server.serve_forever()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        logger.info("WifiTouchProvider: Stylus connected from %s", peer)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                value = line.strip()
                if value == b"1":
                    self._touching = True
                elif value == b"0":
                    self._touching = False
        except Exception:
            logger.exception("WifiTouchProvider: connection error")
        finally:
            logger.info("WifiTouchProvider: Stylus disconnected")
            # A lost connection means the real switch state is no longer
            # known -- safer to assume released than to keep drawing with a
            # stale "still touching" forever.
            self._touching = False
            writer.close()
