import { describe, expect, it } from 'vitest'
import { autoscaleX, autoscaleY, compileExpression, sampleFunction, sampleParametric } from '../functionGraph'

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

describe('sampleParametric', () => {
  it('traces a full circle, not just the upper half (docs/adr/0006)', () => {
    const x = compileExpression('r*cos(t)')
    const y = compileExpression('r*sin(t)')
    const points = sampleParametric(x, y, { r: 2 }, 0, 2 * Math.PI, 5)

    // step = 2pi/4 = pi/2: t=0 -> (2,0), t=pi/2 -> (0,2), t=pi -> (-2,0), t=3pi/2 -> (0,-2)
    expect(points[0].x).toBeCloseTo(2)
    expect(points[0].y).toBeCloseTo(0)
    expect(points[1].x).toBeCloseTo(0)
    expect(points[1].y).toBeCloseTo(2)
    expect(points[2].x).toBeCloseTo(-2)
    expect(points[2].y).toBeCloseTo(0, 5)
    expect(points[3].x).toBeCloseTo(0)
    expect(points[3].y).toBeCloseTo(-2)
  })

  it('skips a sample where either expression is non-finite', () => {
    const x = compileExpression('t')
    const y = compileExpression('1/t')
    const points = sampleParametric(x, y, {}, -1, 1, 3)

    // t=-1 -> (-1,-1), t=0 -> y=1/0=Infinity (skipped), t=1 -> (1,1)
    expect(points).toEqual([
      { x: -1, y: -1 },
      { x: 1, y: 1 },
    ])
  })
})

describe('autoscaleX', () => {
  it("derives [min, max] from a parametric curve's x values, independent of a fixed domain", () => {
    const points = [
      { x: -2, y: 0 },
      { x: 2, y: 0 },
    ]
    const [xMin, xMax] = autoscaleX(points, { paddingRatio: 0 })
    expect(xMin).toBe(-2)
    expect(xMax).toBe(2)
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
