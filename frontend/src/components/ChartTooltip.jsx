import { formatDateTime, formatMw, formatSignedMw } from '../utils/format'

/**
 * Tooltip that reads values from OUR rows (looked up by timestamp) instead of Recharts'
 * merged payload, because the forecast and error lines use their own point sets.
 * `fields` = [{ key: 'actual' | 'forecast' | 'error', label, signed? }]
 */
export default function ChartTooltip({ active, label, payload, rowsByTime, fields }) {
  if (!active) return null
  const t = payload?.[0]?.payload?.t ?? label
  const row = rowsByTime.get(t)
  if (!row) return null

  return (
    <div className="tooltip">
      <p className="tooltip-time">{formatDateTime(t)} (half-hour start)</p>
      {fields.map((field) => {
        const value = row[field.key]
        const usesForecast = field.key === 'forecast' || field.key === 'error'
        let text
        if (value !== null && value !== undefined) {
          text = field.signed ? formatSignedMw(value) : formatMw(value)
        } else if (usesForecast && !row.forecastExpected) {
          text = 'no forecast at this time (hourly dataset)'
        } else if (usesForecast && row.actual !== null && row.actual !== undefined) {
          text = 'missing (no eligible forecast)'
        } else {
          text = 'missing'
        }
        return (
          <p key={field.key} className="tooltip-row">
            <span style={{ color: field.color }}>{field.label}:</span> {text}
          </p>
        )
      })}
    </div>
  )
}
