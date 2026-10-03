/**
 * Public navigation definition.
 *
 * Lives outside the header component because the footer renders the same links,
 * and one list means the two can never disagree.
 */

export interface NavRoute {
  path: string
  label: string
}

export const NAV: NavRoute[] = [
  { path: '/', label: 'Home' },
  { path: '/services', label: 'Services' },
  { path: '/gallery', label: 'Gallery' },
  { path: '/about', label: 'About' },
  { path: '/testimonials', label: 'Reviews' },
  { path: '/offers', label: 'Offers' },
  { path: '/contact', label: 'Contact' },
]
