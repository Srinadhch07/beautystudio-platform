/**
 * Public site shell and routing.
 *
 * The public website is the default at `/`, and the admin panel stays reachable
 * under `#/admin` so the existing Step 6 work keeps working. Hash routing is
 * retained deliberately: it needs no server rewrite rule, so the built site can
 * be dropped on any static host.
 */

import { useHashPath, useScrollToTop } from '@/lib/hash-route'
import { Footer } from './components/Footer'
import { Header } from './components/Header'
import { ErrorState, LoadingState } from './components/primitives'
import { AboutPage } from './pages/AboutPage'
import { ContactPage } from './pages/ContactPage'
import { GalleryPage } from './pages/GalleryPage'
import { HomePage } from './pages/HomePage'
import { OffersPage } from './pages/OffersPage'
import { ServicesPage } from './pages/ServicesPage'
import { TestimonialsPage } from './pages/TestimonialsPage'
import { SiteProvider, useSite } from './site-context'

export function Site() {
  return (
    <SiteProvider>
      <SiteFrame />
    </SiteProvider>
  )
}

function SiteFrame() {
  const { loading, error, config, reload } = useSite()
  const path = useHashPath()
  useScrollToTop(path)

  // A hard failure here means the business identity is unknown, so there is
  // nothing sensible to render beyond a retry.
  if (error !== null && config === null) {
    return (
      <div className="site-boot">
        <ErrorState title="We could not load the studio details" onRetry={reload}>
          Please refresh the page in a moment.
        </ErrorState>
      </div>
    )
  }

  return (
    <div className="site">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header path={path} />
      <main id="main" tabIndex={-1}>
        {loading && config === null ? (
          <div className="shell">
            <LoadingState label="Loading" />
          </div>
        ) : (
          <Routes path={path} />
        )}
      </main>
      <Footer />
    </div>
  )
}

function Routes({ path }: { path: string }) {
  switch (path) {
    case '/':
      return <HomePage />
    case '/services':
      return <ServicesPage />
    case '/gallery':
      return <GalleryPage />
    case '/about':
      return <AboutPage />
    case '/testimonials':
      return <TestimonialsPage />
    case '/offers':
      return <OffersPage />
    case '/contact':
      return <ContactPage />
    default:
      return (
        <div className="page">
          <div className="shell">
            <div className="not-found">
              <h1>Page not found</h1>
              <p>That page does not exist. Try the services list or head back home.</p>
              <a className="button button--primary" href="#/">
                Back to home
              </a>
            </div>
          </div>
        </div>
      )
  }
}