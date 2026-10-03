/**
 * Social link row.
 *
 * The CMS stores a fixed set of platform URLs. Anything blank is skipped, and a
 * value is only rendered as a link once it parses as an http(s) URL, so a
 * malformed CMS entry cannot produce a broken or `javascript:` link.
 */

import type { ReactNode } from 'react'

import type { SocialLinks as SocialLinksValue } from '../types'

const PLATFORMS: { key: keyof SocialLinksValue; label: string; glyph: ReactNode }[] = [
  {
    key: 'instagram',
    label: 'Instagram',
    glyph: (
      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.2" cy="6.8" r="0.9" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    key: 'facebook',
    label: 'Facebook',
    glyph: (
      <svg viewBox="0 0 24 24" width="17" height="17" fill="currentColor">
        <path d="M14 8.5V6.9c0-.8.2-1.2 1.3-1.2H17V2.6h-2.6C11.4 2.6 10.4 4 10.4 6.5v2H8v3.2h2.4V21H14v-9.3h2.5l.4-3.2z" />
      </svg>
    ),
  },
  {
    key: 'twitter',
    label: 'X',
    glyph: (
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <path d="M17.5 3h3l-6.6 7.5L21.8 21h-5.9l-4-5.3L6.9 21H3.8l7-8L2.6 3h6l3.6 4.8zm-1 16h1.7L7.6 4.7H5.8z" />
      </svg>
    ),
  },
  {
    key: 'linkedin',
    label: 'LinkedIn',
    glyph: (
      <svg viewBox="0 0 24 24" width="17" height="17" fill="currentColor">
        <path d="M6.9 21H3.6V9h3.3zm-1.7-13.7A1.9 1.9 0 1 1 3.3 5.4a1.9 1.9 0 0 1 1.9 1.9M21 21h-3.3v-5.8c0-1.4 0-3.2-2-3.2s-2.2 1.5-2.2 3.1V21H10.2V9h3.2v1.6h.1a3.5 3.5 0 0 1 3.1-1.7c3.4 0 4 2.2 4 5.1z" />
      </svg>
    ),
  },
  {
    key: 'youtube',
    label: 'YouTube',
    glyph: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
        <path d="M22.5 7.4a2.8 2.8 0 0 0-1.9-2C18.9 5 12 5 12 5s-6.9 0-8.6.4a2.8 2.8 0 0 0-1.9 2A29 29 0 0 0 1.1 12a29 29 0 0 0 .4 4.6 2.8 2.8 0 0 0 1.9 2C5.1 19 12 19 12 19s6.9 0 8.6-.4a2.8 2.8 0 0 0 1.9-2 29 29 0 0 0 .4-4.6 29 29 0 0 0-.4-4.6M9.8 15.2V8.8l5.5 3.2z" />
      </svg>
    ),
  },
]

function isSafeUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export function SocialLinks({ links }: { links: SocialLinksValue | null | undefined }) {
  if (links === null || links === undefined) return null

  const usable = PLATFORMS.filter(({ key }) => {
    const value = links[key]
    return typeof value === 'string' && value !== '' && isSafeUrl(value)
  })

  if (usable.length === 0) return null

  return (
    <ul className="social-links" aria-label="Social media">
      {usable.map(({ key, label, glyph }) => (
        <li key={key}>
          <a
            href={links[key] as string}
            target="_blank"
            rel="noopener noreferrer me"
            aria-label={label}
          >
            {glyph}
          </a>
        </li>
      ))}
    </ul>
  )
}
