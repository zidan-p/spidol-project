# AI Trigger fires only on explicit body-button press

The original spec contradicted itself: Section 3.1 wired the body button to "AI query / right-click trigger," while Section 3.2.D described the AI pipeline firing automatically whenever any closed geometric loop was drawn and the pen lifted. The automatic version has an obvious false-positive problem — the toolbar includes an Ellipse/Rectangle tool, so an intentionally-drawn circle or box (e.g. a diagram, not a circled formula) would misfire the pipeline every time.

We decided the AI Trigger is the explicit body-button press, full stop. Closed-contour detection is retained only as an ROI-selection helper (pick the last-closed contour if one exists), not as an autonomous trigger. The submitted region (the AI Trigger Region) is every stroke drawn since the last AI Trigger or canvas clear — not a time window — so a pause mid-formula never clips it.
