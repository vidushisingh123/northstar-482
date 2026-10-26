// SYNTHETIC test payloads shaped like the backend response. Not real Elexon data.
const HALF_HOUR = 30 * 60 * 1000

export function makePayload({ start = '2026-01-01', end = '2026-01-07', offset = 2000, hourly = true, dropHours = [] } = {}) {
  const startMs = Date.parse(`${start}T00:00:00Z`)
  const endMs = Date.parse(`${end}T00:00:00Z`) + 24 * 3600 * 1000
  const series = []
  let i = 0
  for (let t = startMs; t < endMs; t += HALF_HOUR, i += 1) {
    const expected = hourly ? t % 3600000 === 0 : true
    const actual = 12000 + (i % 50) * 40
    const dropped = dropHours.includes(new Date(t).toISOString())
    const forecast = expected && !dropped ? actual + offset : null
    series.push({
      start_time: new Date(t).toISOString().replace('.000Z', 'Z'),
      forecast_mw: forecast,
      actual_mw: actual,
      error_mw: forecast === null ? null : forecast - actual,
      forecast_publish_time: forecast === null ? null : '2026-01-01T10:30:00Z',
      forecast_expected: expected,
    })
  }
  const matched = series.filter((p) => p.error_mw !== null)
  const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length
  const forecastable = series.filter((p) => p.forecast_expected).length
  return {
    meta: {
      start, end, unit: 'MW', interval_minutes: 30,
      forecast_selection: 'TEST selection text',
      forecast_resolution_minutes: hourly ? 60 : 30,
      intervals_total: series.length,
      intervals_forecastable: forecastable,
      intervals_missing_forecast: series.filter((p) => p.forecast_expected && p.forecast_mw === null).length,
      intervals_missing_actual: 0,
      duplicates_removed: 0,
    },
    metrics: {
      matched_intervals: matched.length,
      mean_forecast_mw: mean(matched.map((p) => p.forecast_mw)),
      mean_actual_mw: mean(matched.map((p) => p.actual_mw)),
      mae_mw: mean(matched.map((p) => Math.abs(p.error_mw))),
      rmse_mw: Math.sqrt(mean(matched.map((p) => p.error_mw ** 2))),
      bias_mw: mean(matched.map((p) => p.error_mw)),
    },
    series,
  }
}
