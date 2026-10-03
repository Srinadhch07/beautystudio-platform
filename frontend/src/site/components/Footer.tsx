/**
 * Public site footer.
 *
 * Content comes entirely from the CMS config: no repeated business details are
 * hard-coded here, so renaming the studio or changing the phone number is a
 * one-place CMS edit.
 */

import { useState } from 'react'

import { useSite } from '../site-context'
import { formatAddress, telHref } from '../format'
import { NAV } from '../nav'
import { CreatorSignature } from '@/components/CreatorSignature'
import { WhatsAppButton } from './primitives'
import { SocialLinks } from './SocialLinks'
import { OpeningHoursList } from './OpeningHours'

export function Footer() {
  const { config, whatsappLink } = useSite()
  // Read the clock once, lazily, so the render stays pure.
  const [year] = useState(() => new Date().getFullYear())
  if (config === null) return null

  const { identity, contact, social_links: socials } = config

  return (
    <footer className="site-footer">
      <div className="shell site-footer__inner">
        <div className="site-footer__brand">
          <p className="site-footer__name">{identity.business_name}</p>
          {identity.tagline ? <p className="site-footer__tagline">{identity.tagline}</p> : null}
          {identity.description ? <p className="site-footer__blurb">{identity.description}</p> : null}
          <WhatsAppButton message="Hi, I'd like to enquire about your services.">
            Chat on WhatsApp
          </WhatsAppButton>
        </div>

        <nav className="site-footer__nav" aria-label="Footer">
          <h2>Explore</h2>
          <ul>
            {NAV.map((route) => (
              <li key={route.path}>
                <a href={`#${route.path}`}>{route.label}</a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="site-footer__contact">
          <h2>Visit</h2>
          <address>
            {contact.phone ? (
              <a href={telHref(contact.phone)}>{contact.phone}</a>
            ) : null}
            {contact.email ? (
              <a href={`mailto:${contact.email}`}>{contact.email}</a>
            ) : null}
            {whatsappLink() !== null && contact.whatsapp_number ? (
              <a
                href={whatsappLink() ?? '#'}
                target="_blank"
                rel="noopener noreferrer"
              >
                {contact.whatsapp_number}
              </a>
            ) : null}
            {contact.address ? <span className="site-footer__address">{formatAddress(contact.address)}</span> : null}
          </address>
          <SocialLinks links={socials} />
        </div>

        {contact.opening_hours && contact.opening_hours.length > 0 ? (
          <div className="site-footer__hours">
            <h2>Opening hours</h2>
            <OpeningHoursList hours={contact.opening_hours} />
          </div>
        ) : null}
      </div>

      <div className="site-footer__base shell">
        <p className="site-footer__copy">
          &copy; {year} {identity.business_name}. All rights reserved.
        </p>
        <CreatorSignature />
      </div>
    </footer>
  )
}
