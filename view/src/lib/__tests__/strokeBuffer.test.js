// Tests for the stroke-buffer reducer: the seam between incoming
// TRACK_UPDATE messages and the renderable stroke list, independent of the
// canvas/rendering concern. Ink must be driven purely by is_touching
// transitions in the message stream, never by native pointer events.
import { describe, expect, it } from 'vitest'
import { createStrokeBuffer, ingestTrackUpdate } from '../strokeBuffer'

function trackUpdate(overrides) {
  return {
    type: 'TRACK_UPDATE',
    device_id: 'spidol_main',
    x: 0,
    y: 0,
    is_touching: false,
    is_detected: true,
    fps: 60,
    ...overrides,
  }
}

describe('createStrokeBuffer', () => {
  it('starts empty with no active stroke', () => {
    const buffer = createStrokeBuffer()
    expect(buffer.strokes).toEqual([])
    expect(buffer.activeStroke).toBeNull()
  })
})

describe('ingestTrackUpdate', () => {
  it('does nothing while not touching and no active stroke', () => {
    const buffer = createStrokeBuffer()
    const next = ingestTrackUpdate(buffer, trackUpdate({ is_touching: false }))
    expect(next.strokes).toEqual([])
    expect(next.activeStroke).toBeNull()
  })

  it('starts a new active stroke on the first touching update', () => {
    const buffer = createStrokeBuffer()
    const next = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.2, is_touching: true }))
    expect(next.activeStroke).toEqual([{ x: 0.1, y: 0.2 }])
    expect(next.strokes).toEqual([])
  })

  it('appends points to the active stroke on subsequent touching updates', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }))
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.2, y: 0.2, is_touching: true }))

    expect(buffer.activeStroke).toEqual([
      { x: 0.1, y: 0.1 },
      { x: 0.2, y: 0.2 },
    ])
  })

  it('closes the active stroke into strokes[] when touching ends', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }))
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.2, y: 0.2, is_touching: true }))
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.2, y: 0.2, is_touching: false }))

    expect(buffer.activeStroke).toBeNull()
    expect(buffer.strokes).toEqual([
      [
        { x: 0.1, y: 0.1 },
        { x: 0.2, y: 0.2 },
      ],
    ])
  })

  it('starts a fresh stroke after a previous one has closed', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0, y: 0, is_touching: true }))
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0, y: 0, is_touching: false }))
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.5, y: 0.5, is_touching: true }))

    expect(buffer.strokes).toHaveLength(1)
    expect(buffer.activeStroke).toEqual([{ x: 0.5, y: 0.5 }])
  })

  it('ignores updates where the tracker reports not-detected', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }))
    buffer = ingestTrackUpdate(
      buffer,
      trackUpdate({ x: 0.9, y: 0.9, is_touching: true, is_detected: false })
    )

    expect(buffer.activeStroke).toEqual([{ x: 0.1, y: 0.1 }])
  })
})
