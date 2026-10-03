/**
 * Date and formatting helpers shared by the admin screens.
 *
 * Separate from `components/ui.tsx` so that file only exports components, which
 * keeps React Fast Refresh working while editing a screen.
 */

export function formatDate(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/** `datetime-local` wants `YYYY-MM-DDTHH:mm` in *local* time. */
export function toDateTimeLocal(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

/** The inverse, as the ISO string the API expects. */
export function fromDateTimeLocal(value: string): string | null {
  if (value === '') return null
  return new Date(value).toISOString()
}
