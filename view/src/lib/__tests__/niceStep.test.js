import { describe, expect, it } from 'vitest'
import { decimalPlacesForStep, niceStep, roundToStep } from '../niceStep'

describe('niceStep', () => {
  it('picks a clean integer step for a wide range like Spring Stiffness (10-100)', () => {
    // Previously (max-min)/200 = 0.45 -- an awkward, unpredictable step.
    expect(niceStep(10, 100)).toBe(1)
  })

  it('picks a clean fractional step for a narrow range like Mass (0.5-5.0)', () => {
    expect(niceStep(0.5, 5.0)).toBeCloseTo(0.05)
  })

  it('falls back to 1 for a degenerate (zero or negative) range', () => {
    expect(niceStep(5, 5)).toBe(1)
    expect(niceStep(5, 2)).toBe(1)
  })
})

describe('decimalPlacesForStep', () => {
  it.each([
    [1, 0],
    [5, 0],
    [0.5, 1],
    [0.05, 2],
    [0.1, 1],
  ])('step %s -> %s decimal places', (step, expected) => {
    expect(decimalPlacesForStep(step)).toBe(expected)
  })
})

describe('roundToStep', () => {
  it('kills floating-point drift to the step-implied precision', () => {
    expect(roundToStep(0.1 + 0.2, 0.1)).toBe(0.3)
  })

  it('leaves already-clean integer values alone', () => {
    expect(roundToStep(80, 1)).toBe(80)
  })
})
