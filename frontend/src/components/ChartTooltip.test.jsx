import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import ChartTooltip from './ChartTooltip'

const T = Date.parse('2026-01-02T10:30:00Z')
const rowsByTime = new Map([
  [T, { t: T, actual: 12000, forecast: null, error: null, forecastExpected: false }],
  [T + 1800000, { t: T + 1800000, actual: 12100, forecast: 14000, error: 1900, forecastExpected: true }],
  [T + 3600000, { t: T + 3600000, actual: 12200, forecast: null, error: null, forecastExpected: true }],
])
const fields = [
  { key: 'actual', label: 'Actual' },
  { key: 'forecast', label: 'Forecast' },
  { key: 'error', label: 'Error', signed: true },
]

it('explains that an hourly dataset has no forecast at this half-hour', () => {
  render(<ChartTooltip active label={T} payload={[]} rowsByTime={rowsByTime} fields={fields} />)
  // both the Forecast row and the Error row explain the by-design gap
  expect(screen.getAllByText(/no forecast at this time \(hourly dataset\)/i)).toHaveLength(2)
})

it('shows values with units and a signed error', () => {
  render(<ChartTooltip active label={T + 1800000} payload={[]} rowsByTime={rowsByTime} fields={fields} />)
  expect(screen.getByText(/14,000 MW/)).toBeTruthy()
  expect(screen.getByText(/\+1,900 MW/)).toBeTruthy()
})

it('marks a genuinely missing forecast differently from a by-design gap', () => {
  render(<ChartTooltip active label={T + 3600000} payload={[]} rowsByTime={rowsByTime} fields={fields} />)
  expect(screen.getAllByText(/missing \(no eligible forecast\)/).length).toBeGreaterThan(0)
})

it('renders nothing when inactive', () => {
  const { container } = render(<ChartTooltip active={false} rowsByTime={rowsByTime} fields={fields} />)
  expect(container.firstChild).toBeNull()
})
