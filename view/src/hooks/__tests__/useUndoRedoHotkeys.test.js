// Wires Ctrl+Z (undo) / Ctrl+Y (redo) global keyboard shortcuts to
// caller-supplied callbacks (SPEC.md 3.3, "Bottom-Left HUD"). Kept as a
// thin keyboard-binding hook, independent of strokeHistory.js, so the
// history data structure stays testable without a DOM and this hotkey
// wiring stays testable without real stroke data.
import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useUndoRedoHotkeys } from '../useUndoRedoHotkeys'

function keydown({ key, ctrlKey = false, metaKey = false }) {
  window.dispatchEvent(new KeyboardEvent('keydown', { key, ctrlKey, metaKey, bubbles: true }))
}

describe('useUndoRedoHotkeys', () => {
  it('calls onUndo for Ctrl+Z', () => {
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    renderHook(() => useUndoRedoHotkeys({ onUndo, onRedo }))

    act(() => keydown({ key: 'z', ctrlKey: true }))

    expect(onUndo).toHaveBeenCalledTimes(1)
    expect(onRedo).not.toHaveBeenCalled()
  })

  it('calls onRedo for Ctrl+Y', () => {
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    renderHook(() => useUndoRedoHotkeys({ onUndo, onRedo }))

    act(() => keydown({ key: 'y', ctrlKey: true }))

    expect(onRedo).toHaveBeenCalledTimes(1)
    expect(onUndo).not.toHaveBeenCalled()
  })

  it('also accepts Cmd+Z / Cmd+Shift+Z as undo/redo for macOS parity', () => {
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    renderHook(() => useUndoRedoHotkeys({ onUndo, onRedo }))

    act(() => keydown({ key: 'z', metaKey: true }))
    expect(onUndo).toHaveBeenCalledTimes(1)

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', metaKey: true, shiftKey: true, bubbles: true }))
    expect(onRedo).toHaveBeenCalledTimes(1)
  })

  it('ignores plain Z/Y without the modifier key', () => {
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    renderHook(() => useUndoRedoHotkeys({ onUndo, onRedo }))

    act(() => keydown({ key: 'z' }))
    act(() => keydown({ key: 'y' }))

    expect(onUndo).not.toHaveBeenCalled()
    expect(onRedo).not.toHaveBeenCalled()
  })

  it('removes its listener on unmount', () => {
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    const { unmount } = renderHook(() => useUndoRedoHotkeys({ onUndo, onRedo }))
    unmount()

    act(() => keydown({ key: 'z', ctrlKey: true }))

    expect(onUndo).not.toHaveBeenCalled()
  })
})
