import { API_BASE_URL, USE_MOCK } from '../config'
import { buildMockDashboard } from './mockData'

/**
 * Fetch the dashboard payload for a date range.
 * Backend endpoint: GET /api/dashboard?start=YYYY-MM-DD&end=YYYY-MM-DD
 * Real failures are always shown as errors; this function never falls back to mock data.
 */
export async function fetchDashboard({ start, end }, signal) {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 400)) // pretend to be a network call
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    return buildMockDashboard(start, end)
  }

  const query = new URLSearchParams({ start, end })
  const url = `${API_BASE_URL}/api/dashboard?${query}`
  const where = API_BASE_URL || 'this site'

  let response
  try {
    response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error(
      `Could not reach the API at ${where}. Check that the backend is running ` +
        'and that VITE_API_BASE_URL points at it.',
    )
  }

  if (response.status === 404) {
    throw new Error(
      `GET /api/dashboard was not found at ${where}. Restart the backend so it loads the latest code.`,
    )
  }
  if (!response.ok) {
    let detail = ''
    try {
      const body = await response.json()
      if (body.detail) {
        detail = ` - ${typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)}`
      }
    } catch {
      // response had no JSON body; ignore
    }
    throw new Error(`The API returned HTTP ${response.status}${detail}`)
  }

  const data = await response.json()
  if (!data || !Array.isArray(data.series) || !data.metrics || !data.meta) {
    throw new Error('The API response does not match the expected schema (meta, metrics, series).')
  }
  return data
}
