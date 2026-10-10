// Picks a handful of "nice" (1/2/5 x 10^n) axis tick values within
// [min, max], reusing niceStep's step-picking logic -- shared by the
// function_graph canvas renderer's x and y axes (see SimulationWidget.jsx).
import { decimalPlacesForStep, niceStep } from './niceStep'

export function niceTicks(min, max, targetCount = 5) {
  if (!(max > min)) return [min]
  const step = niceStep(min, max, targetCount)
  const decimals = decimalPlacesForStep(step)
  const start = Math.ceil(min / step) * step

  const ticks = []
  for (let v = start; v <= max + step * 1e-9; v += step) {
    ticks.push(Number(v.toFixed(decimals)))
  }
  return ticks
}
