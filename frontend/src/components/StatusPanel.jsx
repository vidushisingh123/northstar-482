export default function StatusPanel({ kind, message, onRetry }) {
  if (kind === 'loading') {
    return (
      <div className="status" role="status">
        <div className="spinner" aria-hidden="true" />
        <p>Loading wind generation data…</p>
      </div>
    )
  }
  if (kind === 'error') {
    return (
      <div className="status status-error" role="alert">
        <h2>Could not load dashboard data</h2>
        <p>{message}</p>
        <button type="button" className="btn" onClick={onRetry}>Try again</button>
      </div>
    )
  }
  return (
    <div className="status">
      <h2>No data for this period</h2>
      <p>The API responded, but returned no half-hourly intervals for the selected dates. Try another range.</p>
    </div>
  )
}