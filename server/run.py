"""Named presets for common `python main.py` flag combinations -- the
closest equivalent in this project to package.json's "scripts" field.
Zero new dependencies (unlike e.g. `poethepoet`), since this is just a
thin `subprocess` dispatch to `main.py`'s own existing CLI.

Usage:
    python run.py                  # lists available presets
    python run.py <preset>         # runs that preset
    python run.py <preset> <extra args...>
                                    # appends extra flags on top of the
                                    # preset -- e.g. add --wifi-touch-port
                                    # 8080 to any camera preset to also
                                    # wire up the ESP32 AI Trigger button,
                                    # without needing a separate preset
                                    # for every combination.

Before using a "-ble" preset, set BLE_ADDRESS below to the Stylus's real
MAC address (the firmware prints its own on every boot). Before using the
"-serial" preset, set SERIAL_TOUCH_PORT below to the COM port Windows
assigned after pairing "SpidolPintar_BT".
"""
import subprocess
import sys

IP_WEBCAM_URL = "http://127.0.0.1:8081/video"
# Not 8080 -- already occupied by an unrelated local process
# (whatsapp-bridge.exe) on this machine, which silently binds to
# 127.0.0.1 only and would make asyncio.start_server fail to bind at all.
WIFI_TOUCH_PORT = "8090"

# MAC address of the SPIDOL Stylus's BLE radio -- placeholder, replace
# with the real one. The firmware (spidol/src/main.cpp) prints it over
# Serial on every boot ("MAC address (pakai ini untuk --ble-address)"),
# or discover it with bleak's `BleakScanner.discover()` filtering by
# device name "SPIDOL_Stylus".
BLE_ADDRESS = "AA:BB:CC:DD:EE:FF"

# COM port for the classic Bluetooth SPP firmware variant
# (spidol/src/main.cpp's BluetoothSerial-based firmware, advertised as
# "SpidolPintar_BT") -- placeholder, replace with the real one. Pair the
# device in Windows' Bluetooth settings first, then check Device
# Manager's Ports (COM & LPT) section for the "Standard Serial over
# Bluetooth link" entry it creates (use the "Outgoing" one).
SERIAL_TOUCH_PORT = "COM9"

PRESETS = {
    "dev": [
        "--dev",
    ],
    "pc-camera": [
        "--dev",
        "--tracker", "optical-color",
        "--debug-camera",
        "--flip-camera",
        "--control-os-cursor",
        "--wifi-touch-port", WIFI_TOUCH_PORT,
    ],
    "ipwebcam": [
        "--dev",
        "--tracker", "optical-color",
        "--camera-url", IP_WEBCAM_URL,
        "--debug-camera",
    ],
    "ipwebcam-trigger": [
        "--dev",
        "--tracker", "optical-color",
        "--camera-url", IP_WEBCAM_URL,
        "--wifi-touch-port", WIFI_TOUCH_PORT,
        "--debug-camera",
    ],
    "adjust-region": [
        "--dev",
        "--tracker", "optical-color",
        "--camera-url", IP_WEBCAM_URL,
        "--adjust-tracking-region",
        "--debug-camera",
        "--control-os-cursor",
        "--wifi-touch-port", WIFI_TOUCH_PORT,
    ],
    # BLE variants -- same as their WiFi/TCP counterparts above, but the
    # Stylus connects over Bluetooth instead of WiFi (--ble-address wins
    # over --wifi-touch-port if both were ever given, so these are just
    # the clean/intentional way to pick BLE, not a hidden fallback).
    "pc-camera-ble": [
        "--dev",
        "--tracker", "optical-color",
        "--debug-camera",
        "--flip-camera",
        "--control-os-cursor",
        "--ble-address", BLE_ADDRESS,
    ],
    "adjust-region-ble": [
        "--dev",
        "--tracker", "optical-color",
        "--camera-url", IP_WEBCAM_URL,
        "--adjust-tracking-region",
        "--debug-camera",
        "--control-os-cursor",
        "--ble-address", BLE_ADDRESS,
    ],
    # Classic Bluetooth SPP variant -- same idea as the BLE presets above,
    # but for spidol/src/main.cpp's BluetoothSerial-based firmware
    # ("SpidolPintar_BT"), read back as a plain COM port.
    "pc-camera-serial": [
        "--dev",
        "--tracker", "optical-color",
        "--debug-camera",
        "--flip-camera",
        "--control-os-cursor",
        "--serial-touch-port", SERIAL_TOUCH_PORT,
    ],
}


def print_usage() -> None:
    print("Usage: python run.py <preset> [extra main.py args...]\n")
    print("Available presets:")
    for name, args in PRESETS.items():
        print(f"  {name:20s} python main.py {' '.join(args)}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_usage()
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    preset = sys.argv[1]
    if preset not in PRESETS:
        print(f"Unknown preset: {preset!r}\n")
        print_usage()
        sys.exit(1)

    extra_args = sys.argv[2:]
    cmd = [sys.executable, "main.py", *PRESETS[preset], *extra_args]
    print(f"$ {' '.join(cmd)}")
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
