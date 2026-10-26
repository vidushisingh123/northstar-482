import { useEffect, useState } from 'react'
import { fetchDashboard } from '../api/dashboardApi'

const has = (value) => value !== null && value !== undefined

/**
 * Loads dashboard data whenever the date range changes.
 * Returns { status: 'loading' | 'error' | 'empty' | 'success', data, error, retry }.
 */
export function useDashboard({ start, end }) {
  const [reloadCount, setReloadCount] = useState(0)
  const [result, setResult] = useState(null)
  const requestKey = `${start}|${end}|${reloadCount}`

  useEffect(() => {
    const controller = new AbortController() // cancels the request if the user changes dates quickly
    fetchDashboard({ start, end }, controller.signal)
      .then((data) => setResult({ requestKey, data, error: null }))
      .catch((error) => {
        if (error.name === 'AbortError') return
        setResult({ requestKey, data: null, error: error.message })
      })
    return () => controller.abort()
  }, [start, end, requestKey])

  const retry = () => setReloadCount((count) => count + 1)

  // A result that belongs to an older request means we are still loading the new one.
  if (!result || result.requestKey !== requestKey) {
    return { status: 'loading', data: null, error: null, retry }
  }
  if (result.error) {
    return { status: 'error', data: null, error: result.error, retry }
  }
  const hasPoints = result.data.series.some((p) => has(p.forecast_mw) || has(p.actual_mw))
  return { status: hasPoints ? 'success' : 'empty', data: result.data, error: null, retry }
}