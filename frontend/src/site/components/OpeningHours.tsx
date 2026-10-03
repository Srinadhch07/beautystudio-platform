/**
 * Opening hours rendering, shared by the contact page and the footer.
 *
 * Closed days are still shown, so a visitor can tell "closed" from "not listed".
 */

import type { OpeningHour } from '../types'

const DAY_ORDER = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const

const DAY_LABELS: Record<string, string> = {  monday: 'Monday',
  tuesday: 'Tuesday',
  wednesday: 'Wednesday',
  thursday: 'Thursday',
  friday: 'Friday',
  saturday: 'Saturday',
  sunday: 'Sunday',
}

/** Formats a `HH:MM` 24-hour value as a friendly 12-hour label. */
function displayTime(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
  const [hourText, minuteText] = value.split(':')
  const hour = Number(hourText)
  if (Number.isNaN(hour)) return value
  const suffix = hour >= 12 ? 'pm' : 'am'
  const twelve = hour % 12 === 0 ? 12 : hour % 12
  const minutes = minuteText === undefined || minuteText === '' ? '' : `:${minuteText}`
  return `${twelve}${minutes} ${suffix}`
}

function range(hour: OpeningHour): string {
  const from = displayTime(hour.open_time)
  const to = displayTime(hour.close_time)
  if (from === '' && to === '') return 'Closed'
  if (from === '') return `Until ${to}`
  if (to === '') return `From ${from}`
  return `${from} – ${to}`
}

export function OpeningHoursList({ hours }: { hours: OpeningHour[] }) {
  const byDay = new Map(hours.map((hour) => [hour.day, hour]))
  const ordered = DAY_ORDER.map((day) => byDay.get(day)).filter(
    (hour): hour is OpeningHour => hour !== undefined,
  )
  // Keep any day the CMS holds that is not in the canonical order, rather than
  // silently dropping it.
  const extras = hours.filter(
    (hour) => !(DAY_ORDER as readonly string[]).includes(hour.day),
  )

  return (
    <dl className="hours-list">
      {[...ordered, ...extras].map((hour) => (
        <div key={hour.day} className={hour.is_closed ? 'is-closed' : ''}>
          <dt>{DAY_LABELS[hour.day] ?? hour.day}</dt>
          <dd>{range(hour)}</dd>
        </div>
      ))}
    </dl>
  )
}
