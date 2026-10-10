// Generic y = f(x) evaluation for the function_graph Simulation Type
// (GLOSSARY.md, docs/adr/0006): the AI returns an arbitrary single-variable
// expression (e.g. "a*x^2 + b*x + c") instead of one of a fixed set of
// hand-written renderers. Parsed/evaluated via mathjs -- never `eval()` or
// `new Function(...)` -- so a malformed or hostile expression can only ever
// fail to parse/evaluate, never execute as code.
// `mathjs/number` (not the default `mathjs` entry point): a plain-JS-number
// build without BigNumber/Fraction/Complex support, which this project
// never needs and which otherwise roughly quadruples the bundle size.
import { compile } from 'mathjs/number'

// Returns a compiled mathjs expression, or null if it doesn't parse (a
// malformed expression from the AI is possible and must not crash the UI --
// see FunctionGraphWidget's "couldn't render this function" fallback).
export function compileExpression(expression) {
  try {
    return compile(expression)
  } catch {
    return null
  }
}

// Samples `compiled` across [xMin, xMax], merging each parameter's current
// value into the evaluation scope alongside x. A sample that throws or
// evaluates to a non-finite number (e.g. sqrt of a negative, log of zero,
// division by zero) is omitted rather than breaking the whole curve --
// real functions often have domain restrictions, so a gap in the plotted
// line is the correct, expected rendering, not a bug.
export function sampleFunction(compiled, parameterValues, xMin, xMax, numSamples = 200) {
  const points = []
  const step = (xMax - xMin) / (numSamples - 1)
  for (let i = 0; i < numSamples; i += 1) {
    const x = xMin + i * step
    try {
      const y = compiled.evaluate({ ...parameterValues, x })
      if (Number.isFinite(y)) points.push({ x, y })
    } catch {
      // Domain error at this x (e.g. sqrt(negative)) -- skip the point.
    }
  }
  return points
}

// Picks a y-axis viewport from the actually-sampled points, with padding,
// rather than assuming a fixed symmetric range -- a quadratic like y = x^2
// over x in [-10, 10] reaches y = 100, which a fixed [-10, 10] viewport
// would clip almost entirely.
export function autoscaleY(points, { paddingRatio = 0.15, fallback = [-10, 10] } = {}) {
  if (points.length === 0) return fallback
  let yMin = Infinity
  let yMax = -Infinity
  for (const { y } of points) {
    if (y < yMin) yMin = y
    if (y > yMax) yMax = y
  }
  if (yMin === yMax) {
    // A constant function (e.g. y = 5) has zero range -- pad around it
    // instead of returning a zero-height viewport.
    const pad = Math.max(Math.abs(yMin), 1)
    return [yMin - pad, yMax + pad]
  }
  const padding = (yMax - yMin) * paddingRatio
  return [yMin - padding, yMax + padding]
}
