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

// Samples a parametric curve (x(t), y(t)) for t in [tMin, tMax] -- used for
// function_graph curves that fail the vertical-line test (a circle, ellipse,
// or any other closed/implicit curve can't be a single y = f(x), so the AI
// returns two expressions in a parameter t instead; see docs/adr/0006 and
// the PROMPT_TEXT in server/ai/vision_pipeline.py). Mirrors sampleFunction's
// error handling: a sample where either expression throws or evaluates
// non-finite is omitted rather than breaking the whole curve.
export function sampleParametric(compiledX, compiledY, parameterValues, tMin, tMax, numSamples = 300) {
  const points = []
  const step = (tMax - tMin) / (numSamples - 1)
  for (let i = 0; i < numSamples; i += 1) {
    const t = tMin + i * step
    try {
      const x = compiledX.evaluate({ ...parameterValues, t })
      const y = compiledY.evaluate({ ...parameterValues, t })
      if (Number.isFinite(x) && Number.isFinite(y)) points.push({ x, y })
    } catch {
      // Domain error at this t -- skip the point.
    }
  }
  return points
}

// Picks a [min, max] viewport from a plain array of numbers, with padding,
// rather than assuming a fixed range -- a quadratic like y = x^2 over x in
// [-10, 10] reaches y = 100, which a fixed [-10, 10] viewport would clip
// almost entirely. Shared by both axes: autoscaleY (below) extracts `y`
// from {x, y} points for the explicit y = f(x) case; a parametric curve's
// x values need the exact same treatment (a circle's x range is [-r, r],
// not a fixed domain), so callers extract whichever field they need.
export function autoscale(values, { paddingRatio = 0.15, fallback = [-10, 10] } = {}) {
  if (values.length === 0) return fallback
  let min = Infinity
  let max = -Infinity
  for (const v of values) {
    if (v < min) min = v
    if (v > max) max = v
  }
  if (min === max) {
    // A constant (e.g. y = 5, or a degenerate single-point curve) has zero
    // range -- pad around it instead of returning a zero-height viewport.
    const pad = Math.max(Math.abs(min), 1)
    return [min - pad, max + pad]
  }
  const padding = (max - min) * paddingRatio
  return [min - padding, max + padding]
}

export function autoscaleY(points, options) {
  return autoscale(
    points.map((p) => p.y),
    options
  )
}

export function autoscaleX(points, options) {
  return autoscale(
    points.map((p) => p.x),
    options
  )
}
