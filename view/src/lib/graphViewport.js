// Pan/zoom math for the function_graph canvas (SimulationWidget.jsx):
// pure, testable transformations of a {xMin, xMax, yMin, yMax} viewport,
// independent of any DOM/canvas event wiring. The widget wires mouse wheel
// to zoomViewport and pointer drag to panViewport.
const MIN_SPAN = 1e-3
const MAX_SPAN = 1e6

function clampSpan(min, max) {
  const span = max - min
  if (span < MIN_SPAN) {
    const center = (min + max) / 2
    return [center - MIN_SPAN / 2, center + MIN_SPAN / 2]
  }
  if (span > MAX_SPAN) {
    const center = (min + max) / 2
    return [center - MAX_SPAN / 2, center + MAX_SPAN / 2]
  }
  return [min, max]
}

// Zooms the viewport by `factor` (< 1 zooms in, > 1 zooms out), keeping the
// data-space point (cx, cy) fixed in place -- the standard "zoom toward
// cursor" behavior, not just zooming toward the viewport's center.
export function zoomViewport({ xMin, xMax, yMin, yMax }, { cx, cy, factor }) {
  const newXSpan = (xMax - xMin) * factor
  const newYSpan = (yMax - yMin) * factor
  const xRatio = (cx - xMin) / (xMax - xMin)
  const yRatio = (cy - yMin) / (yMax - yMin)

  const [newXMin, newXMax] = clampSpan(cx - xRatio * newXSpan, cx - xRatio * newXSpan + newXSpan)
  const [newYMin, newYMax] = clampSpan(cy - yRatio * newYSpan, cy - yRatio * newYSpan + newYSpan)

  return { xMin: newXMin, xMax: newXMax, yMin: newYMin, yMax: newYMax }
}

// Pans the viewport by a data-space delta (dx, dy) -- dragging the graph
// right should reveal data to the left, hence subtracting here, with the
// sign flip applied by the caller converting a pixel delta to data space.
export function panViewport({ xMin, xMax, yMin, yMax }, { dx, dy }) {
  return { xMin: xMin + dx, xMax: xMax + dx, yMin: yMin + dy, yMax: yMax + dy }
}
