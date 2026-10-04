# 02: Camera-based pen tracking with homography calibration

**What to build:** Replace the mouse-driven position source with a real camera tracking the Pen Tip, correctly mapped onto the projected canvas regardless of camera placement angle, and resilient to brief tracking loss during normal handwriting.

**Blocked by:** 01

**Status:** code-complete, hardware-unverified (merged to integration/spidol-v1 at 691aab6)

- [x] `OpticalColorTracker` implemented against the existing `BasePositionTracker` interface — code-verified via synthetic-frame tests. NOT verified: actually reading frames from a phone connected via RemoteCam over USB (no capture pipeline wired up; tracker consumes whatever frame it's handed, which is the correct seam, but the RemoteCam integration itself is unchecked)
- [x] 4-point homography calibration (`cv2.findHomography` / `cv2.perspectiveTransform`) maps camera-space coordinates to canvas-space coordinates — code-verified
- [x] A Calibration Hotkey re-runs the 4-point calibration flow on demand (manual, operator-triggered — no automatic drift detection) — `HomographyCalibrator.recalibrate` code-verified; no UI/keybinding wired to call it yet
- [x] Tracking Loss under ~150ms (e.g. hand/wrist briefly occluding the Pen Tip) is bridged by linear interpolation between the last-known and reacquired points — code-verified via `TrackingLossBridge`, not yet wired into `main.py`'s live telemetry loop
- [x] Tracking Loss beyond ~150ms ends the current stroke (pen-up) rather than interpolating across a longer gap — code-verified
- [ ] **Needs real hardware to verify**: a colored pen tip moved in front of the camera draws correctly aligned ink on the canvas, verified against the homography-mapped projector output. Also unverified: the default HSV color range against a real Pen Tip under real lighting, and whether 150ms "feels" right against real hand-occlusion timing.
