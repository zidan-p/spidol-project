// Tests for useSpidolSocket: the WebSocket client hook. TRACK_UPDATE
// messages must land in a ref (no re-render per message, since they arrive
// at 60fps) while connection-state changes go through React state (low
// frequency, UI-visible).
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSpidolSocket } from '../useSpidolSocket'

class FakeWebSocket {
  static instances = []

  constructor(url) {
    this.url = url
    this.onopen = null
    this.onclose = null
    this.onmessage = null
    this.closed = false
    FakeWebSocket.instances.push(this)
  }

  simulateOpen() {
    this.onopen?.()
  }

  simulateMessage(data) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }

  close() {
    this.closed = true
    this.onclose?.()
  }
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useSpidolSocket', () => {
  it('connects to the given URL', () => {
    renderHook(() => useSpidolSocket('ws://127.0.0.1:8765'))
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(FakeWebSocket.instances[0].url).toBe('ws://127.0.0.1:8765')
  })

  it('reports connecting then open connection state', async () => {
    const { result } = renderHook(() => useSpidolSocket('ws://127.0.0.1:8765'))
    expect(result.current.connectionState).toBe('connecting')

    act(() => {
      FakeWebSocket.instances[0].simulateOpen()
    })

    await waitFor(() => expect(result.current.connectionState).toBe('open'))
  })

  it('stores incoming TRACK_UPDATE messages in latestTrackRef without forcing a state update', () => {
    const { result } = renderHook(() => useSpidolSocket('ws://127.0.0.1:8765'))
    const socket = FakeWebSocket.instances[0]

    const message = {
      type: 'TRACK_UPDATE',
      device_id: 'spidol_main',
      x: 0.4,
      y: 0.6,
      is_touching: true,
      is_detected: true,
      fps: 60,
    }

    act(() => {
      socket.simulateMessage(message)
    })

    expect(result.current.latestTrackRef.current).toEqual(message)
  })

  it('closes the socket on unmount', () => {
    const { unmount } = renderHook(() => useSpidolSocket('ws://127.0.0.1:8765'))
    const socket = FakeWebSocket.instances[0]

    unmount()

    expect(socket.closed).toBe(true)
  })
})
