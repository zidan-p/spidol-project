import { describe, expect, it } from 'vitest'
import { autoscaleY, compileExpression, sampleFunction } from '../functionGraph'

describe('compileExpression', () => {
  it('compiles a valid mathjs expression', () => {
    const compiled = compileExpression('a*x^2 + b*x + c')
    expect(compiled).not.toBeNull()
    expect(compiled.evaluate({ a: 1, b: 0, c: 0, x: 3 })).toBe(9)
  })

  it('returns null for a malformed expression instead of throwing', () => {
    expect(compileExpression('a*x^2 +* b')).toBeNull()
  })
})

describe('sampleFunction', () => {
  it('samples a quadratic across the given domain', () => {
    const compiled = compileExpression('x^2')
    const points = sampleFunction(compiled, {}, -2, 2, 5)

    expect(points).toEqual([
      { x: -2, y: 4 },
      { x: -1, y: 1 },
      { x: 0, y: 0 },
      { x: 1, y: 1 },
      { x: 2, y: 4 },
    ])
  })

  it('merges parameter values into the evaluation scope', () => {
    const compiled = compileExpression('m*x + b')
    const points = sampleFunction(compiled, { m: 2, b: 1 }, 0, 1, 2)

    expect(points).toEqual([
      { x: 0, y: 1 },
      { x: 1, y: 3 },
    ])
  })

  it('skips points where evaluation is non-finite (e.g. sqrt of a negative) instead of crashing', () => {
    const compiled = compileExpression('sqrt(x)')
    const points = sampleFunction(compiled, {}, -1, 1, 3)

    // x=-1 -> NaN (skipped), x=0 -> 0, x=1 -> 1
    expect(points).toEqual([
      { x: 0, y: 0 },
      { x: 1, y: 1 },
    ])
  })
})

describe('autoscaleY', () => {
  it('derives [min, max] with padding from the actual sampled range', () => {
    const points = [
      { x: -2, y: 4 },
      { x: 0, y: 0 },
      { x: 2, y: 4 },
    ]
    const [yMin, yMax] = autoscaleY(points, { paddingRatio: 0.1 })

    expect(yMin).toBeCloseTo(-0.4)
    expect(yMax).toBeCloseTo(4.4)
  })

  it('pads around a constant (zero-range) function instead of returning a zero-height viewport', () => {
    const [yMin, yMax] = autoscaleY([{ x: 0, y: 5 }, { x: 1, y: 5 }])
    expect(yMax).toBeGreaterThan(yMin)
  })

  it('falls back to a default viewport when there are no valid points', () => {
    expect(autoscaleY([], { fallback: [-10, 10] })).toEqual([-10, 10])
  })
})
