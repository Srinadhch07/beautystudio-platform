/**
 * About page.
 *
 * The story, image and values all come from the CMS, so this page needs no
 * content of its own. The values are the same positioning points used on the
 * home page rather than a second set of invented claims.
 */

import { useSite } from '../site-context'
import { telHref } from '../format'
import { CmsImage, SectionHeading, WhatsAppButton } from '../components/primitives'
import { PageIntro } from './ServicesPage'

const VALUES: { title: string; body: string }[] = [
  {
    title: 'Care over speed',
    body: 'We would rather take the time to get it right than rush you out the door.',
  },
  {
    title: 'Honest advice',
    body: 'If a treatment is not right for you, we will say so and explain the alternatives.',
  },
  {
    title: 'A clean space',
    body: 'Stations are sanitised between every guest, with fresh linens and single-use items.',
  },
  {
    title: 'Your comfort first',
    body: 'We go at your pace, check in as we go, and stop if you want a break.',
  },
]

export function AboutPage() {
  const { config } = useSite()
  if (config === null) return null

  const { identity, about, contact } = config
  const story = about?.content ?? identity.description
  const title = about?.title ?? `About ${identity.business_name}`

  return (
    <div className="page">
      <div className="shell">
        <PageIntro title={title} lead={identity.tagline ?? 'Our story, our standards and how we work.'} />

        <div className="about">
          <div className="about__copy">
            {/* The CMS stores plain text, so paragraphs are split on blank lines. */}
            {(story ?? '').split(/\n{2,}/).map((paragraph, index) =>
              paragraph.trim() === '' ? null : <p key={index}>{paragraph.trim()}</p>,
            )}

            {contact.phone ? (
              <p className="about__contact">
                <a href={telHref(contact.phone)}>Call {contact.phone}</a>
              </p>
            ) : null}
          </div>

          <div className="about__media">
            <CmsImage src={about?.image} alt={`${identity.business_name} studio`} ratio="4 / 5" eager />
          </div>
        </div>

        <section className="about__values" aria-labelledby="about-values">
          <SectionHeading eyebrow="What we stand for" title="Our approach" />
          <ul className="benefits benefits--values">
            {VALUES.map((value) => (
              <li key={value.title}>
                <h3>{value.title}</h3>
                <p>{value.body}</p>
              </li>
            ))}
          </ul>
        </section>

        <div className="about__cta">
          <WhatsAppButton message={`Hi, I'd like to know more about ${identity.business_name}.`}>
            Ask us anything
          </WhatsAppButton>
        </div>
      </div>
    </div>
  )
}
