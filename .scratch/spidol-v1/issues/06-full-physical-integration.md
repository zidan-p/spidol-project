# 06: Full physical integration & calibration pass

**What to build:** The complete physical demo described in the spec's key user journey — real Stylus, real camera, real projector, real whiteboard, all working together. This is primarily an integration and verification pass closing the loop between pieces built in parallel against shared interfaces (tickets 02 and 05), not new feature surface.

**Blocked by:** 02, 05

**Status:** ready-for-agent

- [ ] The assembled Stylus (firmware from 05) and camera rig (tracker from 02) are mounted and calibrated together via the Calibration Hotkey against a real projector + whiteboard setup
- [ ] Tracking Loss interpolation/pen-up thresholds are verified against real handwriting occlusion patterns, not just synthetic test conditions
- [ ] The BLE touch signal and camera-tracked position are verified to stay in sync (no visible lag or desync between press/release and ink position) under real use
- [ ] The full key user journey from the spec is demonstrated live: draw with the Stylus on the whiteboard, circle a formula, press the AI Trigger button, see the simulation widget spawn next to the formula, and adjust its sliders with the Stylus
- [ ] Any discrepancies found between the independently-built tracking (02) and touch/AI-trigger (05) pieces are logged and resolved
