/**
 * Small presentational primitives shared by the public pages.
 *
 * Deliberately not styled after the admin dashboard: this is a marketing site,
 * so spacing, type scale and motion are tuned for reading rather than density.
 */

import type { ReactNode } from 'react'

import { useSite } from '../site-context'

/* ------------------------------------------------------------------ images */

/**
 * A CMS image with graceful degradation.
 *
 * Three states matter here: a real image, a CMS record with no image at all, and
 * a URL that fails to load. Both of the latter two render the same neutral
 * placeholder, so a missing asset never leaves a torn hole in a layout.
 */
export function CmsImage({
  src,
  alt,
  ratio = '4 / 3',
  className = '',
  eager = false,
}: {
  src?: string | null
  alt: string
  ratio?: string
  className?: string
  /** Set on the hero image so it loads immediately rather than lazily. */
  eager?: boolean
}) {
  return (
    <span className={`cms-image ${className}`} style={{ aspectRatio: ratio }}>
      {src === null || src === undefined || src === '' ? (
        <ImageFallback />
      ) : (
        <img
          src={src}
          alt={alt}
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          onError={(event) => {
            // Swap in the placeholder rather than leaving a broken-image icon.
            event.currentTarget.style.display = 'none'
            const parent = event.currentTarget.parentElement
            if (parent !== null && parent.dataset.fallback !== 'on') {
              parent.dataset.fallback = 'on'
              const placeholder = document.createElement('span')
              placeholder.className = 'cms-image__fallback'
              placeholder.setAttribute('aria-hidden', 'true')
              parent.appendChild(placeholder)
            }
          }}
        />
      )}
    </span>
  )
}

function ImageFallback() {
  return (
    <span className="cms-image__fallback" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.25">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <circle cx="9" cy="10" r="1.6" />
        <path d="M21 16l-5.5-5-4.5 4.5L8 13l-5 5" />
      </svg>
    </span>
  )
}

/* ---------------------------------------------------------------- headings */

export function SectionHeading({
  eyebrow,
  title,
  children,
  align = 'left',
}: {
  eyebrow?: string | null
  title: string
  children?: ReactNode
  align?: 'left' | 'center'
}) {
  return (
    <header className={`section-heading section-heading--${align}`}>
      {eyebrow !== null && eyebrow !== undefined && eyebrow !== '' ? (
        <p className="section-heading__eyebrow">{eyebrow}</p>
      ) : null}
      <h2>{title}</h2>
      {children === undefined ? null : <p className="section-heading__text">{children}</p>}
    </header>
  )
}

/* ------------------------------------------------------- async state views */

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state--empty">
      <h3>{title}</h3>
      {children === undefined ? null : <p>{children}</p>}
    </div>
  )
}

export function ErrorState({
  title = 'Something went wrong',
  children,
  onRetry,
}: {
  title?: string
  children?: ReactNode
  onRetry?: () => void
}) {
  return (
    <div className="state state--error" role="alert">
      <h3>{title}</h3>
      {children === undefined ? null : <p>{children}</p>}
      {onRetry === undefined ? null : (
        <button type="button" className="link-button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- buttons */

export function WhatsAppButton({
  message,
  children,
  variant = 'primary',
  className = '',
}: {
  /** Prefilled text, so the studio knows what is being asked about. */
  message?: string
  children: ReactNode
  variant?: 'primary' | 'solid' | 'ghost'
  className?: string
}) {
  const { whatsappLink } = useSite()
  const href = whatsappLink(message)

  if (href === null) return null

  return (
    <a
      className={`button button--wa button--${variant} ${className}`}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      <WhatsAppGlyph />
      <span>{children}</span>
    </a>
  )
}

export function WhatsAppGlyph() {
  return (
    <svg className="wa-glyph" viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
      <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.25-.46-2.38-1.47-.88-.78-1.47-1.75-1.65-2.05-.17-.3-.02-.46.13-.6.13-.14.3-.35.45-.53.15-.18.2-.3.3-.5.1-.2.05-.38-.02-.53-.08-.15-.67-1.6-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.47s1.06 2.86 1.21 3.06c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.72 2-1.41.25-.69.25-1.28.17-1.41-.07-.13-.27-.2-.57-.35M12.04 21.5h-.01c-1.75 0-3.48-.47-5.02-1.36l-.36-.21-3.12.82.83-3.04-.23-.37a9.86 9.86 0 0 1-1.51-5.26c0-5.45 4.44-9.89 9.9-9.89a9.8 9.8 0 0 1 6.97 2.9 9.8 9.8 0 0 1 2.89 6.99c0 5.45-4.45 9.89-9.9 9.89M20.46 3.49A11.8 11.8 0 0 0 12.04 0C5.46 0 .1 5.36.1 11.94c0 2.1.55 4.15 1.6 5.95L.1 24l6.25-1.64a11.9 11.9 0 0 0 5.68 1.45h.01c6.58 0 11.94-5.36 11.94-11.94a11.86 11.86 0 0 0-3.52-8.38" />
    </svg>
  )
}

/* --------------------------------------------------------------- filters */

/** A filter toggle. `aria-pressed` carries the selected state for screen readers. */
export function FilterChip({
  label,
  active,
  onSelect,
}: {
  label: string
  active: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={active ? 'filter-chip is-active' : 'filter-chip'}
      aria-pressed={active}
      onClick={onSelect}
    >
      {label}
    </button>
  )
}

/** Wraps chips in a labelled nav so the control set reads as one group. */
export function FilterRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <nav className="filters" aria-label={label}>
      {children}
    </nav>
  )
}

/* ---------------------------------------------------------------- stars */

export function Stars({ value, label }: { value: number; label?: string }) {
  return (
    <span className="stars" role="img" aria-label={label ?? `${value} out of 5`}>
      {[1, 2, 3, 4, 5].map((step) => (
        <svg
          key={step}
          viewBox="0 0 20 20"
          width="15"
          height="15"
          aria-hidden="true"
          className={step <= Math.round(value) ? 'star star--on' : 'star'}
        >
          <path
            d="M10 1.6l2.47 5.2 5.53.77-4 4.05.96 5.78L10 14.62l-4.96 2.78.96-5.78-4-4.05 5.53-.77z"
            fill="currentColor"
          />
        </svg>
      ))}
    </span>
  )
}
