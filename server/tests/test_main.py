"""Tests for main.py's CLI mode selection and the mouse-click -> touch-signal
bridge (the ticket's stand-in for a real Tip Contact Switch while there's no
BLE hardware yet)."""
from pynput.mouse import Button

from main import parse_args, make_click_handler
from hal.providers import KeyboardMockProvider


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
