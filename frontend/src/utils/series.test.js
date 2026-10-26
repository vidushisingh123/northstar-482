import { expect, it } from 'vitest'
import { forecastRowsOf, spanInDays, toChartRows } from './series'
import { makePayload } from '../test/payloads'

it('keeps null (not zero) for missing values and sorts by time', () => {
  const payload = makePayload({ start: '2026-01-01', end: '2026-01-01' })
  const rows = toChartRows([...payload.series].reverse())
  expect(rows[0].t).toBeLessThan(rows[1].t)
  expect(rows[1].forecast).toBeNull() // :30 half-hour of an hourly forecast
  expect(rows[1].forecastExpected).toBe(false)
  expect(rows[0].forecast).not.toBeNull()
  expect(rows[0].error).toBe(rows[0].forecast - rows[0].actual)
})

it('forecast rows keep only intervals where a forecast can exist', () => {
  const rows = toChartRows(makePayload({ start: '2026-01-01', end: '2026-01-02' }).series)
  expect(rows).toHaveLength(96)
  expect(forecastRowsOf(rows)).toHaveLength(48)
})

it('span in days covers the inclusive end date', () => {
  const rows = toChartRows(makePayload({ start: '2026-01-01', end: '2026-01-07' }).series)
  expect(rows).toHaveLength(336)
  expect(spanInDays(rows)).toBeCloseTo(7 - 0.5 / 24, 3) // last interval starts 23:30 on 7 Jan
})
