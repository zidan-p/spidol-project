// Tests for the stroke-buffer reducer: the seam between incoming
// TRACK_UPDATE messages and the renderable stroke list, independent of the
// canvas/rendering concern. Ink must be driven purely by is_touching
// transitions in the message stream, never by native pointer events.
//
// Ticket 03 adds tool/style awareness: each committed stroke now carries the
// tool (pen/eraser/rectangle/ellipse/arrow/line/text) and style (color,
// width, dash) that were active when the stroke *started* -- changing tools
// mid-stroke never retroactively changes an in-progress stroke.
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

function penStyle(overrides) {
  return { tool: 'pen', color: '#ffffff', width: 4, dash: 'solid', ...overrides }
}

describe('createStrokeBuffer', () => {
  it('starts empty with no active stroke', () => {
    const buffer = createStrokeBuffer()
    expect(buffer.strokes).toEqual([])
    expect(buffer.activeStroke).toBeNull()
  })
})

describe('ingestTrackUpdate (pen tool)', () => {
  it('does nothing while not touching and no active stroke', () => {
    const buffer = createStrokeBuffer()
    const next = ingestTrackUpdate(buffer, trackUpdate({ is_touching: false }), penStyle())
    expect(next.strokes).toEqual([])
    expect(next.activeStroke).toBeNull()
  })

  it('starts a new active stroke on the first touching update, tagged with the current style', () => {
    const buffer = createStrokeBuffer()
    const next = ingestTrackUpdate(
      buffer,
      trackUpdate({ x: 0.1, y: 0.2, is_touching: true }),
      penStyle({ color: '#ff0000', width: 8, dash: 'dashed' })
    )
    expect(next.activeStroke).toMatchObject({
      tool: 'pen',
      color: '#ff0000',
      width: 8,
      dash: 'dashed',
      points: [{ x: 0.1, y: 0.2 }],
    })
    expect(next.strokes).toEqual([])
  })

  it('appends points to the active stroke on subsequent touching updates', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), penStyle())
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.2, y: 0.2, is_touching: true }), penStyle())

    expect(buffer.activeStroke.points).toEqual([
      { x: 0.1, y: 0.1 },
      { x: 0.2, y: 0.2 },
    ])
  })

  it('closes the active stroke into strokes[] when touching ends, reporting an add action', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), penStyle())
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.2, y: 0.2, is_touching: true }), penStyle())
    const result = ingestTrackUpdate(buffer, trackUpdate({ x: 0.2, y: 0.2, is_touching: false }), penStyle())

    expect(result.activeStroke).toBeNull()
    expect(result.strokes).toHaveLength(1)
    expect(result.strokes[0]).toMatchObject({
      tool: 'pen',
      points: [
        { x: 0.1, y: 0.1 },
        { x: 0.2, y: 0.2 },
      ],
    })
    expect(result.lastAction).toEqual({ type: 'add', stroke: result.strokes[0] })
  })

  it('starts a fresh stroke after a previous one has closed', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0, y: 0, is_touching: true }), penStyle())
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0, y: 0, is_touching: false }), penStyle())
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.5, y: 0.5, is_touching: true }), penStyle())

    expect(buffer.strokes).toHaveLength(1)
    expect(buffer.activeStroke.points).toEqual([{ x: 0.5, y: 0.5 }])
  })

  it('ignores updates where the tracker reports not-detected', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), penStyle())
    buffer = ingestTrackUpdate(
      buffer,
      trackUpdate({ x: 0.9, y: 0.9, is_touching: true, is_detected: false }),
      penStyle()
    )

    expect(buffer.activeStroke.points).toEqual([{ x: 0.1, y: 0.1 }])
  })

  it('returns no lastAction on calls that neither start nor close a stroke', () => {
    let buffer = createStrokeBuffer()
    const result = ingestTrackUpdate(buffer, trackUpdate({ is_touching: false }), penStyle())
    expect(result.lastAction).toBeNull()
  })
})

describe('ingestTrackUpdate (shape tools: line/rectangle/ellipse/arrow)', () => {
  it.each(['line', 'rectangle', 'ellipse', 'arrow'])(
    'collapses a %s stroke down to its start and end anchor points on release',
    (tool) => {
      let buffer = createStrokeBuffer()
      const style = { tool, color: '#00ff00', width: 2, dash: 'solid' }
      buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), style)
      buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.3, y: 0.2, is_touching: true }), style)
      const result = ingestTrackUpdate(buffer, trackUpdate({ x: 0.9, y: 0.8, is_touching: false }), style)

      expect(result.strokes).toHaveLength(1)
      expect(result.strokes[0].tool).toBe(tool)
      expect(result.strokes[0].points).toEqual([
        { x: 0.1, y: 0.1 },
        { x: 0.9, y: 0.8 },
      ])
    }
  )

  it('previews the live end anchor on the active shape stroke as it is dragged', () => {
    let buffer = createStrokeBuffer()
    const style = { tool: 'rectangle', color: '#fff', width: 2, dash: 'solid' }
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), style)
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.4, y: 0.5, is_touching: true }), style)

    expect(buffer.activeStroke.points).toEqual([
      { x: 0.1, y: 0.1 },
      { x: 0.4, y: 0.5 },
    ])
  })
})

describe('ingestTrackUpdate (text tool)', () => {
  it('commits a single-point anchor stroke with empty text, pending caption entry', () => {
    let buffer = createStrokeBuffer()
    const style = { tool: 'text', color: '#fff', width: 2, dash: 'solid' }
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.5, y: 0.5, is_touching: true }), style)
    const result = ingestTrackUpdate(buffer, trackUpdate({ x: 0.5, y: 0.5, is_touching: false }), style)

    expect(result.strokes).toHaveLength(1)
    expect(result.strokes[0]).toMatchObject({ tool: 'text', text: '', points: [{ x: 0.5, y: 0.5 }] })
    expect(result.lastAction).toEqual({ type: 'add', stroke: result.strokes[0] })
  })
})

describe('ingestTrackUpdate (eraser tool)', () => {
  it('removes whole strokes that the eraser path passes through, reporting an erase action', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), penStyle())
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: false }), penStyle())
    expect(buffer.strokes).toHaveLength(1)
    const target = buffer.strokes[0]

    const eraserStyle = { tool: 'eraser', color: '#fff', width: 12, dash: 'solid' }
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), eraserStyle)
    const result = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: false }), eraserStyle)

    expect(result.strokes).toEqual([])
    expect(result.lastAction).toEqual({ type: 'erase', removed: [target] })
  })

  it('leaves strokes untouched if the eraser path never comes near them', () => {
    let buffer = createStrokeBuffer()
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: true }), penStyle())
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.1, y: 0.1, is_touching: false }), penStyle())

    const eraserStyle = { tool: 'eraser', color: '#fff', width: 12, dash: 'solid' }
    buffer = ingestTrackUpdate(buffer, trackUpdate({ x: 0.9, y: 0.9, is_touching: true }), eraserStyle)
    const result = ingestTrackUpdate(buffer, trackUpdate({ x: 0.9, y: 0.9, is_touching: false }), eraserStyle)

    expect(result.strokes).toHaveLength(1)
    expect(result.lastAction).toBeNull()
  })
})
