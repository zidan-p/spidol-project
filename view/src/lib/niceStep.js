// Picks a "nice" slider step (1/2/5 x a power of ten) for an arbitrary
// AI-returned [min, max] range, instead of the previous `(max-min)/200`
// which produced awkward steps like 0.45 -- dragging the slider would then
// drift between values that look like clean integers and values with a
// long decimal tail for no reason the user could predict.
export function niceStep(min, max, targetSteps = 100) {
  const range = max - min
  if (!(range > 0)) return 1

  const rough = range / targetSteps
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const residual = rough / magnitude

  let nice
  if (residual < 1.5) nice = 1
  else if (residual < 3) nice = 2
  else if (residual < 7) nice = 5
  else nice = 10

  return nice * magnitude
}

// Number of decimal places implied by a step value (e.g. 0.05 -> 2), used
// to round a slider's raw input value and kill floating-point noise
// (0.1 + 0.2-style drift) rather than displaying it.
export function decimalPlacesForStep(step) {
  if (!Number.isFinite(step) || step <= 0) return 0
  const str = step.toString()
  if (str.includes('e-')) {
    // Very small steps (e.g. 1e-7) -- toFixed can't take more than 100.
    return Math.min(100, Number(str.split('e-')[1]))
  }
  const dot = str.indexOf('.')
  return dot === -1 ? 0 : str.length - dot - 1
}

export function roundToStep(value, step) {
  return Number(value.toFixed(decimalPlacesForStep(step)))
}
