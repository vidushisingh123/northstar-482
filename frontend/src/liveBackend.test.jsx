// End-to-end check: the real App + real fetch against a RUNNING backend. Skipped unless LIVE_BACKEND is set.
// Git Bash:  LIVE_BACKEND=1 npx vitest run src/liveBackend.test.jsx
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('recharts', async (importOriginal) => (await import('./test/mockRecharts')).withFixedSize(importOriginal))

import App from './App'
import { API_BASE_URL } from './config'
import { formatMw, formatSignedMw } from './utils/format'

afterEach(cleanup)

describe.skipIf(!process.env.LIVE_BACKEND)('frontend <-> running backend', () => {
  it('shows exactly the KPI values the API returns for the default range', async () => {
    const api = await (await fetch(`${API_BASE_URL}/api/dashboard?start=2026-01-01&end=2026-01-07`)).json()
    render(<App />)
    expect(await screen.findByText('Forecast bias', {}, { timeout: 60000 })).toBeTruthy()

    const m = api.metrics
    expect(screen.getByText(formatSignedMw(m.bias_mw))).toBeTruthy()
    expect(screen.getByText(formatMw(m.mean_forecast_mw))).toBeTruthy()
    expect(screen.getByText(formatMw(m.mean_actual_mw))).toBeTruthy()
    const note = screen.getByRole('note').textContent
    expect(note).toContain(`${m.matched_intervals} compared intervals`)
    console.log(`UI matches API: matched=${m.matched_intervals}/${api.meta.intervals_forecastable} forecastable of ${api.meta.intervals_total} half-hours; bias=${m.bias_mw}, MAE=${m.mae_mw}, RMSE=${m.rmse_mw}`)
    expect(document.querySelectorAll('path.recharts-line-curve').length).toBe(3) // actual, forecast, error
  })
})
