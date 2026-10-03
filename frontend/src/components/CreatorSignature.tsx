/**
 * Creator signature.
 *
 * A single, self-contained mark of authorship shared by the public footer and
 * the admin panel, so the two can never drift apart. The wording is fixed and
 * the two names link to their LinkedIn profiles.
 *
 * Presentation stays inside the existing token system: the studio takes the
 * theme's heading face and text colour, the byline takes the heading face in
 * italic for a signed feel, and every colour is a semantic variable, so all five
 * themes keep their own character and contrast.
 */

const STUDIO_URL = 'https://www.linkedin.com/company/thridhalabs/'
const AUTHOR_URL = 'https://www.linkedin.com/in/srinadhch07'

export function CreatorSignature() {
  return (
    <p className="creator-signature">
      <span className="creator-signature__eyebrow">A creation of</span>
      <a
        className="creator-signature__studio"
        href={STUDIO_URL}
        target="_blank"
        rel="noopener noreferrer"
      >
        Thridha Labs
      </a>
      <span className="creator-signature__dot" aria-hidden="true">
        ·
      </span>
      <span className="creator-signature__byline">
        <span className="creator-signature__by">by</span>
        <a
          className="creator-signature__author"
          href={AUTHOR_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          Srinadh Chintakindi
        </a>
      </span>
    </p>
  )
}
