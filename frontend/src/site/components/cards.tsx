/**
 * Content cards for services, offers and reviews.
 *
 * Each one is a link-free semantic element; the only interactive element is a
 * real button or anchor, so keyboard and screen-reader users get sensible
 * behaviour without extra ARIA.
 */

import type { CSSProperties } from 'react'

import type { PublicOffer, PublicService, PublicTestimonial } from '../types'
import { formatDate, formatMoney, offerWindow } from '../format'
import { CmsImage, Stars, WhatsAppButton } from './primitives'

/* ---------------------------------------------------------------- services */

export function ServiceCard({ service }: { service: PublicService }) {
  return (
    <article className="card service-card">
      {service.image ? (
        <CmsImage src={service.image} alt={service.name} ratio="4 / 3" className="service-card__media" />
      ) : null}
      <div className="service-card__body">
        <div className="service-card__head">
          <h3>{service.name}</h3>
          {service.duration !== null && service.duration !== undefined ? (
            <span className="chip">{service.duration} min</span>
          ) : null}
        </div>

        {service.category ? <p className="service-card__category">{service.category}</p> : null}
        {service.description ? <p className="service-card__text">{service.description}</p> : null}

        <div className="service-card__foot">
          <p className="price">
            {formatMoney(service.price)}
            {service.duration !== null && service.duration !== undefined ? (
              <span className="price__unit"> / session</span>
            ) : null}
          </p>
          <WhatsAppButton
            variant="ghost"
            message={`Hi, I'm interested in ${service.name}. I'd like to know more.`}
          >
            Enquire
          </WhatsAppButton>
        </div>
      </div>
    </article>
  )
}

/* ------------------------------------------------------------------ offers */

export function OfferCard({ offer }: { offer: PublicOffer }) {
  const window = offerWindow(offer)
  const onOffer = window.tone === 'live'

  return (
    <article className={`card offer-card offer-card--${window.tone}`}>
      <div className="offer-card__media">
        <CmsImage src={offer.image} alt={offer.title} ratio="16 / 10" />
        <span className={`badge badge--${window.tone}`}>{window.label}</span>
      </div>
      <div className="offer-card__body">
        <h3>{offer.title}</h3>
        {offer.description ? <p className="offer-card__text">{offer.description}</p> : null}

        <p className="offer-card__prices">
          <span className="price price--lg">{formatMoney(offer.price)}</span>
          {offer.original_price ? (
            <s className="price--was">{formatMoney(offer.original_price)}</s>
          ) : null}
        </p>

        {window.tone !== 'over' ? <p className="offer-card__validity">{validityText(offer)}</p> : null}

        {onOffer ? (
          <WhatsAppButton
            variant="solid"
            message={`Hi, I'm interested in the "${offer.title}" offer. I'd like to know more.`}
          >
            Enquire about this offer
          </WhatsAppButton>
        ) : (
          <p className="offer-card__note">
            {window.tone === 'soon' ? 'Available soon — message us to be notified.' : 'This offer has ended.'}
          </p>
        )}
      </div>
    </article>
  )
}

function validityText(offer: PublicOffer): string {
  if (offer.valid_from === null || offer.valid_from === undefined) {
    return offer.valid_until ? `Ends ${formatDate(offer.valid_until)}` : 'Ongoing offer'
  }
  const from = formatDate(offer.valid_from)
  return offer.valid_until ? `${from} – ${formatDate(offer.valid_until)}` : `From ${from}`
}

/* ------------------------------------------------------------ testimonials */

export function TestimonialCard({
  testimonial,
  index = 0,
}: {
  testimonial: PublicTestimonial
  index?: number
}) {
  return (
    <figure className="card testimonial-card" style={{ '--i': index } as CSSProperties}>
      <Stars value={testimonial.rating} label={`Rated ${testimonial.rating} out of 5`} />
      <blockquote>
        <p>{testimonial.content}</p>
      </blockquote>
      <figcaption>
        <span className="testimonial-card__avatar" aria-hidden="true">
          {testimonial.customer_name.slice(0, 1).toUpperCase()}
        </span>
        <span>
          <span className="testimonial-card__name">{testimonial.customer_name}</span>
          <span className="testimonial-card__date">{formatDate(testimonial.created_at)}</span>
        </span>
      </figcaption>
    </figure>
  )
}
