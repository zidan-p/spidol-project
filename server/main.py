"""Dual-purpose entrypoint: WebSocket broadcaster + (in production mode) a
static file host for the compiled `view/dist` bundle.

    python main.py --dev    Dev mode: WebSocket server only (:8765).
                             Run `pnpm run dev` separately in view/ (:5173).
    python main.py          Production mode: WebSocket server (:8765) AND an
                             HTTP static server for view/dist (:5000),
                             together behind one command.

v1 uses the mouse as the input source end-to-end (ticket 01): position comes
from `SystemMouseFallbackTracker`, and the Touch Signal stand-in comes from
the left mouse button via `KeyboardMockProvider`, bridged by a pynput click
listener. Later tickets swap these for `OpticalColorTracker` /
`BleTouchProvider` without changing anything below the HAL seam.
"""
import argparse
import asyncio
import functools
import http.server
import threading
from pathlib import Path

from hal.providers import KeyboardMockProvider
from hal.trackers import SystemMouseFallbackTracker
from server_app import create_server

WEBSOCKET_HOST = "127.0.0.1"
WEBSOCKET_PORT = 8765
STATIC_HOST = "127.0.0.1"
STATIC_PORT = 5000
VIEW_DIST_DIR = Path(__file__).resolve().parent.parent / "view" / "dist"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SPIDOL server")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Dev mode: WebSocket server only; serve the frontend via `pnpm run dev` instead.",
    )
    return parser.parse_args(argv)


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


async def run(args: argparse.Namespace) -> None:
    tracker = SystemMouseFallbackTracker()
    touch_provider = KeyboardMockProvider()

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
    async with create_server(tracker, touch_provider, host=WEBSOCKET_HOST, port=WEBSOCKET_PORT) as server:
        await server.wait_closed()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
