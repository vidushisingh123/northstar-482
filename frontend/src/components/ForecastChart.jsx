import { useMemo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { forecastRowsOf } from '../utils/series'
import { formatAxisTick } from '../utils/format'
import Card from './Card'
import ChartTooltip from './ChartTooltip'
import { isolatedDot } from './isolatedDot.jsx'

const ACTUAL_COLOR = '#0b3d5c'
const FORECAST_COLOR = '#e07a1f'

export default function ForecastChart({ rows, spanDays, forecastResolutionMinutes = 30 }) {
  const forecastRows = useMemo(() => forecastRowsOf(rows), [rows])
  const rowsByTime = useMemo(() => new Map(rows.map((row) => [row.t, row])), [rows])
  const hourly = forecastResolutionMinutes === 60

  return (
    <Card
      title="Forecast vs actual wind generation"
      subtitle={
        'MW · times in UK local time · gaps = missing data' +
        (hourly
          ? ' · actual is half-hourly (FUELHH), forecast is hourly (WINDFOR): its line joins hourly points and is not interpolated at :30'
          : ' · half-hourly settlement intervals')
      }
    >
      <div className="chart-box">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e8ee" />
            <XAxis
              dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']}
              tickFormatter={(ms) => formatAxisTick(ms, spanDays)} minTickGap={48}
            />
            <YAxis tickFormatter={(v) => v.toLocaleString('en-GB')} label={{ value: 'MW', angle: -90, position: 'insideLeft' }} />
            <Tooltip
              content={
                <ChartTooltip
                  rowsByTime={rowsByTime}
                  fields={[
                    { key: 'actual', label: 'Actual', color: ACTUAL_COLOR },
                    { key: 'forecast', label: 'Forecast', color: FORECAST_COLOR },
                  ]}
                />
              }
            />
            <Legend />
            <Line type="linear" dataKey="actual" name="Actual (FUELHH wind)" stroke={ACTUAL_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line
              type="linear" data={forecastRows} dataKey="forecast" name="Forecast (WINDFOR)"
              stroke={FORECAST_COLOR} strokeWidth={2} isAnimationActive={false}
              dot={isolatedDot(forecastRows, 'forecast', FORECAST_COLOR)}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
