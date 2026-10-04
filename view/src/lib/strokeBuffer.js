// The stroke-buffer reducer: turns the incoming TRACK_UPDATE message stream
// into a renderable list of strokes. This is the seam that proves ink is
// driven purely by server telemetry (x/y/is_touching), never by native
// browser pointer events -- Canvas.jsx reads `strokes`/`activeStroke` only.
//
// Kept as plain data + pure functions (not a class) so it can live in a ref
// and be mutated imperatively by the 60fps message handler without going
// through React state/re-renders (see useSpidolSocket.js).

export function createStrokeBuffer() {
  return { strokes: [], activeStroke: null }
}

export function ingestTrackUpdate(buffer, message) {
  if (!message.is_detected) {
    // Tracking loss handling (interpolation / pen-up after ~150ms) is an
    // OpticalColorTracker-specific concern for a later ticket; the mouse
    // tracker always reports is_detected=true, so v1 just drops the point.
    return buffer
  }

  const point = { x: message.x, y: message.y }

  if (message.is_touching) {
    const activeStroke = buffer.activeStroke
      ? [...buffer.activeStroke, point]
      : [point]
    return { strokes: buffer.strokes, activeStroke }
  }

  if (buffer.activeStroke) {
    return { strokes: [...buffer.strokes, buffer.activeStroke], activeStroke: null }
  }

  return buffer
}
