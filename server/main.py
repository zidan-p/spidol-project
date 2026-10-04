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
`CameraImageSource` (instead of `BlankCanvasImageSource`) plus a
`HomographyCalibrator` and `TrackingLossBridge`, all passed into
`server_app.create_server`, which feeds a real captured frame into the
tracker every telemetry tick and applies homography + tracking-loss bridging
to its output before broadcasting -- see `make_camera_resources` below and
`server_app.py`'s module docstring for the telemetry-loop wiring itself.
`BleTouchProvider` (ticket 05, the real Stylus over BLE) is wired here behind
`--ble-address` without changing anything below the HAL seam.

BLE mode (`--ble-address <mac-or-uuid>`): `make_touch_provider` returns a
`BleTouchProvider` instead of `KeyboardMockProvider`, the pynput mouse
listener is skipped (no mouse involved once a real Stylus is attached), and
`run()` starts `touch_provider.run_forever()` as a background task plus
wires `touch_provider.set_on_ai_trigger(server.fire_ai_trigger)` once the
server exists -- see `server_app.py`'s module docstring for why that's a
direct call, not a self-directed WebSocket message. This firmware pairing
(GATT service/characteristic UUIDs, GPIO pins) is documented in
`spidol/spidol_firmware.ino`.
"""
import argparse
import asyncio
import functools
import http.server
import os
import threading
from pathlib import Path

from ai.gemini_pipeline import make_live_client
from hal.image_source import BlankCanvasImageSource, CameraImageSource
from hal.providers import BleTouchProvider, KeyboardMockProvider
from hal.trackers import OpticalColorTracker, SystemMouseFallbackTracker
from server_app import create_server
from vision.homography import HomographyCalibrator
from vision.tracking_loss import TrackingLossBridge

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
        "exposes itself as a standard UVC webcam, see docs/adr/0003).",
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
    return parser.parse_args(argv)


def make_touch_provider(args: argparse.Namespace):
    """Picks the touch-signal source: the real Stylus over BLE if
    `--ble-address` was given, else the v1 mouse-click stand-in.
    `on_ai_trigger` is deliberately left unset here -- see `run()`, which
    wires it to `server.fire_ai_trigger` once the server exists.
    """
    if args.ble_address:
        return BleTouchProvider(
            device_address=args.ble_address,
            touch_char_uuid=BLE_TOUCH_CHAR_UUID,
            ai_trigger_char_uuid=BLE_AI_TRIGGER_CHAR_UUID,
        )
    return KeyboardMockProvider()


def make_tracker(args: argparse.Namespace):
    """Picks the position-tracking driver: `OpticalColorTracker` if
    `--tracker=optical-color` was given, else the v1 mouse fallback. Mirrors
    `make_touch_provider`'s `--ble-address` selection pattern above.
    """
    if args.tracker == "optical-color":
        return OpticalColorTracker()
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
    v1 mouse-mode defaults (blank image source, no homography/loss bridge)
    otherwise. Mirrors `make_touch_provider`'s `--ble-address` branch.

    `capture_factory` is forwarded to `CameraImageSource` purely so tests can
    avoid opening a real camera device (see hal/image_source.py).
    """
    if args.tracker != "optical-color":
        return BlankCanvasImageSource(), None, None

    kwargs = {} if capture_factory is None else {"capture_factory": capture_factory}
    image_source = CameraImageSource(camera_index=args.camera_index, **kwargs)
    homography = HomographyCalibrator()
    loss_bridge = TrackingLossBridge()
    return image_source, homography, loss_bridge


def make_gemini_client():
    """Constructs the live Gemini client if GEMINI_API_KEY is configured,
    else returns None -- every AI Trigger then serves the Cached Fallback
    Schema (see ai/gemini_pipeline.py), so the server still runs and demos
    correctly without a key configured.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("No GEMINI_API_KEY set; AI Trigger will always serve the Cached Fallback Schema.")
        return None
    return make_live_client(api_key=api_key)


async def run(args: argparse.Namespace) -> None:
    tracker = make_tracker(args)
    touch_provider = make_touch_provider(args)
    gemini_client = make_gemini_client()
    image_source, homography, loss_bridge = make_camera_resources(args)

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
        gemini_client=gemini_client,
        image_source=image_source,
        homography=homography,
        loss_bridge=loss_bridge,
    ) as server:
        if isinstance(touch_provider, BleTouchProvider):
            # Wire the real AI Trigger button straight into the server's
            # direct call path (see server_app.py's module docstring) --
            # the BLE notification callback calls this directly, no
            # self-directed WebSocket message involved.
            touch_provider.set_on_ai_trigger(server.fire_ai_trigger)
            asyncio.create_task(touch_provider.run_forever())
            print(f"Connecting to SPIDOL Stylus at {args.ble_address}...")

        await server.wait_closed()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
