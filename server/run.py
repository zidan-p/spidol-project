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
"""
import subprocess
import sys

IP_WEBCAM_URL = "http://127.0.0.1:8081/video"
# Not 8080 -- already occupied by an unrelated local process
# (whatsapp-bridge.exe) on this machine, which silently binds to
# 127.0.0.1 only and would make asyncio.start_server fail to bind at all.
WIFI_TOUCH_PORT = "8090"

PRESETS = {
    "dev": [
        "--dev",
    ],
    "pc-camera": [
        "--dev",
        "--tracker", "optical-color",
        "--debug-camera",
        "--flip-camera",
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
