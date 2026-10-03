/**
 * Formatting helpers for the public site.
 *
 * Shared so the same value never renders two different ways: the address block
 * appears in the footer, the home summary and the contact page, and the price
 * appears on the services, offers and home pages.
 */

import type { Address, PublicOffer } from './types'

/** Joins the populated address parts into a single line. */
export function formatAddress(address: Address): string {
  return [
    address.line1,
    address.line2,
    address.city,
    address.state,
    address.postal_code,
    address.country,
  ]
    .filter((part) => part !== null && part !== undefined && part !== '')
    .join(', ')
}

/**
 * Builds a maps link.
 *
 * The CMS stores a postal address with no coordinates, so this is a search link
 * rather than a pin. Switching to a real pin would need a latitude/longitude
 * field, which does not exist in the backend yet.
 */
export function buildMapLink(address: Address): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(formatAddress(address))}`
}

/**
 * Formats a price.
 *
 * Prices arrive as decimal strings, never numbers, so nothing here can introduce
 * float rounding. The CMS has no currency field, so no symbol is invented; a
 * symbol already present in the stored value is preserved.
 */
export function formatMoney(value: string): string {
  const trimmed = value.trim()
  if (trimmed === '') return ''

  const match = /^([^0-9]*)(.*)$/.exec(trimmed)
  const symbol = match?.[1]?.trim() ?? ''
  const digits = match?.[2] ?? trimmed
  const [whole = '', fraction] = digits.split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')

  return `${symbol}${grouped}${fraction === undefined ? '' : `.${fraction}`}`
}

export function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

/** Strips formatting from a phone number for a `tel:` link. */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, '')}`
}

/**
 * Whether an offer is bookable now.
 *
 * Mirrors the backend's window logic so the badge a customer sees matches the
 * filter the admin sees. An offer with no dates is always live.
 */
export function offerWindow(offer: PublicOffer): { label: string; tone: 'live' | 'soon' | 'over' } {
  const now = Date.now()
  const from = offer.valid_from ? new Date(offer.valid_from).getTime() : null
  const until = offer.valid_until ? new Date(offer.valid_until).getTime() : null

  if (from !== null && Number.isFinite(from) && now < from) {
    return { label: 'Coming soon', tone: 'soon' }
  }
  if (until !== null && Number.isFinite(until) && now > until) {
    return { label: 'Expired', tone: 'over' }
  }
  return { label: 'Available now', tone: 'live' }
}
