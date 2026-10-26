import Card from './Card'

export default function DataQuality({ meta, metrics }) {
  const rows = [
    ['Half-hourly intervals in range', meta.intervals_total],
    ['Forecast resolution', meta.forecast_resolution_minutes === 60 ? 'Hourly (WINDFOR)' : 'Half-hourly'],
    ['Intervals where a forecast can exist', meta.intervals_forecastable ?? meta.intervals_total],
    ['Compared (forecast + actual)', metrics.matched_intervals],
    ['Missing forecast (where one can exist)', meta.intervals_missing_forecast],
    ['Missing actual', meta.intervals_missing_actual],
    ['Duplicate records removed', meta.duplicates_removed],
  ]

  return (
    <Card title="Data quality and method">
      <dl className="quality-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value ?? '—'}</dd>
          </div>
        ))}
      </dl>
      <p className="note">
        <strong>Forecast used for each interval:</strong> {meta.forecast_selection ?? 'not provided by the API'}
      </p>
      <p className="note">
        Actual = Elexon FUELHH, fuel type WIND. Forecast = Elexon WINDFOR. Metrics only use intervals where both exist.
      </p>
    </Card>
  )
}
