/**
 * Home page.
 *
 * The one page that has to earn the visit: it previews every other section and
 * repeats the WhatsApp path at each natural decision point. Each band loads its
 * own data independently so one slow endpoint cannot blank the page.
 */

import { publicApi } from '../api'
import { useAsync } from '@/lib/hooks'
import { useSite } from '../site-context'
import type { Page } from '../types'
import { buildMapLink, formatAddress, telHref } from '../format'
import { Hero } from '../components/Hero'
import { OpeningHoursList } from '../components/OpeningHours'
import { GalleryGrid } from '../components/GalleryGrid'
import { OfferCard, ServiceCard, TestimonialCard } from '../components/cards'
import { EmptyState, ErrorState, LoadingState, SectionHeading, WhatsAppButton } from '../components/primitives'
import { SocialLinks } from '../components/SocialLinks'

/** The benefits are positioning copy, not CMS records, so they live here. */
const BENEFITS: { title: string; body: string }[] = [
  {
    title: 'Tailored consultations',
    body: 'Every appointment starts with a conversation about your hair, skin and the look you want.',
  },
  {
    title: 'Premium products',
    body: 'Professional-grade care and colour, chosen for lasting results rather than a quick fix.',
  },
  {
    title: 'Hygiene first',
    body: 'A fresh, sanitised station for every guest, with single-use disposables throughout.',
  },
  {
    title: 'Easy booking',
    body: 'Message us on WhatsApp and we will confirm a time that suits you.',
  },
]

export function HomePage() {
  const { config } = useSite()
  const services = useAsync(() => publicApi.services(), [])
  const gallery = useAsync(() => publicApi.gallery(), [])
  const testimonials = useAsync(() => publicApi.testimonials(), [])
  const offers = useAsync(() => publicApi.offers(), [])

  const featured = pick(services.data, 4)
  const work = pick(gallery.data, 6)
  const reviews = pick(testimonials.data, 3)
  const liveOffers = pick(offers.data, 12)
    .filter((offer) => offer.is_active)
    .slice(0, 3)

  return (
    <>
      <Hero />

      {config?.identity.description ? (
        <section className="band band--intro">
          <div className="shell intro">
            <p className="intro__text">{config.identity.description}</p>
          </div>
        </section>
      ) : null}

      <section className="band" aria-labelledby="home-services">
        <div className="shell">
          <SectionHeading eyebrow="What we offer" title="Featured services">
            A sample of our most requested treatments. Prices and durations are published up front.
          </SectionHeading>

          {services.loading ? <LoadingState label="Loading services" /> : null}
          {services.error !== null ? (
            <ErrorState onRetry={services.reload}>Our services list is unavailable right now.</ErrorState>
          ) : null}
          {services.data !== null && featured.length === 0 ? (
            <EmptyState title="No services available right now">
              Please message us on WhatsApp and we will let you know what is open this week.
            </EmptyState>
          ) : null}
          {featured.length > 0 ? (
            <>
              <div className="grid grid--services">
                {featured.map((service) => (
                  <ServiceCard key={service.id} service={service} />
                ))}
              </div>
              {services.data !== null && services.data.total > featured.length ? (
                <p className="band__more">
                  <a className="link-button" href="#/services">
                    View all {services.data.total} services
                  </a>
                </p>
              ) : null}
            </>
          ) : null}
        </div>
      </section>

      <section className="band band--tint" aria-labelledby="home-why">
        <div className="shell">
          <SectionHeading eyebrow="Why choose us" title="A visit you can look forward to" />
          <ul className="benefits">
            {BENEFITS.map((benefit) => (
              <li key={benefit.title}>
                <h3>{benefit.title}</h3>
                <p>{benefit.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="band" aria-labelledby="home-work">
        <div className="shell">
          <SectionHeading eyebrow="Previous work" title="A look at our results">
            Real work from the studio, photographed after the service.
          </SectionHeading>

          {gallery.loading ? <LoadingState label="Loading gallery" /> : null}
          {gallery.error !== null ? (
            <ErrorState onRetry={gallery.reload}>Our gallery is unavailable right now.</ErrorState>
          ) : null}
          {gallery.data !== null && work.length === 0 ? (
            <EmptyState title="No photos yet">
              We are adding our latest work soon — please check back shortly.
            </EmptyState>
          ) : null}
          {work.length > 0 ? (
            <>
              <GalleryGrid items={work} columns={3} />
              {gallery.data !== null && gallery.data.total > work.length ? (
                <p className="band__more">
                  <a className="link-button" href="#/gallery">
                    See the full gallery
                  </a>
                </p>
              ) : null}
            </>
          ) : null}
        </div>
      </section>

      <section className="band band--tint" aria-labelledby="home-reviews">
        <div className="shell">
          <SectionHeading eyebrow="Kind words" title="What our clients say" />
          {testimonials.loading ? <LoadingState label="Loading reviews" /> : null}
          {testimonials.error !== null ? (
            <ErrorState onRetry={testimonials.reload}>Reviews are unavailable right now.</ErrorState>
          ) : null}
          {testimonials.data !== null && reviews.length === 0 ? (
            <EmptyState title="No reviews yet">
              Been to us before? We would love to hear how it went.
            </EmptyState>
          ) : null}
          {reviews.length > 0 ? (
            <div className="grid grid--reviews">
              {reviews.map((testimonial, index) => (
                <TestimonialCard key={testimonial.id} testimonial={testimonial} index={index} />
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <section className="band" aria-labelledby="home-offers">
        <div className="shell">
          <SectionHeading eyebrow="Current offers" title="Packages and promotions" />
          {offers.loading ? <LoadingState label="Loading offers" /> : null}
          {offers.error !== null ? (
            <ErrorState onRetry={offers.reload}>Our offers are unavailable right now.</ErrorState>
          ) : null}
          {offers.data !== null && liveOffers.length === 0 ? (
            <EmptyState title="No offers running right now">
              Message us on WhatsApp — we often have short-term packages available.
            </EmptyState>
          ) : null}
          {liveOffers.length > 0 ? (
            <div className="grid grid--offers">
              {liveOffers.map((offer) => (
                <OfferCard key={offer.id} offer={offer} />
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <WhatsAppCta />
      <ContactSummary />
    </>
  )
}

/** Full-width closing call to action. */
function WhatsAppCta() {
  const { config, hasWhatsapp } = useSite()
  if (!hasWhatsapp) return null
  const name = config?.identity.business_name ?? 'the studio'

  return (
    <section className="band band--cta">
      <div className="shell cta">
        <div>
          <h2>Ready when you are</h2>
          <p>
            Send us a message and we'll reply with availability and anything you need to know before
            you visit {name}.
          </p>
        </div>
        <WhatsAppButton
          variant="solid"
          message={`Hi, I'd like to book an appointment at ${name}.`}
          className="cta__button"
        >
          Chat on WhatsApp
        </WhatsAppButton>
      </div>
    </section>
  )
}

/** Closing location and hours summary. */
function ContactSummary() {
  const { config } = useSite()
  if (config === null) return null
  const { contact } = config
  const hours = contact.opening_hours ?? []
  const address = contact.address

  const mapHref = address === null || address === undefined ? null : buildMapLink(address)

  if (contact.phone === null && contact.email === null && address === null && hours.length === 0) {
    return null
  }

  return (
    <section className="band" aria-labelledby="home-visit">
      <div className="shell visit">
        <div>
          <SectionHeading eyebrow="Visit us" title="Find the studio" />
          <ul className="visit__details">
            {contact.phone ? (
              <li>
                <span>Phone</span>
                <a href={telHref(contact.phone)}>{contact.phone}</a>
              </li>
            ) : null}
            {contact.email ? (
              <li>
                <span>Email</span>
                <a href={`mailto:${contact.email}`}>{contact.email}</a>
              </li>
            ) : null}
            {address ? (
              <li>
                <span>Address</span>
                <span>{formatAddress(address)}</span>
                {mapHref === null ? null : (
                  <a href={mapHref} target="_blank" rel="noopener noreferrer">
                    Open in maps
                  </a>
                )}
              </li>
            ) : null}
          </ul>
          <SocialLinks links={config.social_links} />
        </div>

        {hours.length > 0 ? (
          <div className="visit__hours">
            <h3>Opening hours</h3>
            <OpeningHoursList hours={hours} />
          </div>
        ) : null}
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- helpers */

/** Takes the first `count` published records, if the request has succeeded. */
function pick<T>(data: Page<T> | null, count: number): T[] {
  if (data === null) return []
  return data.items.slice(0, count)
}
