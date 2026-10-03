/**
 * Response and request types for the FastAPI backend.
 *
 * These mirror the Pydantic schemas in `backend/app/schemas`. They are declared
 * by hand rather than generated, because the backend is the only source of truth
 * and a codegen step would add a build dependency for no benefit at this size.
 *
 * Note the conventions the backend uses consistently:
 * - `id` is a 24-character hex string, not a number.
 * - `price` / `original_price` are decimal **strings**, so no float rounding.
 * - list endpoints return a `Page<T>` envelope, not a bare array.
 */

export interface HealthResponse {
  status: 'ok'
  app: string
  version: string
  environment: string
}

// --- Envelopes ---------------------------------------------------------------

export interface Page<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export interface ErrorDetail {
  location: string[]
  message: string
  type: string
}

/** Every failure the API produces uses this shape. */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: ErrorDetail[]
  }
}

export interface MessageResponse {
  message: string
}

export interface ReorderRequest {
  items: { id: string; display_order: number }[]
}

export interface ReorderResponse {
  updated: number
}

// --- Auth --------------------------------------------------------------------

export interface AdminProfile {
  id: string
  email: string
  name: string
  is_active: boolean
  last_login_at: string | null
}

export interface LoginResponse {
  admin: AdminProfile
  expires_at: string
  csrf_token: string
}

// --- Site settings -----------------------------------------------------------

export interface Address {
  line1?: string | null
  line2?: string | null
  city?: string | null
  state?: string | null
  postal_code?: string | null
  country?: string | null
}

export interface OpeningHour {
  day: string
  is_closed: boolean
  open_time?: string | null
  close_time?: string | null
  note?: string | null
}

export interface SocialLinks {
  facebook?: string | null
  instagram?: string | null
  twitter?: string | null
  linkedin?: string | null
  youtube?: string | null
}

export type CtaBehaviour =
  | 'services'
  | 'offers'
  | 'gallery'
  | 'contact'
  | 'testimonials'
  | 'book'
  | 'none'

export interface SiteSettings {
  id: string
  business_name: string
  tagline?: string | null
  description?: string | null
  logo?: string | null
  favicon?: string | null
  phone?: string | null
  whatsapp_number?: string | null
  email?: string | null
  address?: Address | null
  opening_hours: OpeningHour[]
  social_links?: SocialLinks | null
  about_title?: string | null
  about_content?: string | null
  about_image?: string | null
  hero_title?: string | null
  hero_description?: string | null
  hero_image?: string | null
  hero_cta_text?: string | null
  hero_cta_url?: string | null
  hero_cta_behaviour?: CtaBehaviour | null
  active_theme?: string | null
  active_font?: string | null
  /** Per-token colour overrides applied on top of the active theme preset. */
  theme_overrides?: Record<string, string> | null
  created_at: string
  updated_at: string
}

/** Same shape as `SiteSettings`; the patch endpoint accepts any subset. */
export type SiteSettingsInput = Partial<Omit<SiteSettings, 'id' | 'created_at' | 'updated_at'>>

// --- Themes and fonts --------------------------------------------------------

export interface ThemeCatalogueEntry {
  id: string
  name: string
  description: string
  tokens: Record<string, string>
}

export interface FontCatalogueEntry {
  id: string
  name: string
  description: string
  heading_family: string
  body_family: string
  heading_stack: string
  body_stack: string
  href: string
}

// --- Catalogue: services -----------------------------------------------------

export interface Service {
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

export type ServiceInput = Partial<Omit<Service, 'id' | 'created_at' | 'updated_at'>>

// --- Catalogue: offers -------------------------------------------------------

export interface Offer {
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

export type OfferInput = Partial<Omit<Offer, 'id' | 'created_at' | 'updated_at'>>

// --- Gallery and media -------------------------------------------------------

export interface GalleryItem {
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

/** The admin view additionally exposes storage provenance. */
export interface GalleryAdminItem extends GalleryItem {
  s3_key?: string | null
  content_type?: string | null
  file_size?: number | null
  original_filename?: string | null
}

export interface GalleryInput {
  title: string
  description?: string | null
  image_url: string
  category?: string | null
  is_active?: boolean
  display_order?: number
}

// --- Testimonials ------------------------------------------------------------

export type TestimonialStatus = 'pending' | 'approved' | 'rejected'

export interface Testimonial {
  id: string
  customer_name: string
  content: string
  rating: number
  created_at: string
  status: TestimonialStatus
  is_visible: boolean
  updated_at: string
}
