// Mouse-fallback dev mode's touch signal comes from a GLOBAL OS-level mouse
// listener (pynput, server/main.py's make_click_handler): any left-click
// anywhere on screen -- including this app's own sliders, buttons, or
// color swatches -- sets is_touching=true and reports the real OS cursor
// position, which Canvas.jsx would otherwise render as ink under whatever
// UI chrome the user actually meant to interact with.
//
// This hook uses the browser's own `pointerdown` event (which fires for the
// same physical mouse-button press pynput also sees) to detect whether the
// current press-to-release gesture started on the drawing canvas itself or
// on some other element -- if the latter, Canvas.jsx suppresses drawing for
// that gesture's duration, so dragging a slider never leaves a stroke
// behind it. A gesture that starts on the canvas keeps drawing normally
// even if the cursor later wanders over other UI chrome mid-stroke.
import { useEffect, useRef } from 'react'

export function useDrawSuppression(targetRef) {
  const suppressedRef = useRef(false)

  useEffect(() => {
    const onPointerDown = (event) => {
      suppressedRef.current = event.target !== targetRef.current
    }
    const onPointerUp = () => {
      suppressedRef.current = false
    }
    window.addEventListener('pointerdown', onPointerDown, true)
    window.addEventListener('pointerup', onPointerUp, true)
    return () => {
      window.removeEventListener('pointerdown', onPointerDown, true)
      window.removeEventListener('pointerup', onPointerUp, true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return suppressedRef
}
