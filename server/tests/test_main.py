"""Tests for main.py's CLI mode selection and the mouse-click -> touch-signal
bridge (the ticket 01 stand-in for a real Tip Contact Switch), plus ticket
05's `--ble-address` flag that switches the touch-signal source over to the
real Stylus firmware via `BleTouchProvider`."""
from pynput.mouse import Button

from main import make_camera_resources, make_click_handler, make_touch_provider, make_tracker, parse_args
from hal.image_source import BrowserCanvasImageSource, CameraImageSource, HttpCameraImageSource
from hal.providers import BleTouchProvider, KeyboardMockProvider, WifiTouchProvider
from hal.trackers import OpticalColorTracker, SystemMouseFallbackTracker
from vision.debug_preview import DebugPreviewTracker
from vision.homography import HomographyCalibrator
from vision.region_selector import Rect
from vision.tracking_loss import TrackingLossBridge


def test_parse_args_defaults_to_production_mode():
    args = parse_args([])
    assert args.dev is False


def test_parse_args_recognizes_dev_flag():
    args = parse_args(["--dev"])
    assert args.dev is True


def test_click_handler_sets_touching_true_on_left_button_press():
    provider = KeyboardMockProvider()
    handler = make_click_handler(provider)

    handler(0, 0, Button.left, True)

    assert provider.is_touching() is True


def test_click_handler_sets_touching_false_on_left_button_release():
    provider = KeyboardMockProvider()
    provider.set_touching(True)
    handler = make_click_handler(provider)

    handler(0, 0, Button.left, False)

    assert provider.is_touching() is False


def test_click_handler_ignores_non_left_buttons():
    provider = KeyboardMockProvider()
    handler = make_click_handler(provider)

    handler(0, 0, Button.right, True)

    assert provider.is_touching() is False


def test_parse_args_defaults_ble_address_to_none():
    args = parse_args([])
    assert args.ble_address is None


def test_parse_args_recognizes_ble_address_flag():
    args = parse_args(["--ble-address", "AA:BB:CC:DD:EE:FF"])
    assert args.ble_address == "AA:BB:CC:DD:EE:FF"


def test_make_touch_provider_returns_keyboard_mock_when_no_ble_address():
    args = parse_args([])
    provider = make_touch_provider(args)
    assert isinstance(provider, KeyboardMockProvider)


def test_make_touch_provider_returns_ble_touch_provider_when_ble_address_given():
    args = parse_args(["--ble-address", "AA:BB:CC:DD:EE:FF"])
    provider = make_touch_provider(args)
    assert isinstance(provider, BleTouchProvider)


def test_parse_args_defaults_wifi_touch_port_to_none():
    args = parse_args([])
    assert args.wifi_touch_port is None


def test_parse_args_recognizes_wifi_touch_port_flag():
    args = parse_args(["--wifi-touch-port", "8080"])
    assert args.wifi_touch_port == 8080


def test_make_touch_provider_returns_wifi_touch_provider_when_wifi_touch_port_given():
    args = parse_args(["--wifi-touch-port", "8080"])
    provider = make_touch_provider(args)
    assert isinstance(provider, WifiTouchProvider)


def test_make_touch_provider_prefers_ble_address_over_wifi_touch_port_if_both_given():
    args = parse_args(["--ble-address", "AA:BB:CC:DD:EE:FF", "--wifi-touch-port", "8080"])
    provider = make_touch_provider(args)
    assert isinstance(provider, BleTouchProvider)


def test_parse_args_defaults_tracker_to_mouse():
    args = parse_args([])
    assert args.tracker == "mouse"


def test_parse_args_recognizes_tracker_flag():
    args = parse_args(["--tracker", "optical-color"])
    assert args.tracker == "optical-color"


def test_make_tracker_returns_system_mouse_fallback_by_default():
    args = parse_args([])
    tracker = make_tracker(args)
    assert isinstance(tracker, SystemMouseFallbackTracker)


def test_make_tracker_returns_optical_color_tracker_when_selected():
    args = parse_args(["--tracker", "optical-color"])
    tracker = make_tracker(args)
    assert isinstance(tracker, OpticalColorTracker)


def test_parse_args_defaults_debug_camera_to_false():
    args = parse_args([])
    assert args.debug_camera is False


def test_make_tracker_wraps_in_debug_preview_tracker_when_flag_set():
    args = parse_args(["--tracker", "optical-color", "--debug-camera"])
    tracker = make_tracker(args)
    assert isinstance(tracker, DebugPreviewTracker)


def test_make_tracker_debug_camera_flag_has_no_effect_in_mouse_mode():
    args = parse_args(["--debug-camera"])
    tracker = make_tracker(args)
    assert isinstance(tracker, SystemMouseFallbackTracker)


def test_parse_args_defaults_adjust_tracking_region_to_false():
    args = parse_args([])
    assert args.adjust_tracking_region is False


def test_parse_args_recognizes_adjust_tracking_region_flag():
    args = parse_args(["--tracker", "optical-color", "--adjust-tracking-region"])
    assert args.adjust_tracking_region is True


def test_make_tracker_applies_search_region_to_optical_color_tracker():
    region = Rect(x=10, y=20, width=100, height=150)
    args = parse_args(["--tracker", "optical-color"])

    tracker = make_tracker(args, search_region=region)

    assert isinstance(tracker, OpticalColorTracker)
    assert tracker.search_region == region


def test_make_tracker_applies_search_region_even_when_wrapped_in_debug_preview():
    region = Rect(x=10, y=20, width=100, height=150)
    args = parse_args(["--tracker", "optical-color", "--debug-camera"])

    tracker = make_tracker(args, search_region=region)

    assert isinstance(tracker, DebugPreviewTracker)
    assert tracker.inner.search_region == region


def test_make_tracker_ignores_search_region_in_mouse_mode():
    region = Rect(x=10, y=20, width=100, height=150)
    args = parse_args([])

    tracker = make_tracker(args, search_region=region)

    assert isinstance(tracker, SystemMouseFallbackTracker)


class _FakeVideoCapture:
    """Avoids opening a real camera device/network stream in CI (see
    hal/image_source.py's test suite for the same seam). Works for both
    CameraImageSource (passed an int index) and HttpCameraImageSource
    (passed a URL string) -- it doesn't care which."""

    def __init__(self, index_or_url):
        self.index_or_url = index_or_url

    def read(self):
        return False, None

    def release(self):
        pass


def test_make_camera_resources_returns_browser_canvas_source_and_no_homography_for_mouse_tracker():
    args = parse_args([])
    image_source, homography, loss_bridge = make_camera_resources(args)

    assert isinstance(image_source, BrowserCanvasImageSource)
    assert homography is None
    assert loss_bridge is None


def test_make_camera_resources_returns_camera_backed_resources_for_optical_color_tracker():
    args = parse_args(["--tracker", "optical-color", "--camera-index", "2"])
    image_source, homography, loss_bridge = make_camera_resources(
        args, capture_factory=_FakeVideoCapture
    )

    assert isinstance(image_source, CameraImageSource)
    assert isinstance(homography, HomographyCalibrator)
    assert isinstance(loss_bridge, TrackingLossBridge)


def test_parse_args_defaults_camera_url_to_none():
    args = parse_args([])
    assert args.camera_url is None


def test_parse_args_recognizes_camera_url_flag():
    args = parse_args(["--tracker", "optical-color", "--camera-url", "http://127.0.0.1:8081/video"])
    assert args.camera_url == "http://127.0.0.1:8081/video"


def test_make_camera_resources_returns_http_camera_source_when_camera_url_given():
    args = parse_args(
        ["--tracker", "optical-color", "--camera-url", "http://127.0.0.1:8081/video"]
    )
    image_source, homography, loss_bridge = make_camera_resources(
        args, capture_factory=_FakeVideoCapture
    )

    assert isinstance(image_source, HttpCameraImageSource)
    assert isinstance(homography, HomographyCalibrator)
    assert isinstance(loss_bridge, TrackingLossBridge)


def test_make_camera_resources_prefers_camera_url_over_camera_index_if_both_given():
    args = parse_args(
        [
            "--tracker",
            "optical-color",
            "--camera-index",
            "2",
            "--camera-url",
            "http://127.0.0.1:8081/video",
        ]
    )
    image_source, _, _ = make_camera_resources(args, capture_factory=_FakeVideoCapture)

    assert isinstance(image_source, HttpCameraImageSource)
