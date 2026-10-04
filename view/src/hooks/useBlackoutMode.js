// Blackout Mode (hotkey `F`): the visual pitch-black rendering state. This
// is distinct from Kiosk Mode (useKioskMode.js) -- see GLOSSARY.md, the two
// are easy to conflate but address different concerns (visual background
// vs. input-safety/fullscreen).
import { useEffect, useState } from 'react'

function isTypingTarget(target) {
  if (!target) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable
}

export function useBlackoutMode() {
  const [isBlackout, setIsBlackout] = useState(false)

  useEffect(() => {
    const onKeyDown = (event) => {
      if (isTypingTarget(event.target)) return
      if (event.key.toLowerCase() !== 'f') return
      setIsBlackout((prev) => !prev)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return { isBlackout, setIsBlackout }
}
