import { useMemo, useState } from 'react'
import DataQuality from './components/DataQuality'
import DateRangeForm from './components/DateRangeForm'
import ErrorChart from './components/ErrorChart'
import ForecastChart from './components/ForecastChart'
import KpiCards from './components/KpiCards'
import StatusPanel from './components/StatusPanel'
import { USE_MOCK } from './config'
import { useDashboard } from './hooks/useDashboard'
import { spanInDays, toChartRows } from './utils/series'

export default function App() {
  const [range, setRange] = useState({ start: '2026-01-01', end: '2026-01-07' })
  const { status, data, error, retry } = useDashboard(range)

  const rows = useMemo(() => (data ? toChartRows(data.series) : []), [data])
  const spanDays = spanInDays(rows)

  return (
    <>
      <header className="app-header">
        <div className="container">
          <h1>UK Wind Power Forecast Dashboard</h1>
          <p>
            National wind generation · forecast vs actual · Elexon BMRS (WINDFOR, FUELHH) ·
            half-hourly settlement intervals · MW
          </p>
        </div>
      </header>

      <main className="container">
        {USE_MOCK && (
          <div className="mock-banner" role="note">
            <strong>SAMPLE DATA.</strong> Synthetic values for a visual preview only. These are NOT real January 2026 figures.
          </div>
        )}

        <DateRangeForm value={range} onApply={setRange} />

        {status === 'loading' && <StatusPanel kind="loading" />}
        {status === 'error' && <StatusPanel kind="error" message={error} onRetry={retry} />}
        {status === 'empty' && <StatusPanel kind="empty" />}
        {status === 'success' && (
          <>
            <KpiCards metrics={data.metrics} meta={data.meta} />
            <ForecastChart rows={rows} spanDays={spanDays} forecastResolutionMinutes={data.meta.forecast_resolution_minutes} />
            <ErrorChart rows={rows} spanDays={spanDays} />
            <DataQuality meta={data.meta} metrics={data.metrics} />
          </>
        )}
      </main>
    </>
  )
}
