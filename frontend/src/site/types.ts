/**
 * Public website types.
 *
 * These are the *public* projections, which are deliberately narrower than the
 * admin ones: a public service has no `created_at`-driven editing surface, and a
 * public testimonial carries no moderation state at all. Only fields the backend
 * actually returns publicly are declared here.
 */

import type {
  Address,
  CtaBehaviour,
  OpeningHour,
  Page,
  SocialLinks,
} from '@/types/api'

export type { Address, CtaBehaviour, OpeningHour, SocialLinks }
export type { Page }

/** Design tokens, applied to CSS custom properties at the document root. */
export interface ThemeTokens {
  primary: string
  secondary: string
  accent: string
  background: string
  surface: string
  text: string
  muted_text: string
  border: string
  button_bg: string
  button_text: string
  button_hover_bg: string
  button_radius: string
  [token: string]: string
}

export interface PublicTheme {
  id: string
  name: string
  description: string
  tokens: ThemeTokens
}

export interface PublicFont {
  id: string
  name: string
  description: string
  heading_family: string
  body_family: string
  heading_stack: string
  body_stack: string
  href: string
}

export interface PublicConfig {
  identity: {
    business_name: string
    tagline?: string | null
    description?: string | null
    logo?: string | null
    favicon?: string | null
  }
  contact: {
    phone?: string | null
    whatsapp_number?: string | null
    email?: string | null
    address?: Address | null
    opening_hours?: OpeningHour[] | null
  }
  social_links?: SocialLinks | null
  hero?: {
    title?: string | null
    description?: string | null
    image?: string | null
    cta_text?: string | null
    cta_url?: string | null
    cta_behaviour?: CtaBehaviour | null
  } | null
  about?: {
    title?: string | null
    content?: string | null
    image?: string | null
  } | null
  theme: PublicTheme
  font: PublicFont
}

/** A public service, as the CMS published it. */
export interface PublicService {
  id: string
  name: string
  description?: string | null
  price: string
  category?: string | null
  duration?: number | null
  image?: string | null
  is_active: boolean
  display_order: number
  created_at: string
  updated_at: string
}

export interface PublicGalleryItem {
  id: string
  title: string
  description?: string | null
  image_url: string
  category?: string | null
  is_active: boolean
  display_order: number
  created_at: string
  updated_at: string
}

export interface PublicTestimonial {
  id: string
  customer_name: string
  content: string
  rating: number
  created_at: string
}

/** New submissions are always pending and hidden; the customer cannot change that. */
export interface TestimonialSubmission {
  customer_name: string
  content: string
  rating: number
}

export interface PublicOffer {
  id: string
  title: string
  description?: string | null
  price: string
  original_price?: string | null
  image?: string | null
  is_active: boolean
  valid_from?: string | null
  valid_until?: string | null
  display_order: number
  created_at: string
  updated_at: string
}
