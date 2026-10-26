import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('recharts', async (importOriginal) => (await import('./test/mockRecharts')).withFixedSize(importOriginal))

import App from './App'
import { makePayload } from './test/payloads'

const okResponse = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) })
const errResponse = (status, detail) => Promise.resolve({ ok: false, status, json: () => Promise.resolve({ detail }) })
const paramsOf = (call) => Object.fromEntries(new URL(call[0]).searchParams)

let fetchMock
beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

// Offset 2000 for the default week, 500 for any other range, so KPIs visibly change.
const answerByRange = (url) => {
  const q = Object.fromEntries(new URL(url).searchParams)
  const isDefault = q.start === '2026-01-01' && q.end === '2026-01-07'
  return okResponse(makePayload({ start: q.start, end: q.end, offset: isDefault ? 2000 : 500 }))
}

describe('loading real data', () => {
  it('requests the default week from the configured API and shows KPIs from the response', async () => {
    fetchMock.mockImplementation(answerByRange)
    render(<App />)
    expect(screen.getByRole('status')).toBeTruthy() // loading state first
    expect(await screen.findByText('+2,000 MW')).toBeTruthy() // bias
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toMatch(/^http:\/\/127\.0\.0\.1:8000\/api\/dashboard\?/)
    expect(paramsOf(fetchMock.mock.calls[0])).toEqual({ start: '2026-01-01', end: '2026-01-07' })
    expect(screen.getAllByText('2,000 MW').length).toBeGreaterThanOrEqual(2) // MAE and RMSE
    expect(screen.queryByText(/SAMPLE DATA/)).toBeNull()
  })

  it('explains hourly coverage: 168 of 168 forecast intervals compared, 336 half-hours in range', async () => {
    fetchMock.mockImplementation(answerByRange)
    render(<App />)
    const note = await screen.findByRole('note')
    expect(note.textContent).toMatch(/168 compared intervals out of 168 where a forecast can exist \(100%\)/)
    expect(note.textContent).toMatch(/of 336 half-hour intervals, 168 have no forecast by design/)
    expect(screen.getByText('Hourly (WINDFOR)')).toBeTruthy()
  })
})

describe('date range controls', () => {
  it('preset "25–31 Jan" requests the whole last day (inclusive end) and updates the KPIs', async () => {
    fetchMock.mockImplementation(answerByRange)
    render(<App />)
    await screen.findByText('+2,000 MW')
    fireEvent.click(screen.getByRole('button', { name: '25–31 Jan' }))
    expect(await screen.findByText('+500 MW')).toBeTruthy()
    expect(screen.queryByText('+2,000 MW')).toBeNull()
    expect(paramsOf(fetchMock.mock.calls.at(-1))).toEqual({ start: '2026-01-25', end: '2026-01-31' })
  })

  it('preset "Full month" requests 1-31 Jan', async () => {
    fetchMock.mockImplementation(answerByRange)
    render(<App />)
    await screen.findByText('+2,000 MW')
    fireEvent.click(screen.getByRole('button', { name: 'Full month' }))
    await waitFor(() => expect(paramsOf(fetchMock.mock.calls.at(-1))).toEqual({ start: '2026-01-01', end: '2026-01-31' }))
    await screen.findByText('+500 MW')
  })

  it('manual dates are sent on Update; an invalid range is blocked with no request', async () => {
    fetchMock.mockImplementation(answerByRange)
    render(<App />)
    await screen.findByText('+2,000 MW')
    const calls = fetchMock.mock.calls.length

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-01-20' } })
    fireEvent.change(screen.getByLabelText('To (inclusive)'), { target: { value: '2026-01-10' } })
    expect(screen.getByRole('alert').textContent).toMatch(/start date must be on or before/i)
    expect(screen.getByRole('button', { name: 'Update' }).disabled).toBe(true)
    expect(fetchMock.mock.calls.length).toBe(calls)

    fireEvent.change(screen.getByLabelText('To (inclusive)'), { target: { value: '2026-01-22' } })
    fireEvent.click(screen.getByRole('button', { name: 'Update' }))
    await waitFor(() => expect(paramsOf(fetchMock.mock.calls.at(-1))).toEqual({ start: '2026-01-20', end: '2026-01-22' }))
  })
})

describe('failures are shown, never replaced by sample data', () => {
  it('shows the backend error message for an upstream failure (HTTP 502)', async () => {
    fetchMock.mockImplementation(() => errResponse(502, 'Elexon API timed out after 3 attempts'))
    render(<App />)
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/HTTP 502/)
    expect(alert.textContent).toMatch(/timed out after 3 attempts/)
    expect(screen.queryByText('Key metrics')).toBeNull()
    expect(screen.queryByText(/SAMPLE DATA/)).toBeNull()
    expect(screen.queryByText('MAE')).toBeNull()
  })

  it('shows a clear message when the backend is unreachable', async () => {
    fetchMock.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')))
    render(<App />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/Could not reach the API at http:\/\/127\.0\.0\.1:8000/)
  })

  it('shows the empty state when the API returns no values at all', async () => {
    const empty = makePayload({ start: '2026-01-01', end: '2026-01-01' })
    empty.series.forEach((p) => { p.forecast_mw = null; p.actual_mw = null; p.error_mw = null })
    fetchMock.mockImplementation(() => okResponse(empty))
    render(<App />)
    expect(await screen.findByText('No data for this period')).toBeTruthy()
  })

  it('warns about incomplete coverage when forecasts are genuinely missing', async () => {
    const hours = []
    for (let h = 0; h < 24 * 7; h += 2) hours.push(new Date(Date.parse('2026-01-01T00:00:00Z') + h * 3600000).toISOString())
    fetchMock.mockImplementation(() => okResponse(makePayload({ dropHours: hours })))
    render(<App />)
    const note = await screen.findByRole('note')
    expect(note.className).toMatch(/coverage-warn/)
    expect(note.textContent).toMatch(/84 forecast intervals had no eligible forecast/)
    expect(note.textContent).toMatch(/Coverage is incomplete/)
  })
})
