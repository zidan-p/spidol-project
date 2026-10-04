# v1 ships single-stylus, color-tracker-only, with no ArUco driver

The HAL architecture names `ArucoMarkerTracker` and a `device_id` field that implies multi-stylus collaborative tracking, both of which read as core features. Given the 11-day runway to the Oct 15-16, 2026 deadline for a 3-person team building firmware, BLE pairing, CV tracking, an AI pipeline, and a frontend simultaneously, we decided to explicitly descope both for v1.

v1 ships only `OpticalColorTracker` plus the `SystemMouseFallbackTracker` already in the HAL design, and is hard-coded for exactly one stylus end-to-end. `device_id` stays in the WebSocket schema as a forward-looking affordance, unused by v1 logic. The must-work-live bar is pen tracking + drawing + the closed-loop AI formula capture; anything multi-stylus is acceptable as pre-recorded video backup only, and `ArucoMarkerTracker` is cut entirely rather than half-built.
