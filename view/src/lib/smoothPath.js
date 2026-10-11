// Traces `points` ([x, y] pairs, already in the target coordinate space) as
// a smooth curve via canvas path commands, instead of straight lineTo
// segments between raw samples -- the classic "quadratic curve through
// midpoints" technique: each point becomes a control point pulling the
// curve toward it, while the curve itself passes through the midpoint of
// each consecutive pair, so corners get rounded rather than kinked. Shared
// by the function_graph curve (SimulationWidget.jsx) and freehand pen ink
// (Canvas.jsx) -- both want the same cosmetic smoothing over otherwise
// noisy/segmented sample points. `closed` additionally smooths the
// wrap-around segment (a circle, or a pen stroke that loops back near its
// start) instead of leaving a sharp seam.
export function traceSmoothPath(ctx, points, closed = false) {
  const n = points.length
  if (n === 0) return
  if (n === 1) {
    ctx.moveTo(points[0][0], points[0][1])
    return
  }
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]

  if (closed) {
    ctx.moveTo(...mid(points[n - 1], points[0]))
    for (let i = 0; i < n; i += 1) {
      const next = points[(i + 1) % n]
      ctx.quadraticCurveTo(...points[i], ...mid(points[i], next))
    }
  } else {
    ctx.moveTo(...points[0])
    for (let i = 1; i < n - 1; i += 1) {
      ctx.quadraticCurveTo(...points[i], ...mid(points[i], points[i + 1]))
    }
    ctx.lineTo(...points[n - 1])
  }
}
