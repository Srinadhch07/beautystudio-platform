/**
 * Home page hero.
 *
 * Every string comes from the CMS. The admin's `hero_cta_behaviour` decides what
 * the secondary action does, and "book" routes it through WhatsApp so the
 * business can point the hero CTA at their own booking conversation.
 */

import { useSite } from '../site-context'
import { CmsImage, WhatsAppButton } from './primitives'

/** Internal destinations the CMS CTA can point at. */
const CTA_ROUTES: Record<string, string> = {
  services: '#/services',
  offers: '#/offers',
  gallery: '#/gallery',
  contact: '#/contact',
  testimonials: '#/testimonials',
}

export function Hero() {
  const { config } = useSite()
  if (config === null) return null

  const { identity, hero } = config
  const behaviour = hero?.cta_behaviour ?? 'services'
  const ctaLabel = hero?.cta_text ?? 'Explore Services'

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="shell hero__inner">
        <div className="hero__copy">
          <p className="hero__eyebrow">
            <span>{identity.business_name}</span>
            {identity.tagline ? <span className="hero__tagline">{identity.tagline}</span> : null}
          </p>

          <h1 id="hero-title">{hero?.title ?? identity.business_name}</h1>
          {hero?.description ? <p className="hero__text">{hero.description}</p> : null}

          <div className="hero__actions">
            <WhatsAppButton
              message={`Hi, I'd like to book with ${identity.business_name}.`}
              className="hero__primary"
            >
              {behaviour === 'book' ? (ctaLabel || 'Book on WhatsApp') : 'Book / Enquire on WhatsApp'}
            </WhatsAppButton>

            {behaviour === 'none' ? null : behaviour === 'book' ? (
              <a className="button button--quiet" href="#/services">
                Explore Services
              </a>
            ) : (
              <a
                className="button button--quiet"
                href={hero?.cta_url ?? CTA_ROUTES[behaviour] ?? '#/services'}
                {...(hero?.cta_url === null || hero?.cta_url === undefined
                  ? {}
                  : { target: '_blank', rel: 'noopener noreferrer' })}
              >
                {ctaLabel}
              </a>
            )}
          </div>

          {hero?.cta_behaviour === 'book' ? null : (
            <p className="hero__note">
              Prefer a chat? Message us on WhatsApp and we'll reply with availability.
            </p>
          )}
        </div>

        <div className="hero__media">
          {hero?.image ? (
            <CmsImage src={hero.image} alt={hero.title ?? identity.business_name} ratio="4 / 5" eager />
          ) : (
            <CmsImage src={null} alt="" ratio="4 / 5" className="hero__media-placeholder" />
          )}
        </div>
      </div>
    </section>
  )
}
