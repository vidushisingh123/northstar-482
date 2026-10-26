// Convert API records into the shape the charts use: t = timestamp in milliseconds.
export function toChartRows(series) {
  return series
    .map((p) => ({
      t: Date.parse(p.start_time),
      forecast: p.forecast_mw ?? null, // null makes the line show a gap instead of a fake value
      actual: p.actual_mw ?? null,
      error: p.error_mw ?? null, // forecast - actual, computed by the backend
      // false = the forecast dataset has no value at this start time by design (e.g. hourly WINDFOR at :30)
      forecastExpected: p.forecast_expected !== false,
    }))
    .sort((a, b) => a.t - b.t)
}

// Rows where a forecast can exist. Lines for forecast/error use only these, so an hourly
// forecast joins up across the half-hours it does not cover, while a genuinely missing
// forecast (null on one of these rows) still breaks the line and shows as a gap.
export function forecastRowsOf(rows) {
  return rows.filter((row) => row.forecastExpected)
}

export function spanInDays(rows) {
  if (rows.length < 2) return 1
  return (rows[rows.length - 1].t - rows[0].t) / 86_400_000
}
