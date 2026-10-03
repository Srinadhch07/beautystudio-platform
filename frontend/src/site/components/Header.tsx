/**
 * Public site header and mobile navigation.
 *
 * One nav definition drives the desktop bar, the mobile sheet and the footer, so
 * the routes cannot drift apart. The mobile sheet is a real dialog: focus is
 * moved into it, Escape closes it, and background scroll is locked while open.
 */
import { useEffect, useRef, useState } from 'react'

import { useSite } from '../site-context'
import { NAV } from '../nav'
import { WhatsAppButton } from './primitives'

export function Header({ path }: { path: string }) {
  const { config } = useSite()
  // The sheet records which route opened it, so navigating away closes it as a
  // derived consequence rather than through an effect.
  const [openFor, setOpenFor] = useState<string | null>(null)
  const open = openFor === path
  const sheetRef = useRef<HTMLDivElement>(null)
  const toggleRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    sheetRef.current?.querySelector<HTMLAnchorElement>('a')?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenFor(null)
        toggleRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previous
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const name = config?.identity.business_name ?? ''

  return (
    <header className="site-header">
      <div className="site-header__inner shell">
        <a className="site-header__brand" href="#/">
          {config?.identity.logo ? (
            <img src={config.identity.logo} alt="" width="34" height="34" />
          ) : (
            <span className="site-header__mark" aria-hidden="true">
              {name.slice(0, 1).toUpperCase()}
            </span>
          )}
          <span className="site-header__name">{name}</span>
        </a>

        <nav className="site-header__nav" aria-label="Main">
          {NAV.map((route) => (
            <a
              key={route.path}
              href={`#${route.path}`}
              className={path === route.path ? 'is-current' : ''}
              aria-current={path === route.path ? 'page' : undefined}
            >
              {route.label}
            </a>
          ))}
        </nav>

        <div className="site-header__actions">
          <WhatsAppButton variant="solid" message={defaultEnquiry()}>
            <span className="site-header__cta-full">Book on WhatsApp</span>
            <span className="site-header__cta-short">WhatsApp</span>
          </WhatsAppButton>
          <button
            ref={toggleRef}
            type="button"
            className="site-header__toggle"
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpenFor(open ? null : path)}
          >
            <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
            <span className={`burger ${open ? 'burger--open' : ''}`} aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </button>
        </div>
      </div>

      {open ? (
        <>
          <div className="nav-scrim" onClick={() => setOpenFor(null)} aria-hidden="true" />
          <div
            ref={sheetRef}
            id="mobile-nav"
            className="nav-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Site menu"
          >
            <nav className="nav-sheet__nav" aria-label="Mobile">
              {NAV.map((route) => (
                <a
                  key={route.path}
                  href={`#${route.path}`}
                  className={path === route.path ? 'is-current' : ''}
                  aria-current={path === route.path ? 'page' : undefined}
                >
                  {route.label}
                </a>
              ))}
            </nav>
            <WhatsAppButton message={defaultEnquiry()}>Book on WhatsApp</WhatsAppButton>
          </div>
        </>
      ) : null}
    </header>
  )
}

function defaultEnquiry(): string {
  return "Hi, I'd like to enquire about your services."
}
