/**
 * Typed client for the FastAPI backend.
 *
 * Three things this module is responsible for:
 *
 * 1. **Cookies.** Every request is sent with `credentials: 'include'`, so the
 *    HttpOnly session cookie rides along and is never readable from JS.
 * 2. **CSRF.** The backend requires an `X-CSRF-Token` header on every
 *    state-changing request made with a cookie session. The CSRF *cookie* is
 *    scoped to `/api/v1`, so a page served at `/admin` cannot read it through
 *    `document.cookie`. The token therefore arrives in the login response body
 *    and is mirrored into `sessionStorage` so a page reload does not force a
 *    re-login. The session cookie - not this value - is what authenticates, so
 *    keeping it in `sessionStorage` grants no access on its own.
 * 3. **Errors.** Every backend failure uses one envelope, so it is unwrapped
 *    once here into a readable `ApiError` instead of at every call site.
 */

import { env } from './env'
import type {
  AdminProfile,
  ApiErrorBody,
  FontCatalogueEntry,
  GalleryAdminItem,
  GalleryInput,
  HealthResponse,
  LoginResponse,
  MessageResponse,
  Offer,
  OfferInput,
  Page,
  ReorderRequest,
  ReorderResponse,
  Service,
  ServiceInput,
  SiteSettings,
  SiteSettingsInput,
  Testimonial,
  TestimonialStatus,
  ThemeCatalogueEntry,
} from '@/types/api'

const CSRF_STORAGE_KEY = 'bp.csrf'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE'])

/** A failure from the API, already unwrapped from the error envelope. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: { location: string[]; message: string; type: string }[]

  constructor(
    message: string,
    status: number,
    code = 'error',
    details: ApiErrorBody['error']['details'] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details ?? []
  }

  /** True when the session is missing or expired, so the shell can sign out. */
  get isUnauthenticated(): boolean {
    return this.status === 401
  }

  /** Flattens `details` into one line per offending field. */
  get fieldMessages(): string[] {
    return this.details.map((detail) => {
      const field = detail.location.filter((part) => part !== 'body').join('.')
      return field ? `${field}: ${detail.message}` : detail.message
    })
  }
}

export function getCsrfToken(): string | null {
  return sessionStorage.getItem(CSRF_STORAGE_KEY)
}

export function setCsrfToken(token: string): void {
  sessionStorage.setItem(CSRF_STORAGE_KEY, token)
}

export function clearCsrfToken(): void {
  sessionStorage.removeItem(CSRF_STORAGE_KEY)
}

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null
  try {
    body = (await response.json()) as ApiErrorBody
  } catch {
    body = null
  }

  if (body?.error) {
    return new ApiError(body.error.message, response.status, body.error.code, body.error.details)
  }
  return new ApiError(`Request failed (HTTP ${response.status})`, response.status)
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined

  if (body instanceof FormData) {
    // Let the browser set the multipart boundary itself.
    payload = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  if (!SAFE_METHODS.has(method.toUpperCase())) {
    const csrf = getCsrfToken()
    if (csrf) headers['X-CSRF-Token'] = csrf
  }

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method,
    headers,
    body: payload,
    credentials: 'include',
  })

  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T

  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

const get = <T,>(path: string) => request<T>('GET', path)
const post = <T,>(path: string, body?: unknown) => request<T>('POST', path, body)
const patch = <T,>(path: string, body?: unknown) => request<T>('PATCH', path, body)
const put = <T,>(path: string, body?: unknown) => request<T>('PUT', path, body)
const del = (path: string) => request<void>('DELETE', path)

export const api = {
  // Health is mounted at the unversioned prefix, unlike every other route.
  health: () => fetch(`${env.apiRoot}/health`).then((response) => response.json() as Promise<HealthResponse>),

  auth: {
    login: (email: string, password: string) =>
      post<LoginResponse>('/auth/login', { email, password }),
    me: () => get<AdminProfile>('/auth/me'),
    logout: () => post<MessageResponse>('/auth/logout'),
    forgotPassword: (email: string) => post<MessageResponse>('/auth/forgot-password', { email }),
    resetPassword: (token: string, newPassword: string) =>
      post<MessageResponse>('/auth/reset-password', { token, new_password: newPassword }),
  },

  settings: {
    read: () => get<SiteSettings>('/admin/site-settings'),
    update: (body: SiteSettingsInput) => patch<SiteSettings>('/admin/site-settings', body),
  },

  themes: () => get<ThemeCatalogueEntry[]>('/public/themes'),
  fonts: () => get<FontCatalogueEntry[]>('/public/fonts'),

  services: {
    list: (params: { skip?: number; limit?: number } = {}) =>
      get<Page<Service>>(`/admin/services${buildQuery(params)}`),
    create: (body: ServiceInput) => post<Service>('/admin/services', body),
    update: (id: string, body: ServiceInput) => patch<Service>(`/admin/services/${id}`, body),
    setActive: (id: string, isActive: boolean) =>
      patch<Service>(`/admin/services/${id}/active?is_active=${isActive}`),
    reorder: (body: ReorderRequest) => put<ReorderResponse>('/admin/services/order', body),
    remove: (id: string) => del(`/admin/services/${id}`),
  },

  offers: {
    list: (params: { skip?: number; limit?: number } = {}) =>
      get<Page<Offer>>(`/admin/offers${buildQuery(params)}`),
    create: (body: OfferInput) => post<Offer>('/admin/offers', body),
    update: (id: string, body: OfferInput) => patch<Offer>(`/admin/offers/${id}`, body),
    setActive: (id: string, isActive: boolean) =>
      patch<Offer>(`/admin/offers/${id}/active?is_active=${isActive}`),
    reorder: (body: ReorderRequest) => put<ReorderResponse>('/admin/offers/order', body),
    remove: (id: string) => del(`/admin/offers/${id}`),
  },

  gallery: {
    list: (params: { skip?: number; limit?: number } = {}) =>
      get<Page<GalleryAdminItem>>(`/admin/gallery${buildQuery(params)}`),
    create: (body: GalleryInput) => post<GalleryAdminItem>('/admin/gallery', body),
    update: (id: string, body: Partial<GalleryInput>) =>
      patch<GalleryAdminItem>(`/admin/gallery/${id}`, body),
    setActive: (id: string, isActive: boolean) =>
      patch<GalleryAdminItem>(`/admin/gallery/${id}/active?is_active=${isActive}`),
    reorder: (body: ReorderRequest) => put<ReorderResponse>('/admin/gallery/order', body),
    remove: (id: string) => del(`/admin/gallery/${id}`),
  },

  media: {
    /** Multipart upload. Creates the gallery item and the S3 object together. */
    upload: (file: File, fields: Record<string, string>) => {
      const form = new FormData()
      form.append('file', file)
      for (const [key, value] of Object.entries(fields)) form.append(key, value)
      return request<GalleryAdminItem>('POST', '/admin/media', form)
    },
    update: (id: string, body: Record<string, unknown>) =>
      patch<GalleryAdminItem>(`/admin/media/${id}`, body),
    remove: (id: string) => del(`/admin/media/${id}`),
  },

  testimonials: {
    list: (params: { skip?: number; limit?: number; status?: TestimonialStatus } = {}) =>
      get<Page<Testimonial>>(`/admin/testimonials${buildQuery(params)}`),
    update: (
      id: string,
      body: { customer_name?: string; content?: string; rating?: number },
    ) => patch<Testimonial>(`/admin/testimonials/${id}`, body),
    moderate: (id: string, status: TestimonialStatus, isVisible: boolean) =>
      patch<Testimonial>(`/admin/testimonials/${id}/moderate`, {
        status,
        is_visible: isVisible,
      }),
    remove: (id: string) => del(`/admin/testimonials/${id}`),
  },
}
