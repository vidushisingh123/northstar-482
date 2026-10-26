import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('recharts', async (importOriginal) => (await import('../test/mockRecharts')).withFixedSize(importOriginal))

import { makePayload } from '../test/payloads'
import { spanInDays, toChartRows } from '../utils/series'
import ErrorChart from './ErrorChart'
import ForecastChart from './ForecastChart'

afterEach(cleanup)

const pathStats = (path) => {
  const d = path?.getAttribute('d') || ''
  const nums = [...d.matchAll(/[ML]\s*(-?[\d.]+)[ ,](-?[\d.]+)/g)].map((m) => ({ x: +m[1], y: +m[2] }))
  return { M: (d.match(/M/g) || []).length, L: (d.match(/L/g) || []).length, points: nums }
}
const curves = (container) => [...container.querySelectorAll('path.recharts-line-curve')].map(pathStats)

function renderForecast(payload) {
  const rows = toChartRows(payload.series)
  return render(
    <ForecastChart rows={rows} spanDays={spanInDays(rows)} forecastResolutionMinutes={payload.meta.forecast_resolution_minutes} />,
  )
}
function renderError(payload) {
  const rows = toChartRows(payload.series)
  return render(<ErrorChart rows={rows} spanDays={spanInDays(rows)} />)
}

describe('hourly forecast (the 336 intervals / 168 matched case)', () => {
  const payload = makePayload()

  it('draws BOTH the actual and the forecast as connected lines', () => {
    const [actual, forecast] = curves(renderForecast(payload).container)
    expect(actual.M).toBe(1)
    expect(actual.L).toBe(335) // every half-hour
    expect(forecast.M).toBe(1) // one continuous line...
    expect(forecast.L).toBe(167) // ...through all 168 hourly points
  })

  it('puts both lines on one y-scale, inside the plot area (forecast is higher, so drawn above)', () => {
    const [actual, forecast] = curves(renderForecast(payload).container)
    const inside = (line) => line.points.every((p) => p.y >= 8 && p.y <= 292) // chart margins are 8px
    expect(inside(actual)).toBe(true)
    expect(inside(forecast)).toBe(true) // not clipped off the top of the plot
    // synthetic data: max forecast (15,920) > max actual (13,960)
    expect(Math.min(...forecast.points.map((p) => p.y))).toBeLessThan(Math.min(...actual.points.map((p) => p.y)))
  })

  it('draws the error as a real line, not just the zero reference line', () => {
    const { container } = renderError(payload)
    const [error] = curves(container)
    expect(error.M).toBe(1)
    expect(error.L).toBe(167)
    expect(container.querySelector('.recharts-reference-line')).toBeTruthy()
  })

  it('error line is drawn at +2000 (matches the signed bias), not flat at zero', () => {
    const { container } = renderError(makePayload({ offset: 2000 }))
    const [error] = curves(container)
    const ys = new Set(error.points.map((p) => Math.round(p.y)))
    expect(ys.size).toBe(1) // constant error in this synthetic payload
    const zeroY = Number(container.querySelector('.recharts-reference-line line')?.getAttribute('y1'))
    expect([...ys][0]).toBeLessThan(zeroY) // positive error plots ABOVE the zero line
  })
})

describe('genuine gaps stay visible', () => {
  it('a missing forecast hour splits the forecast line and the error line in two', () => {
    const payload = makePayload({ dropHours: ['2026-01-03T05:00:00.000Z'] })
    const [, forecast] = curves(renderForecast(payload).container)
    expect(forecast.M).toBe(2)
    expect(curves(renderError(payload).container)[0].M).toBe(2)
  })

  it('an isolated forecast point is drawn as a dot instead of vanishing', () => {
    const payload = makePayload({ start: '2026-01-01', end: '2026-01-01' })
    // keep only the forecast at 06:00 so both neighbours are missing
    payload.series.forEach((p) => {
      if (p.start_time !== '2026-01-01T06:00:00Z') { p.forecast_mw = null; p.error_mw = null }
    })
    const { container } = renderForecast(payload)
    expect(container.querySelectorAll('circle').length).toBe(1)
  })

  it('does not scatter dots over a continuous line', () => {
    expect(renderForecast(makePayload()).container.querySelectorAll('circle').length).toBe(0)
  })
})

describe('half-hourly forecast still works', () => {
  it('draws a continuous forecast line through every half-hour', () => {
    const [, forecast] = curves(renderForecast(makePayload({ hourly: false })).container)
    expect(forecast.M).toBe(1)
    expect(forecast.L).toBe(335)
  })
})
