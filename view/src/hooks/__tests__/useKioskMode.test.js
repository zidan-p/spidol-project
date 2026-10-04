// Kiosk Mode (GLOSSARY.md): true browser fullscreen with the real OS
// cursor hidden (`cursor: none`), nothing else clickable. Distinct from
// Blackout Mode (useBlackoutMode.js) -- see GLOSSARY.md note not to
// conflate the two. This hook owns requesting/exiting the Fullscreen API
// and tracking whether the document is currently fullscreen; the
// cursor-none styling is applied by the caller via the returned boolean
// (as a CSS class/data-attribute), kept here only as documented intent.
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useKioskMode } from '../useKioskMode'

beforeEach(() => {
  document.documentElement.requestFullscreen = vi.fn(() => {
    document.__fullscreenElement = document.documentElement
    document.dispatchEvent(new Event('fullscreenchange'))
    return Promise.resolve()
  })
  document.exitFullscreen = vi.fn(() => {
    document.__fullscreenElement = null
    document.dispatchEvent(new Event('fullscreenchange'))
    return Promise.resolve()
  })
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    get: () => document.__fullscreenElement ?? null,
  })
})

afterEach(() => {
  document.__fullscreenElement = null
  vi.restoreAllMocks()
})

describe('useKioskMode', () => {
  it('starts out of kiosk mode', () => {
    const { result } = renderHook(() => useKioskMode())
    expect(result.current.isKiosk).toBe(false)
  })

  it('requests fullscreen and flips isKiosk on enterKiosk', async () => {
    const { result } = renderHook(() => useKioskMode())
    await act(async () => {
      await result.current.enterKiosk()
    })
    expect(document.documentElement.requestFullscreen).toHaveBeenCalled()
    expect(result.current.isKiosk).toBe(true)
  })

  it('exits fullscreen and flips isKiosk off on exitKiosk', async () => {
    const { result } = renderHook(() => useKioskMode())
    await act(async () => {
      await result.current.enterKiosk()
    })
    await act(async () => {
      await result.current.exitKiosk()
    })
    expect(document.exitFullscreen).toHaveBeenCalled()
    expect(result.current.isKiosk).toBe(false)
  })

  it('tracks isKiosk going false if fullscreen is exited some other way (e.g. the OS Escape key)', async () => {
    const { result } = renderHook(() => useKioskMode())
    await act(async () => {
      await result.current.enterKiosk()
    })
    expect(result.current.isKiosk).toBe(true)

    act(() => {
      document.__fullscreenElement = null
      document.dispatchEvent(new Event('fullscreenchange'))
    })

    expect(result.current.isKiosk).toBe(false)
  })

  it('toggleKiosk flips between enter and exit', async () => {
    const { result } = renderHook(() => useKioskMode())
    await act(async () => {
      await result.current.toggleKiosk()
    })
    expect(result.current.isKiosk).toBe(true)

    await act(async () => {
      await result.current.toggleKiosk()
    })
    expect(result.current.isKiosk).toBe(false)
  })
})
