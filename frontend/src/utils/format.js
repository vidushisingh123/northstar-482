// January in the UK is GMT (= UTC), but we format in Europe/London so the code stays correct.
const LONDON = 'Europe/London'

const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
})
const timeFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: LONDON, hour: '2-digit', minute: '2-digit', hour12: false,
})
const dayFormat = new Intl.DateTimeFormat('en-GB', { timeZone: LONDON, day: 'numeric', month: 'short' })

const isMissing = (value) => value === null || value === undefined || Number.isNaN(value)

export function formatNumber(value, digits = 0) {
  if (isMissing(value)) return '—'
  return value.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function formatMw(value, digits = 0) {
  return isMissing(value) ? '—' : `${formatNumber(value, digits)} MW`
}

export function formatSignedMw(value, digits = 0) {
  if (isMissing(value)) return '—'
  return `${value > 0 ? '+' : ''}${formatNumber(value, digits)} MW`
}

export function formatDateTime(ms) {
  return dateTimeFormat.format(ms)
}

// Short ranges show clock times on the axis; longer ranges show dates.
export function formatAxisTick(ms, spanDays) {
  return spanDays <= 2 ? timeFormat.format(ms) : dayFormat.format(ms)
}