/**
 * Application root.
 *
 * One bundle serves both audiences. The public website is the default at `/`,
 * and the admin panel lives under `/admin`, so the studio's customers never load
 * the admin shell or make an authenticated `/auth/me` request.
 *
 * Both apps use hash routing rather than a router dependency: the whole thing is
 * a static bundle, so hash routes need no server rewrite rule. The admin
 * reset-password screen is the one screen rendered outside the admin layout,
 * because the requester has no session.
 */

import { useCallback, useEffect, useState } from 'react'

import { Layout } from '@/components/layout'
import type { RouteName } from '@/components/layout'
import { Spinner } from '@/components/ui'
import { AuthProvider, useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/hooks'
import { useHashPath } from '@/lib/hash-route'
import { DashboardPage } from '@/pages/dashboard'
import { ForgotPasswordPage, LoginPage, ResetPasswordPage } from '@/pages/auth'
import { GalleryPage } from '@/pages/gallery'
import { OffersPage } from '@/pages/offers'
import { ServicesPage } from '@/pages/services'
import { SiteSettingsPage } from '@/pages/site-settings'
import { TestimonialsPage } from '@/pages/testimonials'
import { ADMIN_PREFIX, isAdminRoute } from '@/site/routes'
import { Site } from '@/site/Site'
import { env } from '@/lib/env'

const ROUTES: RouteName[] = [
  'dashboard',
  'settings',
  'services',
  'gallery',
  'testimonials',
  'offers',
]

/** Reads the admin section out of `/admin/<section>`. */
function readRoute(): RouteName {
  const path = window.location.hash.replace(/^#/, '').replace(/[?].*$/, '')
  const section = path.startsWith(`${ADMIN_PREFIX}/`) ? path.slice(ADMIN_PREFIX.length + 1) : ''
  return (ROUTES as string[]).includes(section) ? (section as RouteName) : 'dashboard'
}

function AdminApp() {
  const { admin, initialising } = useAuth()
  const [route, setRoute] = useState<RouteName>(readRoute)
  const [authView, setAuthView] = useState<'login' | 'forgot'>('login')

  useEffect(() => {
    document.title = `${env.appName} · Admin`
  }, [])

  // Hash changes (including the browser's back button) drive navigation.
  useEffect(() => {
    const onHashChange = () => setRoute(readRoute())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const navigate = useCallback((next: RouteName) => {
    window.location.hash = `${ADMIN_PREFIX}/${next}`
    setRoute(next)
  }, [])

  // Drives the "awaiting review" badge in the sidebar.
  const pending = useAsync(
    () => (admin === null ? Promise.resolve(null) : api.testimonials.list({ status: 'pending', limit: 1 })),
    [admin?.id],
  )

  if (initialising) {
    return (
      <div className="auth">
        <Spinner label="Checking your session" />
      </div>
    )
  }

  // A reset link is honoured whether or not there is an active session.
  const resetToken = new URLSearchParams(window.location.search).get('reset_token')
  if (resetToken !== null && resetToken !== '') {
    return (
      <ResetPasswordPage
        token={resetToken}
        onDone={() => {
          window.history.replaceState({}, '', window.location.pathname)
          setAuthView('login')
        }}
      />
    )
  }

  if (admin === null) {
    return authView === 'forgot' ? (
      <ForgotPasswordPage onBack={() => setAuthView('login')} />
    ) : (
      <LoginPage onForgot={() => setAuthView('forgot')} />
    )
  }

  return (
    <Layout
      route={route}
      onNavigate={navigate}
      pendingCount={pending.data?.total ?? 0}
    >
      {route === 'dashboard' && <DashboardPage onNavigate={navigate} />}
      {route === 'settings' && <SiteSettingsPage />}
      {route === 'services' && <ServicesPage />}
      {route === 'gallery' && <GalleryPage />}
      {route === 'testimonials' && <TestimonialsPage />}
      {route === 'offers' && <OffersPage />}
    </Layout>
  )
}

export default function App() {
  const path = useHashPath()

  // The public site owns its own document title, from the CMS business name.
  return isAdminRoute(path) ? (
    <AuthProvider>
      <AdminApp />
    </AuthProvider>
  ) : (
    <Site />
  )
}
