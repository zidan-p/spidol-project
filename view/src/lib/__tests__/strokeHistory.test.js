// Tests for the undo/redo history stack. This is the seam between
// strokeBuffer's `lastAction` ('add' | 'erase') and the Ctrl+Z/Ctrl+Y
// keyboard behavior described in ticket 03 -- the history module never
// touches the DOM or React state, it just answers "what does the committed
// strokes list look like after undoing/redoing the Nth action".
import { describe, expect, it } from 'vitest'
import { createHistory, commitAction, undo, redo, canUndo, canRedo } from '../strokeHistory'

function addAction(stroke) {
  return { type: 'add', stroke }
}

function eraseAction(removed) {
  return { type: 'erase', removed }
}

describe('createHistory', () => {
  it('starts with an empty stroke list and nothing to undo/redo', () => {
    const history = createHistory([])
    expect(history.strokes).toEqual([])
    expect(canUndo(history)).toBe(false)
    expect(canRedo(history)).toBe(false)
  })

  it('seeds from an initial strokes list', () => {
    const history = createHistory([{ id: 'a' }])
    expect(history.strokes).toEqual([{ id: 'a' }])
  })
})

describe('commitAction', () => {
  it('ignores a null action', () => {
    const history = createHistory([])
    const next = commitAction(history, null)
    expect(next).toBe(history)
  })

  it('records an add action onto the strokes list and clears the redo stack', () => {
    const history = createHistory([])
    const next = commitAction(history, addAction({ id: 'a' }))
    expect(next.strokes).toEqual([{ id: 'a' }])
    expect(canUndo(next)).toBe(true)
    expect(canRedo(next)).toBe(false)
  })

  it('records an erase action by removing the erased strokes from the list', () => {
    const strokeA = { id: 'a' }
    const history = commitAction(createHistory([]), addAction(strokeA))
    const next = commitAction(history, eraseAction([strokeA]))
    expect(next.strokes).toEqual([])
    expect(canUndo(next)).toBe(true)
  })
})

describe('undo / redo', () => {
  it('undo reverses the most recent add', () => {
    let history = createHistory([])
    history = commitAction(history, addAction({ id: 'a' }))
    history = commitAction(history, addAction({ id: 'b' }))

    history = undo(history)
    expect(history.strokes).toEqual([{ id: 'a' }])
    expect(canRedo(history)).toBe(true)
  })

  it('undo reverses the most recent erase by restoring the removed strokes', () => {
    const strokeA = { id: 'a' }
    const strokeB = { id: 'b' }
    let history = createHistory([])
    history = commitAction(history, addAction(strokeA))
    history = commitAction(history, addAction(strokeB))
    history = commitAction(history, eraseAction([strokeA]))
    expect(history.strokes).toEqual([strokeB])

    history = undo(history)
    expect(history.strokes).toEqual([strokeB, strokeA])
  })

  it('redo re-applies an undone action', () => {
    let history = createHistory([])
    history = commitAction(history, addAction({ id: 'a' }))
    history = undo(history)
    expect(history.strokes).toEqual([])

    history = redo(history)
    expect(history.strokes).toEqual([{ id: 'a' }])
    expect(canRedo(history)).toBe(false)
  })

  it('committing a new action after an undo discards the stale redo branch', () => {
    let history = createHistory([])
    history = commitAction(history, addAction({ id: 'a' }))
    history = commitAction(history, addAction({ id: 'b' }))
    history = undo(history)
    history = commitAction(history, addAction({ id: 'c' }))

    expect(history.strokes).toEqual([{ id: 'a' }, { id: 'c' }])
    expect(canRedo(history)).toBe(false)
  })

  it('undo is a no-op when there is nothing to undo', () => {
    const history = createHistory([{ id: 'a' }])
    expect(undo(history)).toBe(history)
  })

  it('redo is a no-op when there is nothing to redo', () => {
    const history = createHistory([{ id: 'a' }])
    expect(redo(history)).toBe(history)
  })
})
