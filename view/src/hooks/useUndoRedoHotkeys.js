// Ctrl+Z (undo) / Ctrl+Y (redo) global keyboard shortcuts (SPEC.md 3.3,
// "Bottom-Left HUD"). Cmd+Z / Cmd+Shift+Z are also accepted for macOS
// parity even though the demo rig targets Windows/Linux laptops. Deals
// only in keybindings -- the actual undo/redo data lives in
// strokeHistory.js, kept separate so each stays independently testable.
import { useEffect } from 'react'

export function useUndoRedoHotkeys({ onUndo, onRedo }) {
  useEffect(() => {
    const onKeyDown = (event) => {
      const mod = event.ctrlKey || event.metaKey
      if (!mod) return
      const key = event.key.toLowerCase()

      if (key === 'z' && event.shiftKey) {
        event.preventDefault()
        onRedo?.()
        return
      }
      if (key === 'z') {
        event.preventDefault()
        onUndo?.()
        return
      }
      if (key === 'y') {
        event.preventDefault()
        onRedo?.()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onUndo, onRedo])
}
