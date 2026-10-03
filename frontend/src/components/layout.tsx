import { useState } from 'react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui'
import { CreatorSignature } from '@/components/CreatorSignature'
import { useAuth } from '@/lib/auth'

export type RouteName =
  | 'dashboard'
  | 'settings'
  | 'services'
  | 'gallery'
  | 'testimonials'
  | 'offers'

interface NavItem {
  route: RouteName
  label: string
  icon: string
  group?: string
}

/** A single flat list: the panel has six sections, so a group taxonomy is noise. */
const NAV: NavItem[] = [
  { route: 'dashboard', label: 'Dashboard', icon: '◈' },
  { route: 'settings', label: 'Site settings', icon: '⚙' },
  { route: 'services', label: 'Services', icon: '✦' },
  { route: 'gallery', label: 'Gallery & media', icon: '▣' },
  { route: 'testimonials', label: 'Testimonials', icon: '❞' },
  { route: 'offers', label: 'Offers', icon: '◷' },
]

export function Layout({
  route,
  onNavigate,
  pendingCount,
  children,
}: {
  route: RouteName
  onNavigate: (route: RouteName) => void
  /** Unreviewed testimonial count, surfaced as a nav badge. */
  pendingCount: number
  children: ReactNode
}) {
  const { admin, signOut } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)

  const current = NAV.find((item) => item.route === route)

  const go = (next: RouteName) => {
    onNavigate(next)
    setMenuOpen(false)
  }

  const onSignOut = async () => {
    setSigningOut(true)
    try {
      await signOut()
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <div className="admin-shell">
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} role="presentation" />}

      <aside className={menuOpen ? 'sidebar sidebar--open' : 'sidebar'}>
        <div className="sidebar__brand">
          <div className="sidebar__mark">BP</div>
          <div>
            <strong>{admin?.name ?? 'Admin'}</strong>
            <span>Admin panel</span>
          </div>
        </div>

        <nav>
          {NAV.map((item) => (
            <button
              key={item.route}
              type="button"
              className={
                item.route === route ? 'nav-link nav-link--active' : 'nav-link'
              }
              onClick={() => go(item.route)}
              aria-current={item.route === route ? 'page' : undefined}
            >
              <span className="nav-link__icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
              {item.route === 'testimonials' && pendingCount > 0 && (
                <span className="nav-link__badge">{pendingCount}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar__foot">
          <Button
            variant="secondary"
            onClick={onSignOut}
            busy={signingOut}
            disabled={signingOut}
          >
            Sign out
          </Button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <Button
            variant="ghost"
            className="menu-toggle"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label="Toggle navigation"
          >
            ☰
          </Button>
          <span className="topbar__title">{current?.label ?? 'Admin'}</span>
          <span className="topbar__spacer" />
          <span className="topbar__user">{admin?.email}</span>
        </header>

        <main className="content">{children}</main>

        <footer className="admin-footer">
          <CreatorSignature />
        </footer>
      </div>
    </div>
  )
}
