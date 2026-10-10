import { describe, expect, it } from 'vitest'
import { niceTicks } from '../axisTicks'

describe('niceTicks', () => {
  it('produces clean round ticks spanning a -10..10 range', () => {
    expect(niceTicks(-10, 10, 5)).toEqual([-10, -5, 0, 5, 10])
  })

  it('produces ticks for a narrow, non-symmetric range', () => {
    const ticks = niceTicks(-2.84, 4.9, 5)
    expect(ticks.length).toBeGreaterThan(1)
    for (const t of ticks) {
      expect(t).toBeGreaterThanOrEqual(-2.84)
      expect(t).toBeLessThanOrEqual(4.9)
    }
  })

  it('returns a single value for a degenerate (zero-range) domain instead of looping forever', () => {
    expect(niceTicks(5, 5)).toEqual([5])
  })
})
