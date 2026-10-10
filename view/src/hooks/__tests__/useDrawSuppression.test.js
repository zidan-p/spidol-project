// Tests for useDrawSuppression: a gesture (pointerdown -> pointerup) that
// starts on something other than the tracked target element must suppress
// drawing for its duration; a gesture starting on the target itself must
// not.
import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useDrawSuppression } from '../useDrawSuppression'

function firePointerDown(target) {
  const event = new Event('pointerdown', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'target', { value: target, enumerable: true })
  window.dispatchEvent(event)
}

function firePointerUp() {
  window.dispatchEvent(new Event('pointerup', { bubbles: true, cancelable: true }))
}

describe('useDrawSuppression', () => {
  let canvasEl
  let otherEl

  afterEach(() => {
    canvasEl?.remove()
    otherEl?.remove()
  })

  function setup() {
    canvasEl = document.createElement('canvas')
    otherEl = document.createElement('input')
    document.body.append(canvasEl, otherEl)
    const targetRef = { current: canvasEl }
    const { result } = renderHook(() => useDrawSuppression(targetRef))
    return result
  }

  it('starts unsuppressed', () => {
    const result = setup()
    expect(result.current.current).toBe(false)
  })

  it('suppresses drawing when a gesture starts on a non-target element', () => {
    const result = setup()

    firePointerDown(otherEl)

    expect(result.current.current).toBe(true)
  })

  it('does not suppress drawing when a gesture starts on the target element itself', () => {
    const result = setup()

    firePointerDown(canvasEl)

    expect(result.current.current).toBe(false)
  })

  it('un-suppresses once the gesture ends (pointerup), regardless of where it started', () => {
    const result = setup()

    firePointerDown(otherEl)
    expect(result.current.current).toBe(true)

    firePointerUp()
    expect(result.current.current).toBe(false)
  })
})
