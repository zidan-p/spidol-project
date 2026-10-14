// The stroke-buffer reducer: turns the incoming TRACK_UPDATE message stream
// into a renderable list of strokes. This is the seam that proves ink is
// driven purely by server telemetry (x/y/is_touching), never by native
// browser pointer events -- Canvas.jsx reads `strokes`/`activeStroke` only.
//
// Kept as plain data + pure functions (not a class) so it can live in a ref
// and be mutated imperatively by the 60fps message handler without going
// through React state/re-renders (see useSpidolSocket.js).
//
// Ticket 03 (drawing tools & UI chrome) adds tool/style awareness: every
// stroke is tagged with the tool and style (color/width/dash) that were
// selected when the stroke *started* (ToolIsland / PropertySidebar state,
// threaded in by the caller as `style`). Shape tools (line/rectangle/
// ellipse/arrow) collapse their point stream down to a start+end anchor
// pair; the text tool collapses to a single anchor plus an (initially
// empty) caption string filled in later by the UI; the eraser tool never
// produces a visible stroke of its own -- instead it removes whole
// existing strokes whose rendered path it passes through.
import { isPointNearStroke } from './strokeGeometry'

const SHAPE_TOOLS = new Set(['line', 'rectangle', 'ellipse', 'arrow'])

export function createStrokeBuffer() {
  return { strokes: [], activeStroke: null }
}

function startActiveStroke(style, point) {
  return { tool: style.tool, color: style.color, width: style.width, dash: style.dash, points: [point] }
}

function appendPoint(activeStroke, point) {
  if (SHAPE_TOOLS.has(activeStroke.tool)) {
    // Shape tools only ever care about the first (anchor) and most recent
    // (drag) point -- the live preview is "anchor -> current cursor".
    const anchor = activeStroke.points[0]
    return { ...activeStroke, points: [anchor, point] }
  }
  if (activeStroke.tool === 'text') {
    // Text placement is a single click; ignore any drag past the anchor.
    return activeStroke
  }
  const lastPoint = activeStroke.points[activeStroke.points.length - 1]
  if (lastPoint && distance(lastPoint, point) < MIN_POINT_DISTANCE) {
    // Within the jitter dead-zone -- treat as "still at the same point"
    // rather than appending a near-duplicate.
    return activeStroke
  }
  return { ...activeStroke, points: [...activeStroke.points, point] }
}

// Fixed hit-test radius in normalized (0..1) stroke-point units, independent
// of the eraser's on-screen pixel width -- the two live in different unit
// systems (points are normalized to canvas size, width is a CSS px value for
// rendering), so scaling one from the other would make the eraser's hit
// radius depend on the viewer's canvas size.
const ERASER_HIT_RADIUS = 0.035

// Minimum movement (same normalized 0..1 units as stroke points) a new
// freehand point must be from the stroke's last point to actually get
// appended. OpticalColorTracker's blob-centroid naturally jitters by a tiny
// amount even when the hand is genuinely still (paused at a corner) --
// without this dead-zone, that jitter draws a messy little radiating
// cluster at every pause instead of a clean point/corner.
const MIN_POINT_DISTANCE = 0.004

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

// The release (pen-up) TRACK_UPDATE's point is only meaningful for shape/
// text tools, where it supplies the final drag endpoint. For freehand
// tools (pen/eraser) it duplicates the last touching sample already in the
// point list, so it's dropped rather than appended again.
function applyReleasePoint(activeStroke, point) {
  if (SHAPE_TOOLS.has(activeStroke.tool)) {
    return appendPoint(activeStroke, point)
  }
  return activeStroke
}

function finalizeStroke(buffer, activeStroke) {
  if (activeStroke.tool === 'eraser') {
    const removed = []
    const kept = []
    for (const stroke of buffer.strokes) {
      const hit = activeStroke.points.some((p) => isPointNearStroke(stroke, p, ERASER_HIT_RADIUS))
      if (hit) {
        removed.push(stroke)
      } else {
        kept.push(stroke)
      }
    }
    if (removed.length === 0) {
      return { strokes: buffer.strokes, activeStroke: null, lastAction: null }
    }
    return { strokes: kept, activeStroke: null, lastAction: { type: 'erase', removed } }
  }

  const stroke =
    activeStroke.tool === 'text'
      ? { ...activeStroke, text: '' }
      : activeStroke

  const strokes = [...buffer.strokes, stroke]
  return { strokes, activeStroke: null, lastAction: { type: 'add', stroke } }
}

export function ingestTrackUpdate(buffer, message, style) {
  const point = { x: message.x, y: message.y }

  if (message.is_touching) {
    const activeStroke = buffer.activeStroke
      ? appendPoint(buffer.activeStroke, point)
      : startActiveStroke(style, point)
    return { strokes: buffer.strokes, activeStroke, lastAction: null }
  }

  if (buffer.activeStroke) {
    const finishedStroke = applyReleasePoint(buffer.activeStroke, point)
    return finalizeStroke(buffer, finishedStroke)
  }

  return { ...buffer, lastAction: null }
}
