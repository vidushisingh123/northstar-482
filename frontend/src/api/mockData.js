// SYNTHETIC DATA for a visual preview only. These are NOT real Elexon values.
// Metrics are computed here only so the preview is self-consistent; in the real
// app the backend computes them.
const HALF_HOUR_MS = 30 * 60 * 1000
const DAY_MS = 24 * 60 * 60 * 1000

export function buildMockDashboard(start, end) {
  const startMs = Date.parse(`${start}T00:00:00Z`)
  const endMs = Date.parse(`${end}T00:00:00Z`) + DAY_MS

  const series = []
  let n = 0
  for (let t = startMs; t < endMs; t += HALF_HOUR_MS, n += 1) {
    const shape = 6000 + 3500 * Math.sin(n / 60) + 1200 * Math.sin(n / 7)
    // A few deliberate gaps so the "missing data" handling can be seen.
    const actual = n % 173 === 0 ? null : Math.round(Math.max(0, shape))
    const forecast =
      n % 211 === 0 ? null : Math.round(Math.max(0, shape + 800 * Math.sin(n / 11) - 250))
    const error = actual === null || forecast === null ? null : forecast - actual
    series.push({
      start_time: new Date(t).toISOString(),
      forecast_mw: forecast,
      actual_mw: actual,
      error_mw: error,
      forecast_publish_time: null,
      forecast_expected: true,
    })
  }

  const matched = series.filter((p) => p.error_mw !== null)
  const count = matched.length
  const mean = (values) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : null)

  return {
    meta: {
      start,
      end,
      unit: 'MW',
      interval_minutes: 30,
      forecast_selection: 'SAMPLE DATA - synthetic values, no real forecast selection applied.',
      forecast_resolution_minutes: 30,
      intervals_total: series.length,
      intervals_forecastable: series.length,
      intervals_missing_forecast: series.filter((p) => p.forecast_mw === null).length,
      intervals_missing_actual: series.filter((p) => p.actual_mw === null).length,
      duplicates_removed: 0,
    },
    metrics: {
      matched_intervals: count,
      mean_forecast_mw: mean(matched.map((p) => p.forecast_mw)),
      mean_actual_mw: mean(matched.map((p) => p.actual_mw)),
      mae_mw: mean(matched.map((p) => Math.abs(p.error_mw))),
      rmse_mw: count ? Math.sqrt(mean(matched.map((p) => p.error_mw ** 2))) : null,
      bias_mw: mean(matched.map((p) => p.error_mw)),
    },
    series,
  }
}
