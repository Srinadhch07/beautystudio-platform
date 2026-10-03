/**
 * Offers page.
 *
 * The public API only ever returns offers whose validity window contains now, so
 * in practice every item rendered here is live. The split below re-checks the
 * window client-side anyway: an offer that expires between the response and the
 * render is moved to "Previous offers" rather than being shown as bookable, which
 * keeps the badge honest without a second request. A "none running" state is the
 * common case for a real studio, so it reads as normal rather than as a fault.
 */

import { useMemo } from 'react'

import { publicApi } from '../api'
import { useAsync } from '@/lib/hooks'
import { offerWindow } from '../format'
import { OfferCard } from '../components/cards'
import { EmptyState, ErrorState, LoadingState } from '../components/primitives'
import { PageIntro } from './ServicesPage'

export function OffersPage() {
  const offers = useAsync(() => publicApi.offers(), [])

  const { live, past } = useMemo(() => {
    const active = (offers.data?.items ?? []).filter((offer) => offer.is_active)
    return {
      live: active.filter((offer) => offerWindow(offer).tone !== 'over'),
      past: active.filter((offer) => offerWindow(offer).tone === 'over'),
    }
  }, [offers.data])

  return (
    <div className="page">
      <div className="shell">
        <PageIntro
          title="Offers & packages"
          lead="Current packages and promotions. Message us on WhatsApp to check availability before you visit."
        />

        {offers.loading ? <LoadingState label="Loading offers" /> : null}
        {offers.error !== null ? (
          <ErrorState onRetry={offers.reload}>Our offers are unavailable right now.</ErrorState>
        ) : null}
        {offers.data !== null && live.length === 0 && past.length === 0 ? (
          <EmptyState title="No offers running right now">
            Message us on WhatsApp — we often have short-term packages available.
          </EmptyState>
        ) : null}

        {live.length > 0 ? (
          <div className="grid grid--offers">
            {live.map((offer) => (
              <OfferCard key={offer.id} offer={offer} />
            ))}
          </div>
        ) : null}

        {past.length > 0 ? (
          <section className="past-offers" aria-labelledby="past-offers">
            <h2 id="past-offers">Previous offers</h2>
            <div className="grid grid--offers">
              {past.map((offer) => (
                <OfferCard key={offer.id} offer={offer} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  )
}
