import { describe, expect, it } from 'vitest'
import { panViewport, zoomViewport } from '../graphViewport'

const BASE = { xMin: -10, xMax: 10, yMin: -10, yMax: 10 }

describe('zoomViewport', () => {
  it('zooms in (factor < 1) around the focus point, shrinking the span', () => {
    const next = zoomViewport(BASE, { cx: 0, cy: 0, factor: 0.5 })
    expect(next.xMax - next.xMin).toBeCloseTo(10)
    expect(next.yMax - next.yMin).toBeCloseTo(10)
  })

  it('zooms out (factor > 1), growing the span', () => {
    const next = zoomViewport(BASE, { cx: 0, cy: 0, factor: 2 })
    expect(next.xMax - next.xMin).toBeCloseTo(40)
  })

  it('keeps the focus point fixed in place (zoom toward cursor, not just the center)', () => {
    // Focus near the right edge -- zooming in should pull the right edge
    // toward the focus point much more than the left edge moves.
    const next = zoomViewport(BASE, { cx: 8, cy: 0, factor: 0.5 })
    const rightEdgeMovement = Math.abs(next.xMax - BASE.xMax)
    const leftEdgeMovement = Math.abs(next.xMin - BASE.xMin)
    expect(rightEdgeMovement).toBeLessThan(leftEdgeMovement)
  })

  it('never collapses to a zero or negative span under repeated zoom-in', () => {
    let viewport = BASE
    for (let i = 0; i < 100; i += 1) {
      viewport = zoomViewport(viewport, { cx: 0, cy: 0, factor: 0.5 })
    }
    expect(viewport.xMax).toBeGreaterThan(viewport.xMin)
    expect(viewport.yMax).toBeGreaterThan(viewport.yMin)
  })

  it('never grows unboundedly under repeated zoom-out', () => {
    let viewport = BASE
    for (let i = 0; i < 100; i += 1) {
      viewport = zoomViewport(viewport, { cx: 0, cy: 0, factor: 2 })
    }
    expect(Number.isFinite(viewport.xMax - viewport.xMin)).toBe(true)
    expect(viewport.xMax - viewport.xMin).toBeLessThan(1e7)
  })
})

describe('panViewport', () => {
  it('shifts both axes by the given data-space delta, preserving the span', () => {
    const next = panViewport(BASE, { dx: 5, dy: -3 })
    expect(next).toEqual({ xMin: -5, xMax: 15, yMin: -13, yMax: 7 })
  })
})
