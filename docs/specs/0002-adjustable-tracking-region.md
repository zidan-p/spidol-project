# Adjustable Tracking Region

**Status:** ready-for-agent (manually applied — no issue tracker configured in this session; see note at bottom)

## Problem Statement

`OpticalColorTracker` always searches the *entire* camera frame for the blue Pen Tip. In practice the camera sees more than just the whiteboard — other blue objects in the room (clothing, furniture, equipment) can produce false-positive detections that hijack the reported Pen Tip position. There's also no way today to tell the system which part of the frame actually corresponds to the whiteboard, and the right answer changes between venues/sessions since the camera's position, angle, and even the physical device attached (a laptop webcam during dev, a different USB webcam or RemoteCam-exposed phone in production) aren't fixed.

## Solution

A new one-shot interactive setup step, invoked via `--adjust-tracking-region` alongside `--tracker optical-color`, pops open a native OpenCV window showing the live camera feed. The operator drags a rectangle over the area that should actually be searched for the Pen Tip (typically the whiteboard's bounds), confirms it, and the window closes — then the same process continues straight into the normal server startup, with `OpticalColorTracker`'s search restricted to inside that rectangle for the rest of the run. Nothing is persisted to disk; the operator redoes this once per session if needed, matching the existing Calibration Hotkey's "once per session" pattern (GLOSSARY.md).

## User Stories

1. As an operator, I want to pass a single flag that opens a live camera preview before the server starts, so that I can set up the tracked area as part of the same command I use to launch the server.
2. As an operator, I want to see the live camera feed (not a single frozen frame) while I'm choosing the region, so that I can confirm the whiteboard is actually in view and correctly framed as I drag.
3. As an operator, I want to click-and-drag a rectangle directly over the live preview, so that selecting the tracked area feels like a familiar crop-tool gesture.
4. As an operator, I want to see the rectangle I'm dragging overlaid live on top of the moving camera feed, so that I can visually verify it lines up with the whiteboard's actual edges before committing.
5. As an operator, I want to press a single key (Enter/Space) to confirm my selection, so that locking in the region doesn't require any UI beyond mouse and keyboard.
6. As an operator, I want to press a different key (Esc) to discard a selection and redraw it, so that I can correct a mis-drawn rectangle without restarting the whole process.
7. As an operator, I want the preview window to close automatically once I confirm, so that the actual demo run starts clean with no debug window left on screen.
8. As an operator, I want tracking to default to the full camera frame if I don't adjust anything, so that confirming without touching the rectangle behaves exactly like today (no surprise regressions).
9. As an operator, I want anything outside my chosen rectangle to be completely invisible to the Pen Tip detector, so that a stray blue object elsewhere in the room never hijacks the reported position.
10. As an operator, I want this to work with whatever camera device is currently configured (`--camera-index`, a USB webcam, or a RemoteCam-exposed phone), so that I don't need different tooling for dev testing versus an actual production venue.
11. As an operator, I want this setup step to be completely independent of `--debug-camera`, so that a real demo run never shows a developer debug overlay unless I explicitly ask for one.
12. As an operator, I want to still be able to combine `--adjust-tracking-region` with `--debug-camera` if I want, so that I can keep troubleshooting the live feed after the region is set, when I actually need to.
13. As an operator, I want the chosen region to only live in memory for that run (never written to disk), so that each session starts from a clean, explicit choice rather than silently reusing a stale prior configuration.
14. As an operator, I want to see the applied region logged to the console once I've confirmed it, so that I have visibility into exactly what was set without needing to inspect code.
15. As an operator, I want a sensible fallback (full frame, clearly logged) if I close the window without confirming, so that an aborted setup never crashes the server or leaves it in an undefined state.
16. As an operator, I want this feature to have no effect at all when using `--tracker mouse` (the default dev/testing mode), so that it doesn't interfere with existing mouse-fallback workflows.

## Implementation Decisions

- New CLI flag `--adjust-tracking-region`, usable together with `--tracker optical-color`; a no-op with any other tracker.
- `OpticalColorTracker` gains an optional search-region constraint. When set, the `cv2.inRange`/`cv2.findContours` search operates only on that sub-array of the frame before the centroid is computed; left unset, behavior is identical to today (full-frame search) — a purely additive, backward-compatible change.
- A new pure, synchronous region-selection state machine holds the interactive logic: mouse-down/move/up handlers track a provisional rectangle while dragging, and a key handler distinguishes confirm (Enter/Space, finalizing the rectangle into `region`) from discard (Esc, clearing the provisional rectangle so the operator can redraw). This class has no `cv2` dependency of its own.
- A thin real-I/O wrapper owns the actual `cv2.namedWindow`/`cv2.setMouseCallback`/`cv2.imshow`/`cv2.waitKey` loop: it reads live frames from the configured camera source, forwards raw mouse/key events into the state machine, draws the live feed plus the current provisional/confirmed rectangle each frame, and exits once the state machine reports either a confirmed region or that the window was closed unconfirmed (in which case it falls back to the full-frame default, with that fallback explicitly logged).
- Once resolved (confirmed or defaulted), `main.py`'s startup flow applies the chosen region to the `OpticalColorTracker` instance before proceeding into the existing `run()` flow — all within the same process and invocation, no second command needed.
- No persistence layer of any kind (no config file, no environment variable) — the region exists only in the running process's memory, matching the Calibration Hotkey's documented "redo once per session" precedent.
- `--debug-camera` remains fully independent and unaffected: combinable with `--adjust-tracking-region`, but neither implies the other.
- The resolved region (confirmed or defaulted) is logged at INFO level, consistent with the existing `logging.basicConfig` setup and `WifiTouchProvider`'s connect/disconnect logging precedent.
- `HomographyCalibrator`/the Calibration Hotkey are untouched — restricting the *search* area and dewarping *detected coordinates* are independent, non-interacting mechanisms that happen to both involve a camera-frame overlay.

## Testing Decisions

Good tests here assert on externally observable behavior — what `OpticalColorTracker.get_position()` returns for a given frame and configured region, and what the region-selection state machine's resolved `region` is after a given sequence of synthetic mouse/key events — never on internal OpenCV calls or the real frame-capture loop.

- **`OpticalColorTracker` seam** (existing, extended; prior art: `tests/test_optical_color_tracker.py`, which already feeds synthetic numpy BGR frames directly into the public method with no real camera). New cases: a blob outside the configured region returns `is_detected=False`; one inside it detects normally; the existing full-frame tests continue to cover the no-region-configured default.
- **Region-selection state machine seam** (new, minimal; prior art: `vision/debug_preview.py`'s injectable `show_frame` callback, `hal/providers.py`'s `BleTouchProvider` injectable `client_factory` — both let tests drive real logic without real I/O). Unit tests drive the state machine directly via synthetic mouse-down/move/up coordinates and key codes, asserting the resulting provisional/confirmed region, the confirm/discard/redraw transitions, and the fallback-to-full-frame behavior when no confirmation occurs — no real `cv2` window or camera involved.
- The thin real-I/O wrapper (`cv2.namedWindow`/`imshow`/`waitKey`/`setMouseCallback`) is not unit tested, same as `DebugPreviewTracker`'s real `cv2.imshow` call today — verified manually, same as the rest of the camera-tracking pipeline.
- `main.py`'s CLI wiring (`--adjust-tracking-region` recognized; only takes effect combined with `--tracker optical-color`) follows the existing `tests/test_main.py` pattern of asserting directly on `parse_args`/`make_tracker` return values.

## Out of Scope

- 4-point perspective/homography correction for an angled camera — a separate, already-partially-built feature (`HomographyCalibrator`); untouched by this work.
- Persisting the chosen region to disk/config across server restarts.
- Live/mid-session re-adjustment while people are actively drawing — this is a setup-time-only action.
- Any network/IP-camera capture mechanism beyond the existing device-index-based `cv2.VideoCapture` (RemoteCam, USB webcams) — "another camera in production" means only a different `--camera-index`/device, already supported today.
- A browser-based version of this UI — this stays a native OpenCV window used by the operator at the physical rig.
- Multiple simultaneous tracked regions, or non-rectangular region shapes.

## Further Notes

- This spec reflects the grilling session that preceded it in this conversation (a 10-question round covering where the UI lives, rectangle vs. perspective correction, persistence, timing, camera selection, and the one-shot/combined-command workflow) — no separate interview was conducted to produce this document.
- See [GLOSSARY.md](../../GLOSSARY.md) for canonical terminology (Pen Tip, OpticalColorTracker, Calibration Hotkey) and [docs/adr/](../adr/) for related architectural decisions.
- **No issue tracker or triage label vocabulary is configured in this session.** Per this skill's instructions, publishing to a tracker and applying the `ready-for-agent` label requires `/setup-matt-pocock-skills`, which isn't installed here. This spec has been written to `docs/specs/0002-adjustable-tracking-region.md` instead; move/paste it into the real tracker once that's set up.
