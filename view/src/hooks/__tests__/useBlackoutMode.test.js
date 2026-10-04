// Blackout Mode (SPEC.md 3.3 / GLOSSARY.md): the visual pitch-black
// rendering state toggled by the `F` hotkey, distinct from Kiosk Mode
// (fullscreen + cursor:none, a separate hook). This hook owns only the
// on/off state and the keyboard listener; hiding chrome / forcing
// background color is the caller's (App.jsx's) concern via the returned
// boolean.
import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useBlackoutMode } from '../useBlackoutMode'

function pressKey(key) {
  window.dispatchEvent(new KeyboardEvent('keydown', { key }))
}

describe('useBlackoutMode', () => {
  afterEach(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
  })

  it('starts out of blackout mode', () => {
    const { result } = renderHook(() => useBlackoutMode())
    expect(result.current.isBlackout).toBe(false)
  })

  it('toggles on when F is pressed', () => {
    const { result } = renderHook(() => useBlackoutMode())
    act(() => pressKey('f'))
    expect(result.current.isBlackout).toBe(true)
  })

  it('toggles back off on a second F press', () => {
    const { result } = renderHook(() => useBlackoutMode())
    act(() => pressKey('f'))
    act(() => pressKey('f'))
    expect(result.current.isBlackout).toBe(false)
  })

  it('is case-insensitive to the F key', () => {
    const { result } = renderHook(() => useBlackoutMode())
    act(() => pressKey('F'))
    expect(result.current.isBlackout).toBe(true)
  })

  it('exposes a manual setter for UI-driven toggling (e.g. a chrome button)', () => {
    const { result } = renderHook(() => useBlackoutMode())
    act(() => result.current.setIsBlackout(true))
    expect(result.current.isBlackout).toBe(true)
  })

  it('ignores unrelated keys', () => {
    const { result } = renderHook(() => useBlackoutMode())
    act(() => pressKey('g'))
    expect(result.current.isBlackout).toBe(false)
  })

  it('removes its listener on unmount', () => {
    const { result, unmount } = renderHook(() => useBlackoutMode())
    unmount()
    act(() => pressKey('f'))
    expect(result.current.isBlackout).toBe(false)
  })

  it('does not toggle while the user is typing into a text field (e.g. the Text-tool caption box)', () => {
    const { result } = renderHook(() => useBlackoutMode())
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    act(() => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', bubbles: true }))
    })

    expect(result.current.isBlackout).toBe(false)
    document.body.removeChild(input)
  })
})
