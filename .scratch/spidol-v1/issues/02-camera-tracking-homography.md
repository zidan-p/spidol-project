# 02: Camera-based pen tracking with homography calibration

**What to build:** Replace the mouse-driven position source with a real camera tracking the Pen Tip, correctly mapped onto the projected canvas regardless of camera placement angle, and resilient to brief tracking loss during normal handwriting.

**Blocked by:** 01

**Status:** code-complete, hardware-unverified (merged to integration/spidol-v1 at 691aab6)

- [x] `OpticalColorTracker` implemented against the existing `BasePositionTracker` interface — code-verified via synthetic-frame tests. The capture pipeline is now wired (`hal/image_source.py`'s `CameraImageSource`, a `cv2.VideoCapture(camera_index)` wrapper, selected by `main.py --tracker=optical-color` and fed into both the telemetry loop and the AI Trigger crop). NOT verified: an actual phone connected via RemoteCam over USB enumerating correctly as camera index N on the demo machine — that hardware pairing is still unchecked, only the generic `cv2.VideoCapture` seam is code-verified (with a fake capture object, no real camera).
- [x] 4-point homography calibration (`cv2.findHomography` / `cv2.perspectiveTransform`) maps camera-space coordinates to canvas-space coordinates — code-verified
- [x] A Calibration Hotkey re-runs the 4-point calibration flow on demand (manual, operator-triggered — no automatic drift detection) — `HomographyCalibrator.recalibrate` code-verified; now wired end-to-end: a "C" keydown in `view/src/App.jsx` sends `{"type": "CALIBRATE"}` over the WebSocket, and `server_app.py`'s handler calls `homography.recalibrate(...)`. The point-collection UX is still a dev-mode stub (a fixed identity 4-corner correspondence, not real click-to-pick corners) — real point-picking UI remains a known gap.
- [x] Tracking Loss under ~150ms (e.g. hand/wrist briefly occluding the Pen Tip) is bridged by linear interpolation between the last-known and reacquired points — code-verified via `TrackingLossBridge`, now wired into the live telemetry loop (`server_app.py`'s `_telemetry_loop`, constructed in `main.py`'s `make_camera_resources` when `--tracker=optical-color` is selected)
- [x] Tracking Loss beyond ~150ms ends the current stroke (pen-up) rather than interpolating across a longer gap — code-verified
- [ ] **Needs real hardware to verify**: a colored pen tip moved in front of the camera draws correctly aligned ink on the canvas, verified against the homography-mapped projector output. Also unverified: the default HSV color range against a real Pen Tip under real lighting, and whether 150ms "feels" right against real hand-occlusion timing.
