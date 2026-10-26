import { useState } from 'react'
import { MAX_DATE, MIN_DATE } from '../config'

const PRESETS = [
  { label: 'Full month', start: MIN_DATE, end: MAX_DATE },
  { label: '1–7 Jan', start: '2026-01-01', end: '2026-01-07' },
  { label: '25–31 Jan', start: '2026-01-25', end: '2026-01-31' },
]

function validate(start, end) {
  if (!start || !end) return 'Choose both a start and an end date.'
  if (start < MIN_DATE || end > MAX_DATE) return 'Dates must be within January 2026.'
  if (start > end) return 'The start date must be on or before the end date.'
  return ''
}

export default function DateRangeForm({ value, onApply }) {
  const [start, setStart] = useState(value.start)
  const [end, setEnd] = useState(value.end)
  const problem = validate(start, end)

  function handleSubmit(event) {
    event.preventDefault()
    if (!problem) onApply({ start, end })
  }

  function applyPreset(preset) {
    setStart(preset.start)
    setEnd(preset.end)
    onApply({ start: preset.start, end: preset.end })
  }

  return (
    <form className="range-form card" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="start">From</label>
        <input id="start" type="date" min={MIN_DATE} max={MAX_DATE} value={start}
          onChange={(e) => setStart(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="end">To (inclusive)</label>
        <input id="end" type="date" min={MIN_DATE} max={MAX_DATE} value={end}
          onChange={(e) => setEnd(e.target.value)} />
      </div>
      <button type="submit" className="btn" disabled={Boolean(problem)}>Update</button>
      <div className="presets">
        {PRESETS.map((preset) => (
          <button key={preset.label} type="button" className="btn btn-ghost" onClick={() => applyPreset(preset)}>
            {preset.label}
          </button>
        ))}
      </div>
      {problem && <p className="form-problem" role="alert">{problem}</p>}
    </form>
  )
}