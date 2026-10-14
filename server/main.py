"""Dual-purpose entrypoint: WebSocket broadcaster + (in production mode) a
static file host for the compiled `view/dist` bundle.

    python main.py --dev    Dev mode: WebSocket server only (:8765).
                             Run `pnpm run dev` separately in view/ (:5173).
    python main.py          Production mode: WebSocket server (:8765) AND an
                             HTTP static server for view/dist (:5000),
                             together behind one command.

v1 defaults to the mouse as the input source end-to-end (ticket 01): position
comes from `SystemMouseFallbackTracker`, and the Touch Signal stand-in comes
from the left mouse button via `KeyboardMockProvider`, bridged by a pynput
click listener. `OpticalColorTracker` (ticket 02, real camera-based position
tracking) is wired in behind `--tracker=optical-color`: it selects a real
`CameraImageSource` (a USB/UVC device index, instead of
`BlankCanvasImageSource`) -- or, with `--camera-url`, `HttpCameraImageSource`
instead (a camera streamed over HTTP, e.g. a phone running an "IP Webcam"-
style app at a URL like `http://127.0.0.1:8081/video`; takes precedence over
`--camera-index` when both are given) -- plus a `HomographyCalibrator` and
`TrackingLossBridge`, all passed into
`server_app.create_server`, which feeds a real captured frame into the
tracker every telemetry tick and applies homography + tracking-loss bridging
to its output before broadcasting -- see `make_camera_resources` below and
`server_app.py`'s module docstring for the telemetry-loop wiring itself.
`BleTouchProvider` (ticket 05, the real Stylus over BLE) is wired here behind
`--ble-address` without changing anything below the HAL seam.
`WifiTouchProvider` is a sibling for a WiFi/TCP firmware variant, wired
behind `--wifi-touch-port` the same way.

BLE mode (`--ble-address <mac-or-uuid>`): `make_touch_provider` returns a
`BleTouchProvider` instead of `KeyboardMockProvider`, the pynput mouse
listener is skipped (no mouse involved once a real Stylus is attached), and
`run()` starts `touch_provider.run_forever()` as a background task plus
wires `touch_provider.set_on_ai_trigger(server.fire_ai_trigger)` once the
server exists -- see `server_app.py`'s module docstring for why that's a
direct call, not a self-directed WebSocket message. This firmware pairing
(GATT service/characteristic UUIDs, GPIO pins) is documented in
`spidol/spidol_firmware.ino`.

WiFi mode (`--wifi-touch-port <port>`): `make_touch_provider` returns a
`WifiTouchProvider` instead, which listens for the ESP32's own outgoing TCP
connection (`spidol/src/main.cpp`'s `WiFiClient`-based firmware) rather than
this process connecting out. Carries both the Touch Signal (newline-
terminated "1"/"0" lines on each switch transition) and the AI Trigger (a
"TRIGGER" line, sent once per button press) over the same connection --
`run()` wires `set_on_ai_trigger(server.fire_ai_trigger)` the same way as
the BLE path above, just before starting its `run_forever()` background
task.

Adjustable Tracking Region (`--adjust-tracking-region`, docs/specs/0002-
adjustable-tracking-region.md): with `--tracker=optical-color`, `run()` pops
up `vision/region_picker.py`'s live preview window *before* constructing the
real `OpticalColorTracker` -- the operator drags out a rectangle (or just
confirms to accept the full frame), the window closes, and the resolved
region is baked into `OpticalColorTracker` via `make_tracker`'s
`search_region` parameter, all within this same invocation. Nothing is
persisted to disk; redo it next run if needed. Independent of
`--debug-camera` (combinable, but neither implies the other).
"""
import argparse
import asyncio
import functools
import http.server
import logging
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

from ai.vision_pipeline import DEFAULT_BASE_URL, DEFAULT_MODEL, LazyOpenAIClient
from hal.image_source import BrowserCanvasImageSource, CameraImageSource, HttpCameraImageSource
from hal.os_cursor_controller import OsCursorController
from hal.providers import BleTouchProvider, KeyboardMockProvider, WifiTouchProvider
from hal.trackers import OpticalColorTracker, SystemMouseFallbackTracker, detect_screen_size
from server_app import create_server
from vision.debug_preview import DebugPreviewTracker
from vision.homography import HomographyCalibrator
from vision.region_picker import pick_tracking_region
from vision.region_selector import Quad
from vision.tracking_loss import TrackingLossBridge

logger = logging.getLogger(__name__)

WEBSOCKET_HOST = "127.0.0.1"
WEBSOCKET_PORT = 8765
STATIC_HOST = "127.0.0.1"
STATIC_PORT = 5000
VIEW_DIST_DIR = Path(__file__).resolve().parent.parent / "view" / "dist"

# Must match the GATT UUIDs advertised by spidol/spidol_firmware.ino.
BLE_TOUCH_CHAR_UUID = "a1b2c3d4-0001-1000-8000-00805f9b34fb"
BLE_AI_TRIGGER_CHAR_UUID = "a1b2c3d4-0002-1000-8000-00805f9b34fb"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SPIDOL server")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Dev mode: WebSocket server only; serve the frontend via `pnpm run dev` instead.",
    )
    parser.add_argument(
        "--tracker",
        choices=["mouse", "optical-color"],
        default="mouse",
        help=(
            "Position-tracking driver: 'mouse' (default) uses "
            "SystemMouseFallbackTracker; 'optical-color' uses OpticalColorTracker "
            "against a real camera frame (via CameraImageSource), with "
            "HomographyCalibrator and TrackingLossBridge wired into the telemetry "
            "loop. Analogous to --ble-address for the touch-signal side."
        ),
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index to open when --tracker=optical-color (RemoteCam "
        "exposes itself as a standard UVC webcam, see docs/adr/0003). Ignored if "
        "--camera-url is given.",
    )
    parser.add_argument(
        "--camera-url",
        default=None,
        help=(
            "When --tracker=optical-color, stream the camera over HTTP instead of "
            "a USB/UVC device index -- e.g. a phone running an 'IP Webcam'-style "
            "Android app, served at a URL like http://127.0.0.1:8081/video. Takes "
            "precedence over --camera-index when both are given."
        ),
    )
    parser.add_argument(
        "--flip-camera",
        action="store_true",
        help=(
            "When --tracker=optical-color with a USB/UVC device (--camera-index, "
            "not --camera-url), mirror the captured frame left-right. A PC webcam "
            "typically faces the user directly, so a raw frame moves opposite to "
            "the user's real-world left/right, like a security camera rather than "
            "a mirror."
        ),
    )
    parser.add_argument(
        "--control-os-cursor",
        action="store_true",
        help=(
            "DANGEROUS, explicitly opt-in: moves the REAL OS mouse cursor to follow "
            "the tracked Pen Tip, and synthesizes a real left-click press/release on "
            "Touch Signal transitions -- letting the tracked marker replace the "
            "mouse for arbitrary on-screen UI, not just this app's own canvas. "
            "Unlike the Stylus's own Touch Signal (ADR-0001, which deliberately "
            "never drives the OS cursor to avoid a stray click landing wherever the "
            "literal cursor sits), this is a separate, clearly-labeled capability "
            "you are opting into with that same risk. Works with --tracker="
            "optical-color (camera-tracked) or --tracker=mouse (pointless but "
            "harmless -- the cursor already follows your own mouse)."
        ),
    )
    parser.add_argument(
        "--debug-camera",
        action="store_true",
        help=(
            "When --tracker=optical-color, pop up a local OpenCV window showing the "
            "live camera feed with the detected Pen Tip position (or 'NO TARGET') "
            "burned onto it -- the fastest way to confirm OpticalColorTracker is "
            "actually seeing the tracked color before trusting the drawing-based "
            "end-to-end test. No effect in mouse-fallback mode."
        ),
    )
    parser.add_argument(
        "--adjust-tracking-region",
        action="store_true",
        help=(
            "When --tracker=optical-color, before starting the server, pop up a "
            "live camera preview and let the operator drag out a rectangle "
            "restricting where OpticalColorTracker searches for the Pen Tip -- "
            "Enter/Space confirms (or accepts the full frame if nothing was "
            "dragged), Esc discards the current drag to redraw. The window closes "
            "once resolved and the same process continues into the normal server "
            "run with that region applied; nothing is persisted across restarts. "
            "No effect in mouse-fallback mode."
        ),
    )
    parser.add_argument(
        "--ble-address",
        default=None,
        help=(
            "MAC (Linux/Windows) or UUID (macOS) of the SPIDOL Stylus BLE peripheral. "
            "When set, touch signal and AI Trigger come from the real Stylus firmware "
            "(spidol/spidol_firmware.ino) via BleTouchProvider instead of the mouse/"
            "keyboard stand-in. Discover the address with `bleak`'s `BleakScanner.discover()` "
            "filtering by device name 'SPIDOL_Stylus'."
        ),
    )
    parser.add_argument(
        "--wifi-touch-port",
        type=int,
        default=None,
        help=(
            "Listen on this TCP port for the WiFi/TCP Stylus firmware variant "
            "(spidol/spidol_firmware.ino's WiFiClient-based main.cpp), which "
            "connects out to this process and sends newline-terminated '1'/'0' "
            "lines on each Tip Contact Switch transition. Mutually exclusive "
            "with --ble-address (that one wins if both are given)."
        ),
    )
    parser.add_argument(
        "--ai-base-url",
        default=None,
        help=(
            "Base URL of the OpenAI-compatible vision endpoint to use for the AI "
            "Trigger pipeline. Overrides AI_BASE_URL. Defaults to Gemini's own "
            "OpenAI-compatible endpoint if neither is set -- point this at "
            "OpenRouter (https://openrouter.ai/api/v1) or any other OpenAI-"
            "compatible provider instead to switch providers, pairing it with "
            "--ai-model and a matching AI_API_KEY."
        ),
    )
    parser.add_argument(
        "--ai-model",
        default=None,
        help="Model name to request at --ai-base-url. Overrides AI_MODEL.",
    )
    parser.add_argument(
        "--ai-timeout-s",
        type=float,
        default=None,
        help=(
            "Seconds to wait for the live vision model call before falling back "
            "to the Cached Fallback Schema. Overrides AI_TIMEOUT_S. Defaults to "
            "3.0 -- real OpenAI-compatible routers/providers can easily take "
            "longer than that, so raise this if AI Triggers always serve the "
            "fallback despite a working AI_API_KEY/AI_BASE_URL/AI_MODEL."
        ),
    )
    return parser.parse_args(argv)


def make_touch_provider(args: argparse.Namespace):
    """Picks the touch-signal source: the real Stylus over BLE if
    `--ble-address` was given, the WiFi/TCP firmware variant if
    `--wifi-touch-port` was given, else the v1 mouse-click stand-in.
    `on_ai_trigger` is deliberately left unset here -- see `run()`, which
    wires it to `server.fire_ai_trigger` once the server exists, for both
    the BLE and WiFi/TCP variants.
    """
    if args.ble_address:
        return BleTouchProvider(
            device_address=args.ble_address,
            touch_char_uuid=BLE_TOUCH_CHAR_UUID,
            ai_trigger_char_uuid=BLE_AI_TRIGGER_CHAR_UUID,
        )
    if args.wifi_touch_port:
        return WifiTouchProvider(port=args.wifi_touch_port)
    return KeyboardMockProvider()


def make_tracker(args: argparse.Namespace, search_region: Quad | None = None):
    """Picks the position-tracking driver: `OpticalColorTracker` if
    `--tracker=optical-color` was given, else the v1 mouse fallback. Mirrors
    `make_touch_provider`'s `--ble-address` selection pattern above.

    `search_region` (resolved by `run()`'s `--adjust-tracking-region` setup
    step, before this is called) is applied to the raw `OpticalColorTracker`
    *before* any `--debug-camera` wrapping, so it takes effect regardless of
    whether debug preview is also enabled.

    `--debug-camera` wraps the optical tracker in `DebugPreviewTracker`
    (transparent to the telemetry loop -- same `get_position` contract),
    popping up a local OpenCV preview window of what it's actually seeing.
    """
    if args.tracker == "optical-color":
        tracker = OpticalColorTracker(search_region=search_region)
        if args.debug_camera:
            tracker = DebugPreviewTracker(tracker)
        return tracker
    return SystemMouseFallbackTracker()


def make_click_handler(touch_provider: KeyboardMockProvider):
    """Bridges left-mouse-button state to the touch provider.

    Stands in for the real Tip Contact Switch (fired over BLE in later
    tickets) while no hardware stylus exists yet -- the rest of the pipeline
    (WebSocket contract, frontend stroke buffer) doesn't know the difference.
    """
    from pynput.mouse import Button

    def on_click(x, y, button, pressed):
        if button is Button.left:
            touch_provider.set_touching(pressed)

    return on_click


def start_static_server(directory: Path, host: str, port: int) -> threading.Thread:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread


def make_camera_resources(args: argparse.Namespace, capture_factory=None):
    """Builds the camera-dependent trio -- image source, homography
    calibrator, tracking-loss bridge -- for `--tracker=optical-color`, or the
    v1 mouse-mode defaults otherwise. Mirrors `make_touch_provider`'s
    `--ble-address` branch.

    Mouse mode uses `BrowserCanvasImageSource`, not `BlankCanvasImageSource`:
    the frontend sends its own canvas pixels alongside `AI_TRIGGER` (see
    `server_app.py`'s handler), so the AI pipeline can actually see what was
    drawn even with no real camera wired -- `BlankCanvasImageSource`'s fixed
    blank frame meant the live vision model could never recognize anything.

    `capture_factory` is forwarded to whichever image source gets
    constructed purely so tests can avoid opening a real camera device/
    network stream (see hal/image_source.py).

    `--camera-url`, if given, selects `HttpCameraImageSource` (a camera
    streamed over HTTP, e.g. a phone running an "IP Webcam"-style app)
    instead of `CameraImageSource` (a USB/UVC device index) -- takes
    precedence over `--camera-index` when both are set. `--flip-camera`
    only applies to the `CameraImageSource` (device-index) path -- a PC
    webcam typically faces the user directly, unlike a phone stream, which
    is usually already positioned the way the rig expects.
    """
    if args.tracker != "optical-color":
        return BrowserCanvasImageSource(), None, None

    kwargs = {} if capture_factory is None else {"capture_factory": capture_factory}
    if args.camera_url:
        image_source = HttpCameraImageSource(url=args.camera_url, **kwargs)
    else:
        image_source = CameraImageSource(
            camera_index=args.camera_index, flip_horizontal=args.flip_camera, **kwargs
        )
    homography = HomographyCalibrator()
    loss_bridge = TrackingLossBridge()
    return image_source, homography, loss_bridge


def make_vision_client(args: argparse.Namespace):
    """Returns a vision client if AI_API_KEY (or the legacy GEMINI_API_KEY)
    is configured, else None -- every AI Trigger then serves the Cached
    Fallback Schema (see ai/vision_pipeline.py), so the server still runs
    and demos correctly without a key configured.

    Returns a `LazyOpenAIClient`, not an already-constructed real one:
    importing the `openai` SDK (and its dependency tree) costs roughly 1-2s
    the first time in a process, and this is called during every server
    startup that has a key configured -- regardless of whether a session
    ever actually fires an AI Trigger. Deferring that cost to the first
    real AI Trigger keeps startup (camera/tracking-region setup included)
    from paying it every time.

    `--ai-base-url`/AI_BASE_URL let this point at any OpenAI-compatible
    endpoint -- Gemini's own (the default), OpenRouter
    (https://openrouter.ai/api/v1), or another provider/router -- paired
    with `--ai-model`/AI_MODEL for the model name to request there.
    """
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("No AI_API_KEY set; AI Trigger will always serve the Cached Fallback Schema.")
        return None, DEFAULT_MODEL

    base_url = args.ai_base_url or os.environ.get("AI_BASE_URL") or DEFAULT_BASE_URL
    model = args.ai_model or os.environ.get("AI_MODEL") or DEFAULT_MODEL
    return LazyOpenAIClient(api_key=api_key, base_url=base_url), model


def make_ai_timeout_s(args: argparse.Namespace) -> float:
    """Resolves `--ai-timeout-s`/AI_TIMEOUT_S, defaulting to 3.0. Real
    OpenAI-compatible routers/providers can easily take longer than that --
    if AI Triggers always serve the Cached Fallback Schema despite a working
    key/base_url/model, this is usually why.
    """
    if args.ai_timeout_s is not None:
        return args.ai_timeout_s
    env_value = os.environ.get("AI_TIMEOUT_S")
    return float(env_value) if env_value else 3.0


def make_os_cursor_controller(args: argparse.Namespace):
    """Returns an `OsCursorController` if `--control-os-cursor` was given,
    else `None` -- see that flag's help text for the real tradeoff this
    opts into (never active by default, matching every other optional
    collaborator `create_server` accepts).
    """
    if not args.control_os_cursor:
        return None
    print(
        "WARNING: --control-os-cursor is active -- the real mouse cursor will "
        "move and click based on tracked input. This can click anywhere on "
        "your screen, including outside this app."
    )
    return OsCursorController(screen_size=detect_screen_size())


async def run(args: argparse.Namespace) -> None:
    # Built first (and reused for the picker below, never opened twice) --
    # make_tracker needs the resolved search_region before it constructs
    # the real OpticalColorTracker, and the picker needs this same
    # image_source's capture_frame to show a live preview.
    image_source, homography, loss_bridge = make_camera_resources(args)

    search_region = None
    if args.tracker == "optical-color" and args.adjust_tracking_region:
        print(
            "Adjust Tracking Region: drag a rectangle over the live preview, "
            "Enter/Space to confirm (or accept the full frame), Esc to redraw."
        )
        search_region = pick_tracking_region(image_source.capture_frame)
        if search_region is not None:
            logger.info("Tracking region set to %r", search_region)
        else:
            logger.info("No tracking region selected; searching the full camera frame.")

    tracker = make_tracker(args, search_region=search_region)
    touch_provider = make_touch_provider(args)
    vision_client, ai_model = make_vision_client(args)
    ai_timeout_s = make_ai_timeout_s(args)
    os_cursor_controller = make_os_cursor_controller(args)

    if isinstance(touch_provider, KeyboardMockProvider):
        from pynput.mouse import Listener

        listener = Listener(on_click=make_click_handler(touch_provider))
        listener.start()

    if not args.dev:
        if not VIEW_DIST_DIR.exists():
            raise SystemExit(
                f"Production mode requires a built frontend at {VIEW_DIST_DIR}. "
                "Run `pnpm run build` in view/ first."
            )
        start_static_server(VIEW_DIST_DIR, STATIC_HOST, STATIC_PORT)
        print(f"Serving view/dist at http://{STATIC_HOST}:{STATIC_PORT}")

    print(f"WebSocket server at ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
    async with create_server(
        tracker,
        touch_provider,
        host=WEBSOCKET_HOST,
        port=WEBSOCKET_PORT,
        vision_client=vision_client,
        ai_model=ai_model,
        ai_timeout_s=ai_timeout_s,
        image_source=image_source,
        homography=homography,
        loss_bridge=loss_bridge,
        os_cursor_controller=os_cursor_controller,
    ) as server:
        if isinstance(touch_provider, BleTouchProvider):
            # Wire the real AI Trigger button straight into the server's
            # direct call path (see server_app.py's module docstring) --
            # the BLE notification callback calls this directly, no
            # self-directed WebSocket message involved.
            touch_provider.set_on_ai_trigger(server.fire_ai_trigger)
            asyncio.create_task(touch_provider.run_forever())
            print(f"Connecting to SPIDOL Stylus at {args.ble_address}...")
        elif isinstance(touch_provider, WifiTouchProvider):
            # Same direct-call wiring as the BLE path above -- the WiFi/TCP
            # firmware variant now also sends a "TRIGGER" line (see
            # hal/providers.py), not just touch signal.
            touch_provider.set_on_ai_trigger(server.fire_ai_trigger)
            asyncio.create_task(touch_provider.run_forever())
            print(f"Listening for SPIDOL Stylus (WiFi) on TCP port {args.wifi_touch_port}...")

        await server.wait_closed()


def main() -> None:
    # Without this, every module's module-level `logger.info(...)`/
    # `logger.warning(...)` call (e.g. WifiTouchProvider's "Stylus
    # connected"/"disconnected" logs) is silently dropped -- Python's root
    # logger has no handler by default, so only WARNING+ reaches stderr via
    # the fallback handler, and even that has no timestamp/module context.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
    load_dotenv()
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
