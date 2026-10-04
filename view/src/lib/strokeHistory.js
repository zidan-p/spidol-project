// Undo/redo history stack (Ctrl+Z / Ctrl+Y, SPEC.md 3.3 "Bottom-Left HUD").
//
// Wraps strokeBuffer's `lastAction` ('add' | 'erase') into a linear
// undo/redo log. Each entry is the action as reported by
// `ingestTrackUpdate`, so undoing an 'add' removes that one stroke and
// undoing an 'erase' restores every stroke that gesture removed (a single
// eraser drag that swept up several strokes undoes as one step, matching
// the user's mental model of "undo my last gesture").
//
// Kept as plain data + pure functions, mirroring strokeBuffer.js, so it can
// live in a ref/plain variable and be driven imperatively from Canvas.jsx's
// per-frame loop without forcing a React re-render on every point.

export function createHistory(initialStrokes = []) {
  return { strokes: initialStrokes, undoStack: [], redoStack: [] }
}

export function canUndo(history) {
  return history.undoStack.length > 0
}

export function canRedo(history) {
  return history.redoStack.length > 0
}

function applyForward(strokes, action) {
  if (action.type === 'add') {
    return [...strokes, action.stroke]
  }
  // 'erase'
  const removedIds = new Set(action.removed)
  return strokes.filter((stroke) => !removedIds.has(stroke))
}

function applyBackward(strokes, action) {
  if (action.type === 'add') {
    return strokes.filter((stroke) => stroke !== action.stroke)
  }
  // 'erase': restore the removed strokes. Order isn't load-bearing for
  // rendering (strokes don't z-fight), so appending them back is enough.
  return [...strokes, ...action.removed]
}

export function commitAction(history, action) {
  if (!action) return history
  return {
    strokes: applyForward(history.strokes, action),
    undoStack: [...history.undoStack, action],
    redoStack: [],
  }
}

export function undo(history) {
  if (!canUndo(history)) return history
  const action = history.undoStack[history.undoStack.length - 1]
  return {
    strokes: applyBackward(history.strokes, action),
    undoStack: history.undoStack.slice(0, -1),
    redoStack: [...history.redoStack, action],
  }
}

export function redo(history) {
  if (!canRedo(history)) return history
  const action = history.redoStack[history.redoStack.length - 1]
  return {
    strokes: applyForward(history.strokes, action),
    undoStack: [...history.undoStack, action],
    redoStack: history.redoStack.slice(0, -1),
  }
}
