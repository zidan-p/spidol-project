// Geometry helpers shared by stroke rendering (Canvas.jsx) and eraser
// hit-testing (strokeBuffer.js). Kept tool-aware but rendering-agnostic: it
// only computes point/segment geometry, never touches a canvas context.

const ELLIPSE_SAMPLES = 24

function bbox(a, b) {
  return {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    w: Math.abs(b.x - a.x),
    h: Math.abs(b.y - a.y),
  }
}

// Returns the ordered list of segments ([start, end] point pairs) that make
// up a stroke's visible path, regardless of tool. This is the single place
// that knows how each tool's anchor points expand into an actual shape, so
// both rendering and eraser hit-testing stay consistent.
export function strokeSegments(stroke) {
  const { tool, points } = stroke

  if (points.length === 0) return []

  switch (tool) {
    case 'line':
    case 'arrow': {
      if (points.length < 2) return []
      return [[points[0], points[1]]]
    }
    case 'rectangle': {
      if (points.length < 2) return []
      const { x, y, w, h } = bbox(points[0], points[1])
      const tl = { x, y }
      const tr = { x: x + w, y }
      const br = { x: x + w, y: y + h }
      const bl = { x, y: y + h }
      return [
        [tl, tr],
        [tr, br],
        [br, bl],
        [bl, tl],
      ]
    }
    case 'ellipse': {
      if (points.length < 2) return []
      const { x, y, w, h } = bbox(points[0], points[1])
      const cx = x + w / 2
      const cy = y + h / 2
      const rx = w / 2
      const ry = h / 2
      const perimeter = []
      for (let i = 0; i <= ELLIPSE_SAMPLES; i += 1) {
        const angle = (i / ELLIPSE_SAMPLES) * Math.PI * 2
        perimeter.push({ x: cx + rx * Math.cos(angle), y: cy + ry * Math.sin(angle) })
      }
      const segments = []
      for (let i = 0; i < perimeter.length - 1; i += 1) {
        segments.push([perimeter[i], perimeter[i + 1]])
      }
      return segments
    }
    case 'text': {
      return [[points[0], points[0]]]
    }
    case 'pen':
    case 'eraser':
    default: {
      if (points.length === 1) return [[points[0], points[0]]]
      const segments = []
      for (let i = 0; i < points.length - 1; i += 1) {
        segments.push([points[i], points[i + 1]])
      }
      return segments
    }
  }
}

function distanceToSegment(point, a, b) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const lengthSquared = dx * dx + dy * dy

  if (lengthSquared === 0) {
    const ddx = point.x - a.x
    const ddy = point.y - a.y
    return Math.sqrt(ddx * ddx + ddy * ddy)
  }

  let t = ((point.x - a.x) * dx + (point.y - a.y) * dy) / lengthSquared
  t = Math.max(0, Math.min(1, t))

  const closest = { x: a.x + t * dx, y: a.y + t * dy }
  const ddx = point.x - closest.x
  const ddy = point.y - closest.y
  return Math.sqrt(ddx * ddx + ddy * ddy)
}

// True if `point` comes within `radius` (in the same normalized 0..1 units
// as stroke points) of any segment of the stroke's rendered path.
export function isPointNearStroke(stroke, point, radius) {
  const segments = strokeSegments(stroke)
  return segments.some(([a, b]) => distanceToSegment(point, a, b) <= radius)
}
