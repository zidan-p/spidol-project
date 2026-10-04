// Kiosk Mode (GLOSSARY.md): true browser fullscreen, nothing else
// clickable, real OS cursor hidden (`cursor: none`). A defense-in-depth
// nicety, not a load-bearing mitigation -- see GLOSSARY.md. Distinct from
// Blackout Mode (useBlackoutMode.js); do not conflate the two.
//
// This hook only owns the Fullscreen API request/exit + tracking whether
// the document is still fullscreen (which can change outside our control,
// e.g. the user hitting the OS Escape key) -- actually hiding the cursor
// is a pure CSS concern the caller applies via the returned `isKiosk` flag
// (see index.css's `[data-kiosk='true']` rule).
import { useCallback, useEffect, useState } from 'react'

export function useKioskMode() {
  const [isKiosk, setIsKiosk] = useState(() => Boolean(document.fullscreenElement))

  useEffect(() => {
    const onFullscreenChange = () => setIsKiosk(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [])

  const enterKiosk = useCallback(async () => {
    await document.documentElement.requestFullscreen?.()
  }, [])

  const exitKiosk = useCallback(async () => {
    if (document.fullscreenElement) {
      await document.exitFullscreen?.()
    }
  }, [])

  const toggleKiosk = useCallback(async () => {
    if (document.fullscreenElement) {
      await exitKiosk()
    } else {
      await enterKiosk()
    }
  }, [enterKiosk, exitKiosk])

  return { isKiosk, enterKiosk, exitKiosk, toggleKiosk }
}
