# 02: Camera-based pen tracking with homography calibration

**What to build:** Replace the mouse-driven position source with a real camera tracking the Pen Tip, correctly mapped onto the projected canvas regardless of camera placement angle, and resilient to brief tracking loss during normal handwriting.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `OpticalColorTracker` implemented against the existing `BasePositionTracker` interface, reading frames from a phone connected via RemoteCam over USB
- [ ] 4-point homography calibration (`cv2.findHomography` / `cv2.perspectiveTransform`) maps camera-space coordinates to canvas-space coordinates
- [ ] A Calibration Hotkey re-runs the 4-point calibration flow on demand (manual, operator-triggered — no automatic drift detection)
- [ ] Tracking Loss under ~150ms (e.g. hand/wrist briefly occluding the Pen Tip) is bridged by linear interpolation between the last-known and reacquired points, producing a continuous-looking stroke
- [ ] Tracking Loss beyond ~150ms ends the current stroke (pen-up) rather than interpolating across a longer gap
- [ ] A colored pen tip moved in front of the camera draws correctly aligned ink on the canvas, verified against the homography-mapped projector output
