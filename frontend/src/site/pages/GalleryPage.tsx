/**
 * Gallery page.
 *
 * Category filters are derived from the published images themselves, so the
 * filter list can never disagree with the data.
 */

import { useMemo, useState } from 'react'

import { publicApi } from '../api'
import { useAsync } from '@/lib/hooks'
import { GalleryGrid } from '../components/GalleryGrid'
import { EmptyState, ErrorState, FilterChip, FilterRow, LoadingState } from '../components/primitives'
import { PageIntro } from './ServicesPage'

export function GalleryPage() {
  const gallery = useAsync(() => publicApi.gallery(), [])
  const [filter, setFilter] = useState('all')

  const published = useMemo(
    () => (gallery.data?.items ?? []).filter((item) => item.is_active),
    [gallery.data],
  )

  const categories = useMemo(() => {
    const found: string[] = []
    for (const item of published) {
      const label = item.category?.trim()
      if (label !== undefined && label !== '' && !found.includes(label)) found.push(label)
    }
    return found.sort((a, b) => a.localeCompare(b))
  }, [published])

  const visible = useMemo(
    () => (filter === 'all' ? published : published.filter((item) => item.category?.trim() === filter)),
    [published, filter],
  )

  return (
    <div className="page">
      <div className="shell">
        <PageIntro
          title="Our work"
          lead="A selection of looks we have created in the studio. Select any image to view it larger."
        />

        {gallery.loading ? <LoadingState label="Loading gallery" /> : null}
        {gallery.error !== null ? (
          <ErrorState onRetry={gallery.reload}>Our gallery is unavailable right now.</ErrorState>
        ) : null}
        {gallery.data !== null && published.length === 0 ? (
          <EmptyState title="No photos yet">
            We are adding our latest work soon — please check back shortly.
          </EmptyState>
        ) : null}

        {categories.length > 1 ? (
          <FilterRow label="Filter gallery by category">
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

        {visible.length > 0 ? <GalleryGrid items={visible} columns={3} /> : null}

        {filter !== 'all' && visible.length === 0 ? (
          <EmptyState title="Nothing in this category yet">Try another category.</EmptyState>
        ) : null}
      </div>
    </div>
  )
}
