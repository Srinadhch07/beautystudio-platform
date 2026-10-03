/**
 * Services page.
 *
 * Services are grouped by category because that is how a guest actually browses,
 * with an uncategorised group for anything left blank in the CMS.
 */

import { useMemo, useState } from 'react'

import { publicApi } from '../api'
import { useAsync } from '@/lib/hooks'
import type { PublicService } from '../types'
import { ServiceCard } from '../components/cards'
import {
  EmptyState,
  ErrorState,
  FilterChip,
  FilterRow,
  LoadingState,
} from '../components/primitives'

type Filter = 'all' | string

export function ServicesPage() {
  const services = useAsync(() => publicApi.services(), [])
  const [filter, setFilter] = useState<Filter>('all')

  const published = useMemo(
    () => (services.data?.items ?? []).filter((service) => service.is_active),
    [services.data],
  )

  const categories = useMemo(() => {
    const found: string[] = []
    for (const service of published) {
      const label = normaliseCategory(service.category)
      if (!found.includes(label)) found.push(label)
    }
    return found.sort((a, b) => a.localeCompare(b))
  }, [published])

  const visible = useMemo(
    () => (filter === 'all' ? published : published.filter((s) => normaliseCategory(s.category) === filter)),
    [published, filter],
  )

  return (
    <div className="page">
      <div className="shell">
        <PageIntro
          title="Services & pricing"
          lead="Every treatment is discussed before we begin, so you know exactly what to expect and what it will cost."
        />

        {services.loading ? <LoadingState label="Loading services" /> : null}
        {services.error !== null ? (
          <ErrorState onRetry={services.reload}>Our services list is unavailable right now.</ErrorState>
        ) : null}
        {services.data !== null && published.length === 0 ? (
          <EmptyState title="No services available right now">
            Please message us on WhatsApp and we will let you know what is open this week.
          </EmptyState>
        ) : null}

        {categories.length > 1 ? (
          <FilterRow label="Filter services by category">
            <FilterChip label="All" active={filter === 'all'} onSelect={() => setFilter('all')} />
            {categories.map((category) => (
              <FilterChip
                key={category}
                label={category}
                active={filter === category}
                onSelect={() => setFilter(category)}
              />
            ))}
          </FilterRow>
        ) : null}

        {visible.length > 0 ? (
          <div className="grid grid--services">
            {visible.map((service) => (
              <ServiceCard key={service.id} service={service} />
            ))}
          </div>
        ) : null}

        {filter !== 'all' && visible.length === 0 ? (
          <EmptyState title="Nothing in this category yet">
            Try another category, or message us on WhatsApp.
          </EmptyState>
        ) : null}
      </div>
    </div>
  )
}

function normaliseCategory(category: PublicService['category']): string {
  const trimmed = category?.trim() ?? ''
  return trimmed === '' ? 'Other' : trimmed
}

function PageIntro({ title, lead }: { title: string; lead: string }) {
  return (
    <header className="page-intro">
      <h1>{title}</h1>
      <p>{lead}</p>
    </header>
  )
}

export { PageIntro }
