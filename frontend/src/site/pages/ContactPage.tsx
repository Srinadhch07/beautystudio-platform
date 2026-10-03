/**
 * Contact page.
 *
 * WhatsApp leads because it is how the studio actually takes bookings. Phone,
 * email, address, hours, socials and a maps link follow from the CMS; anything
 * the admin has not filled in is simply omitted.
 */

import { useSite } from '../site-context'
import { buildMapLink, formatAddress, telHref } from '../format'
import { OpeningHoursList } from '../components/OpeningHours'
import { SocialLinks } from '../components/SocialLinks'
import { EmptyState, WhatsAppButton } from '../components/primitives'
import { PageIntro } from './ServicesPage'

export function ContactPage() {
  const { config, hasWhatsapp } = useSite()
  if (config === null) return null

  const { identity, contact } = config
  const hours = contact.opening_hours ?? []
  // The CMS treats an absent address and a null address the same way, so both
  // are normalised to null once here rather than at every use.
  const address = contact.address ?? null

  const hasAnyDetail =
    contact.phone !== null ||
    contact.email !== null ||
    address !== null ||
    hours.length > 0 ||
    hasWhatsapp

  return (
    <div className="page">
      <div className="shell">
        <PageIntro
          title="Contact"
          lead="The quickest way to reach us is WhatsApp — send a message and we will reply with availability."
        />

        {hasAnyDetail ? (
          <div className="contact">
            <div className="contact__primary">
              {hasWhatsapp ? (
                <div className="contact__wa">
                  <h2>Book or enquire</h2>
                  <p>Tell us what you would like and when suits you.</p>
                  <WhatsAppButton
                    variant="solid"
                    message={`Hi, I'd like to book an appointment at ${identity.business_name}.`}
                    className="contact__wa-button"
                  >
                    Chat on WhatsApp
                  </WhatsAppButton>
                </div>
              ) : null}

              <div className="contact__details">
                <h2>Details</h2>
                <ul>
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
                    </li>
                  ) : null}
                </ul>
                <SocialLinks links={config.social_links} />
              </div>
            </div>

            <aside className="contact__side">
              {hours.length > 0 ? (
                <div className="contact__hours">
                  <h2>Opening hours</h2>
                  <OpeningHoursList hours={hours} />
                </div>
              ) : null}

              {address === null ? null : (
                <div className="contact__map">
                  <a
                    className="contact__map-link"
                    href={buildMapLink(address)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <span>Open in maps</span>
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                      <path d="M9 4L3 7v13l6-3 6 3 6-3V4l-6 3-6-3zM9 4v13M15 7v13" />
                    </svg>
                  </a>
                  <p className="contact__map-note">{formatAddress(address)}</p>
                </div>
              )}
            </aside>
          </div>
        ) : (
          <EmptyState title="Contact details are on their way">
            We are adding our details now — please check back shortly.
          </EmptyState>
        )}
      </div>
    </div>
  )
}
