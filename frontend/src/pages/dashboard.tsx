import { api } from '@/lib/api'
import { useAsync } from '@/lib/hooks'
import { Banner, Card, EmptyState, PageHeader, Spinner } from '@/components/ui'
import type { RouteName } from '@/components/layout'
import type { SiteSettings } from '@/types/api'

interface Counts {
  services: number
  activeServices: number
  offers: number
  activeOffers: number
  gallery: number
  pendingTestimonials: number
}

export function DashboardPage({ onNavigate }: { onNavigate: (route: RouteName) => void }) {
  // One request per collection. They are independent, so they are fired together
  // rather than chained.
  const services = useAsync(() => api.services.list({ limit: 200 }), [])
  const offers = useAsync(() => api.offers.list({ limit: 200 }), [])
  const gallery = useAsync(() => api.gallery.list({ limit: 200 }), [])
  const testimonials = useAsync(() => api.testimonials.list({ limit: 200 }), [])
  const settings = useAsync(() => api.settings.read(), [])

  const loading = [services, offers, gallery, testimonials].some((state) => state.loading)
  const failure = [services, offers, gallery, testimonials, settings].find(
    (state) => state.error !== null,
  )?.error

  if (loading) return <Spinner label="Loading dashboard" />
  if (failure !== undefined) return <Banner tone="error">{failure}</Banner>

  const counts: Counts = {
    services: services.data?.total ?? 0,
    activeServices: (services.data?.items ?? []).filter((item) => item.is_active).length,
    offers: offers.data?.total ?? 0,
    activeOffers: (offers.data?.items ?? []).filter((item) => item.is_active).length,
    gallery: gallery.data?.total ?? 0,
    pendingTestimonials: (testimonials.data?.items ?? []).filter(
      (item) => item.status === 'pending',
    ).length,
  }

  const recent = (testimonials.data?.items ?? [])
    .filter((item) => item.status === 'pending')
    .slice(0, 5)

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="An overview of your parlour content."
      />

      <div className="stat-grid">
        <Stat
          label="Services"
          value={`${counts.activeServices}/${counts.services}`}
          hint="active"
          onClick={() => onNavigate('services')}
        />
        <Stat
          label="Offers"
          value={`${counts.activeOffers}/${counts.offers}`}
          hint="active"
          onClick={() => onNavigate('offers')}
        />
        <Stat
          label="Gallery items"
          value={counts.gallery}
          onClick={() => onNavigate('gallery')}
        />
        <Stat
          label="Awaiting review"
          value={counts.pendingTestimonials}
          tone={counts.pendingTestimonials > 0 ? 'warning' : 'default'}
          onClick={() => onNavigate('testimonials')}
        />
      </div>

      <Card
        title="Site"
        description="Identity, contact details and the active theme and font."
        footer={
          <button type="button" className="btn btn--secondary" onClick={() => onNavigate('settings')}>
            Edit site settings
          </button>
        }
      >
        <SiteSummary settings={settings.data} />
      </Card>

      <Card
        title="Testimonials awaiting review"
        description="Customers cannot see a testimonial until you approve it."
        footer={
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => onNavigate('testimonials')}
          >
            Moderate testimonials
          </button>
        }
      >
        {recent.length === 0 ? (
          <EmptyState
            title="Nothing to review"
            description="New customer submissions will appear here."
          />
        ) : (
          <div className="stack">
            {recent.map((item) => (
              <div key={item.id} className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <strong>{item.customer_name}</strong>
                  <span className="muted"> · {item.rating}/5</span>
                  <p className="muted">{item.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  )
}

function Stat({
  label,
  value,
  hint,
  tone = 'default',
  onClick,
}: {
  label: string
  value: number | string
  hint?: string
  tone?: 'default' | 'warning'
  onClick: () => void
}) {
  return (
    <button type="button" className="stat" onClick={onClick} style={{ textAlign: 'left' }}>
      <div
        className="stat__value"
        style={tone === 'warning' ? { color: 'var(--warning)' } : undefined}
      >
        {value}
      </div>
      <div className="stat__label">
        {label}
        {hint !== undefined ? ` (${hint})` : ''}
      </div>
    </button>
  )
}

function SiteSummary({ settings }: { settings: SiteSettings | null }) {
  if (settings === null) return <p className="muted">Settings unavailable.</p>
  return (
    <div className="grid grid--3">
      <Detail label="Business" value={settings.business_name} />
      <Detail label="Theme" value={settings.active_theme ?? '—'} />
      <Detail label="Font" value={settings.active_font ?? '—'} />
      <Detail label="Phone" value={settings.phone ?? '—'} />
      <Detail label="Email" value={settings.email ?? '—'} />
      <Detail
        label="Address"
        value={
          [settings.address?.city, settings.address?.state].filter(Boolean).join(', ') || '—'
        }
      />
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="stat__label">{label}</div>
      <div>{value}</div>
    </div>
  )
}
