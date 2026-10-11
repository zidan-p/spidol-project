import { describe, expect, it } from 'vitest'
import { traceSmoothPath } from '../smoothPath'

// A fake 2D context that just records which path commands were called, so
// the smoothing logic can be verified without a real canvas (unavailable
// under jsdom).
function recordingCtx() {
  const calls = []
  return {
    calls,
    moveTo: (x, y) => calls.push(['moveTo', x, y]),
    lineTo: (x, y) => calls.push(['lineTo', x, y]),
    quadraticCurveTo: (cx, cy, x, y) => calls.push(['quadraticCurveTo', cx, cy, x, y]),
  }
}

describe('traceSmoothPath', () => {
  it('does nothing for an empty point list', () => {
    const ctx = recordingCtx()
    traceSmoothPath(ctx, [])
    expect(ctx.calls).toEqual([])
  })

  it('moves to the single point without drawing a line', () => {
    const ctx = recordingCtx()
    traceSmoothPath(ctx, [[1, 2]])
    expect(ctx.calls).toEqual([['moveTo', 1, 2]])
  })

  it('routes an open path through quadratic curves between midpoints, ending at the last point exactly', () => {
    const ctx = recordingCtx()
    const points = [
      [0, 0],
      [10, 10],
      [20, 0],
    ]
    traceSmoothPath(ctx, points, false)

    expect(ctx.calls[0]).toEqual(['moveTo', 0, 0])
    expect(ctx.calls[1]).toEqual(['quadraticCurveTo', 10, 10, 15, 5])
    expect(ctx.calls[2]).toEqual(['lineTo', 20, 0])
  })

  it('wraps around through the closing segment when closed', () => {
    const ctx = recordingCtx()
    const points = [
      [0, 0],
      [10, 0],
      [10, 10],
    ]
    traceSmoothPath(ctx, points, true)

    expect(ctx.calls[0]).toEqual(['moveTo', 5, 5])
    expect(ctx.calls.at(-1)).toEqual(['quadraticCurveTo', 10, 10, 5, 5])
  })
})
