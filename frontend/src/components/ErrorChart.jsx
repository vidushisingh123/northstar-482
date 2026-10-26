import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { forecastRowsOf } from '../utils/series'
import { formatAxisTick } from '../utils/format'
import Card from './Card'
import ChartTooltip from './ChartTooltip'
import { isolatedDot } from './isolatedDot.jsx'

const ERROR_COLOR = '#c0392b'

export default function ErrorChart({ rows, spanDays }) {
  const errorRows = useMemo(() => forecastRowsOf(rows), [rows])
  const rowsByTime = useMemo(() => new Map(rows.map((row) => [row.t, row])), [rows])

  return (
    <Card
      title="Forecast error over time"
      subtitle="Error = forecast − actual, in MW, for compared intervals only. Above 0 = over-forecast, below 0 = under-forecast. Gaps = no comparison possible."
    >
      <div className="chart-box chart-box-small">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e8ee" />
            <XAxis
              dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']}
              tickFormatter={(ms) => formatAxisTick(ms, spanDays)} minTickGap={48}
            />
            <YAxis tickFormatter={(v) => v.toLocaleString('en-GB')} label={{ value: 'MW', angle: -90, position: 'insideLeft' }} />
            <ReferenceLine y={0} stroke="#5b6b7b" />
            <Tooltip
              content={
                <ChartTooltip
                  rowsByTime={rowsByTime}
                  fields={[{ key: 'error', label: 'Error (forecast − actual)', signed: true, color: ERROR_COLOR }]}
                />
              }
            />
            <Line
              type="linear" data={errorRows} dataKey="error" name="Error" stroke={ERROR_COLOR}
              strokeWidth={1.5} isAnimationActive={false}
              dot={isolatedDot(errorRows, 'error', ERROR_COLOR)}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
