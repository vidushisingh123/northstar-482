// Vite exposes variables that start with VITE_ through import.meta.env.
// They are baked in when the dev server starts, so restart it after editing .env.local.
// An EMPTY value means "same origin" (used when one container serves both the API and the built page).
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')

// Temporary visual preview only. Never enable this when presenting real results.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// The assignment covers January 2026 only.
export const MIN_DATE = '2026-01-01'
export const MAX_DATE = '2026-01-31'
