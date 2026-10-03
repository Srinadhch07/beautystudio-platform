/**
 * Public website API layer.
 *
 * No credentials, no CSRF token, no session handling: these endpoints are
 * unauthenticated by design. Errors are reduced to a short customer-safe string
 * here, so no component ever renders a raw exception to a visitor.
 */

import { env } from '@/lib/env'
import type {
  Page,
  PublicConfig,
  PublicFont,
  PublicGalleryItem,
  PublicOffer,
  PublicService,
  PublicTestimonial,
  PublicTheme,
  TestimonialSubmission,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    })
  } catch {
    // A network failure is the common case for a visitor on a train or a weak
    // signal, so it gets a human message rather than "Failed to fetch".
    throw new Error('We could not reach the studio right now. Please try again shortly.')
  }

  if (!response.ok) throw new Error('This part of the site is unavailable right now.')

  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

function page<T>(path: string, limit = 200): Promise<Page<T>> {
  return request<Page<T>>(`${path}?limit=${limit}`)
}

export const publicApi = {
  config: () => request<PublicConfig>('/public/config'),
  themes: () => request<PublicTheme[]>('/public/themes'),
  fonts: () => request<PublicFont[]>('/public/fonts'),

  services: () => page<PublicService>('/public/services'),
  gallery: () => page<PublicGalleryItem>('/public/gallery'),
  offers: () => page<PublicOffer>('/public/offers'),
  testimonials: () => page<PublicTestimonial>('/public/testimonials'),

  /** Submits a review. The backend queues it as pending and hidden. */
  submitTestimonial: (body: TestimonialSubmission) =>
    request<{ id: string }>('/public/testimonials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
