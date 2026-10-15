"""Touch-signal provider drivers.

v1 ships `KeyboardMockProvider` as the mouse-click-based touch stub (this
ticket binds it to the left mouse button in main.py). `BleTouchProvider`
(real GATT notify consumer), `WifiTouchProvider` (the WiFi/TCP firmware
variant), and `SerialTouchProvider` (the classic Bluetooth SPP firmware
variant, read back as a plain virtual COM port) slot in here as sibling
classes implementing the same `BaseTouchProvider` ABC -- one per
`spidol/src/main.cpp` firmware variant that has existed in this project.
"""
import asyncio
import logging
import threading

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
        """Connects to the Stylus and subscribes to the touch
        characteristic, plus the AI Trigger characteristic if the
        connected firmware actually has one. Must be awaited once (e.g.
        from an `asyncio.create_task` at server startup -- see research
        notes section 3) before `is_touching()` reports real hardware
        state.

        The current Stylus hardware only has the Tip Contact Switch
        wired up -- no AI Trigger body button exists yet -- so
        `spidol/src/main.cpp` doesn't create that characteristic at all.
        Subscribing to a characteristic the peripheral never created
        raises; that failure is swallowed here so a touch-only Stylus
        still works end-to-end, it just never fires AI Trigger. A future
        firmware revision that does wire up the body button needs no
        server-side change at all -- the subscribe just stops failing.
        """
        self._client = self._client_factory(self._device_address)
        await self._client.connect()
        await self._client.start_notify(self._touch_char_uuid, self._on_touch_notify)
        try:
            await self._client.start_notify(self._ai_trigger_char_uuid, self._on_ai_trigger_notify)
        except Exception:
            logger.info(
                "BleTouchProvider: no AI Trigger characteristic on this Stylus "
                "(touch-only firmware) -- Touch Signal still works."
            )

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


class CompositeTouchProvider(BaseTouchProvider):
    """Combines multiple touch-signal sources with OR logic: Touch Signal
    is True whenever any one of them reports touching.

    Lets a real mouse click and the ESP32 Stylus's own Tip Contact Switch
    (over BLE or WiFi) both independently paint the board at once, rather
    than forcing one exclusive source -- e.g. with `--control-os-cursor`,
    the camera-tracked cursor can be "clicked" either with the physical
    mouse button or the ESP board's switch.
    """

    def __init__(self, *providers: BaseTouchProvider):
        self.providers = providers

    def is_touching(self) -> bool:
        return any(provider.is_touching() for provider in self.providers)


class WifiTouchProvider(BaseTouchProvider):
    """Touch-signal and AI-Trigger source for the WiFi/TCP firmware variant
    (spidol/src/main.cpp's `WiFiClient`-based firmware): instead of this
    process connecting out over BLE, the ESP32 connects out to *this*
    process as a plain TCP client and sends newline-terminated ASCII lines:
    "1"/"0" on each Tip Contact Switch transition (touch signal), and
    "TRIGGER" once per AI Trigger button press (a one-shot action, not an
    ongoing state -- the firmware sends it once per press, not continuously
    while held).

    Mirrors `BleTouchProvider`'s shape: a background `run_forever()`
    coroutine (intended to run as its own `asyncio.create_task` at server
    startup) bridging the async socket read loop into the synchronous
    `is_touching()` seam the 60fps telemetry loop calls every tick, plus an
    injected `on_ai_trigger` callback (sync or async) invoked on each
    "TRIGGER" line -- same dual-callback-type handling as `BleTouchProvider`.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, on_ai_trigger=None):
        self._host = host
        self._port = port
        self._on_ai_trigger = on_ai_trigger
        self._touching = False
        self._server = None

    def set_on_ai_trigger(self, callback) -> None:
        """Wires (or re-wires) the AI-trigger callback after construction --
        same startup-order constraint as `BleTouchProvider.set_on_ai_trigger`:
        this provider must exist before `server_app.create_server` starts,
        but `server.fire_ai_trigger` only exists once the server has.
        """
        self._on_ai_trigger = callback

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
                    print("ADA SINYAL -> Stylus menyentuh papan")
                elif value == b"0":
                    self._touching = False
                    print("TIDAK ADA SINYAL -> Stylus lepas dari papan")
                elif value == b"TRIGGER":
                    self._handle_trigger_line()
        except Exception:
            logger.exception("WifiTouchProvider: connection error")
        finally:
            logger.info("WifiTouchProvider: Stylus disconnected")
            # A lost connection means the real switch state is no longer
            # known -- safer to assume released than to keep drawing with a
            # stale "still touching" forever.
            self._touching = False
            writer.close()

    def _handle_trigger_line(self) -> None:
        if self._on_ai_trigger is None:
            return
        try:
            if asyncio.iscoroutinefunction(self._on_ai_trigger):
                asyncio.create_task(self._on_ai_trigger())
            else:
                self._on_ai_trigger()
        except Exception:
            # A notification callback must never raise back into the read
            # loop -- a crash here would otherwise tear down the TCP
            # connection (or the whole server) over an AI-trigger-handling
            # bug, which is strictly worse than just logging and continuing.
            logger.exception("on_ai_trigger callback raised")


def _default_serial_factory(port: str, baudrate: int):
    import serial

    return serial.Serial(port, baudrate, timeout=1)


class SerialTouchProvider(BaseTouchProvider):
    """Touch-signal and AI-Trigger source for the classic Bluetooth SPP
    firmware variant (spidol/src/main.cpp's `BluetoothSerial`-based
    firmware, advertised as "SpidolPintar_BT"): after pairing that device
    in Windows' Bluetooth settings, it shows up as a plain virtual COM
    port (Device Manager -> Ports (COM & LPT) -> "Standard Serial over
    Bluetooth link (COMx)", the "Outgoing" one) -- over which the
    firmware sends the exact same newline-terminated "1"/"0" lines as the
    WiFi/TCP variant (`WifiTouchProvider`), just over a serial port
    instead of a TCP socket.

    `pyserial`'s API is blocking, unlike `bleak`/`asyncio.start_server`'s
    native async I/O -- so the actual read loop runs in a background
    thread (via `loop.run_in_executor`, started by `run_forever()`)
    rather than being a native coroutine. `is_touching()` just reads back
    whatever that thread last wrote, same "callback writes a plain
    instance variable, no awaiting" bridge pattern as
    `BleTouchProvider`/`WifiTouchProvider`. `serial_factory` is injected
    (mirrors `BleTouchProvider`'s `client_factory` seam) so tests never
    open a real COM port.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        on_ai_trigger=None,
        serial_factory=_default_serial_factory,
    ):
        self._port = port
        self._baudrate = baudrate
        self._on_ai_trigger = on_ai_trigger
        self._serial_factory = serial_factory
        self._touching = False
        self._loop: asyncio.AbstractEventLoop | None = None
        # Checked by _read_loop on every readline() timeout -- the only
        # way to actually stop the background thread, since cancelling
        # run_forever's own asyncio task has no effect on a thread already
        # blocked in a background executor (see stop()).
        self._stop_event = threading.Event()

    def set_on_ai_trigger(self, callback) -> None:
        """Wires (or re-wires) the AI-trigger callback after construction --
        same startup-order constraint as `WifiTouchProvider.set_on_ai_trigger`.
        """
        self._on_ai_trigger = callback

    def is_touching(self) -> bool:
        return self._touching

    def stop(self) -> None:
        """Signals the background read thread to exit at its next
        `readline()` timeout, instead of blocking forever. Cancelling
        `run_forever`'s own asyncio task does NOT do this by itself --
        asyncio cancellation has no effect on a thread already running in
        a background executor, it only stops *awaiting* it. Needed for a
        clean shutdown/test teardown rather than leaking a thread that
        blocks process exit.
        """
        self._stop_event.set()

    async def run_forever(self, retry_delay_s: float = 1.0) -> None:
        """Connects and then reconnects on disconnect, forever -- same
        shape as `BleTouchProvider.run_forever`/`WifiTouchProvider`'s
        accept-loop, since a dropped Bluetooth SPP link is just as routine
        as a BLE or TCP disconnect. Intended to be run as its own
        `asyncio.create_task` at server startup.
        """
        self._loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            try:
                await self._loop.run_in_executor(None, self._read_loop)
            except Exception:
                logger.exception("SerialTouchProvider: connection error")
            # A lost connection means the real switch state is no longer
            # known -- safer to assume released than to keep drawing with
            # a stale "still touching" forever.
            self._touching = False
            await asyncio.sleep(retry_delay_s)

    def _read_loop(self) -> None:
        # Runs on a background thread (see run_forever) -- blocking I/O
        # only, nothing here may touch the asyncio event loop directly.
        connection = self._serial_factory(self._port, self._baudrate)
        logger.info("SerialTouchProvider: connected to %s", self._port)
        try:
            while not self._stop_event.is_set():
                line = connection.readline()
                if not line:
                    continue
                value = line.strip()
                if value == b"1":
                    self._touching = True
                    print("ADA SINYAL -> Stylus menyentuh papan (Bluetooth Serial)")
                elif value == b"0":
                    self._touching = False
                    print("TIDAK ADA SINYAL -> Stylus lepas dari papan (Bluetooth Serial)")
                elif value == b"TRIGGER":
                    self._handle_trigger_line()
        finally:
            logger.info("SerialTouchProvider: disconnected from %s", self._port)
            connection.close()

    def _handle_trigger_line(self) -> None:
        # Called from the background thread (see _read_loop), NOT the
        # event loop thread -- unlike BleTouchProvider/WifiTouchProvider,
        # where the equivalent handler already runs on the event loop
        # (bleak's callback / asyncio.start_server's read loop both do),
        # so asyncio.create_task would be unsafe to call directly here.
        # run_coroutine_threadsafe/call_soon_threadsafe are the
        # cross-thread-safe equivalents, scheduling onto run_forever's
        # loop (captured in self._loop) instead of touching it directly.
        if self._on_ai_trigger is None:
            return
        try:
            if asyncio.iscoroutinefunction(self._on_ai_trigger):
                asyncio.run_coroutine_threadsafe(self._on_ai_trigger(), self._loop)
            else:
                self._loop.call_soon_threadsafe(self._on_ai_trigger)
        except Exception:
            logger.exception("on_ai_trigger callback raised")
