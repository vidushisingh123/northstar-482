import { formatMw, formatSignedMw } from '../utils/format'

export default function KpiCards({ metrics, meta }) {
  const cards = [
    { label: 'Avg. forecast generation', value: formatMw(metrics.mean_forecast_mw), hint: 'Mean forecast over matched intervals' },
    { label: 'Avg. actual generation', value: formatMw(metrics.mean_actual_mw), hint: 'Mean actual wind over matched intervals' },
    { label: 'MAE', value: formatMw(metrics.mae_mw), hint: 'Mean absolute error' },
    { label: 'RMSE', value: formatMw(metrics.rmse_mw), hint: 'Root mean square error; penalises big misses' },
    { label: 'Forecast bias', value: formatSignedMw(metrics.bias_mw), hint: 'Mean of forecast − actual. Positive = over-forecast' },
  ]

  return (
    <section aria-label="Key metrics">
      <div className="kpi-grid">
        {cards.map((card) => (
          <div className="kpi" key={card.label}>
            <p className="kpi-label">{card.label}</p>
            <p className="kpi-value">{card.value}</p>
            <p className="kpi-hint">{card.hint}</p>
          </div>
        ))}
      </div>
      <CoverageNote metrics={metrics} meta={meta} />
    </section>
  )
}

function CoverageNote({ metrics, meta }) {
  const matched = metrics.matched_intervals ?? 0
  const forecastable = meta?.intervals_forecastable ?? meta?.intervals_total ?? 0
  const total = meta?.intervals_total ?? 0
  const missing = meta?.intervals_missing_forecast ?? 0
  const hourly = meta?.forecast_resolution_minutes === 60
  const coverage = forecastable > 0 ? matched / forecastable : 0
  const incomplete = forecastable === 0 || coverage < 0.9

  return (
    <div className={incomplete ? 'coverage-note coverage-warn' : 'coverage-note'} role="note">
      <p>
        Metrics use <strong>{matched}</strong> compared intervals
        {forecastable > 0 && <> out of {forecastable} where a forecast can exist ({Math.round(coverage * 100)}%)</>}
        , i.e. only intervals with both a forecast and an actual.
      </p>
      {hourly && (
        <p>
          WINDFOR is an hourly forecast: of {total} half-hour intervals, {total - forecastable} have no forecast by
          design and are not compared (nothing is interpolated). The compared actuals are the half-hours starting on the hour.
        </p>
      )}
      {missing > 0 && (
        <p>
          {missing} forecast interval{missing === 1 ? '' : 's'} had no eligible forecast published before the cutoff.
          Coverage is incomplete, so treat the figures with care.
        </p>
      )}
    </div>
  )
}
