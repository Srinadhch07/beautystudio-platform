/**
 * Typed access to the public (browser-visible) environment.
 *
 * Vite only exposes variables prefixed with `VITE_`. Secrets such as AWS keys,
 * JWT secrets or the MongoDB connection string live in the backend `.env` and
 * must never be added here.
 */
const raw = import.meta.env

function normaliseBaseUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, '')
  return trimmed === '' ? '' : trimmed
}

/**
 * Base for all versioned API traffic.
 *
 * The backend mounts its API at `<api_prefix>/v1` (see `app/main.py`), so this
 * must include the version segment. Health is the single exception, mounted at
 * the unversioned prefix, and `apiRoot` below is derived from this value rather
 * than configured separately so the two can never drift apart.
 */
const apiBaseUrl = normaliseBaseUrl(raw.VITE_API_BASE_URL ?? '/api/v1')

export const env = {
  appName: raw.VITE_APP_NAME?.trim() || 'Beauty Parlour',
  apiBaseUrl,
  apiRoot: apiBaseUrl.replace(/\/v1$/, ''),
  isDevelopment: raw.DEV,
  isProduction: raw.PROD,
} as const

export type Env = typeof env
