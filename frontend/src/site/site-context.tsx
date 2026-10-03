/**
 * Site-wide data and presentation for the public website.
 *
 * `/public/config` is loaded once and shared, because nearly every section needs
 * the business identity and the active theme. Its theme tokens and font preset
 * are applied as CSS custom properties on the document root, so the stylesheet
 * can theme the whole site without any component knowing a colour value, and
 * without a second theme system existing in the frontend.
 */

import { createContext, useContext, useEffect, useMemo } from 'react'
import type { ReactNode } from 'react'

import { publicApi } from './api'
import { useAsync } from '@/lib/hooks'
import type { PublicConfig } from './types'

/**
 * Maps backend theme tokens onto the custom properties the stylesheet uses.
 * Anything the backend does not define is skipped, so adding a token to a
 * preset later cannot produce an undefined colour.
 */
const TOKEN_VARS: Record<string, string> = {
  primary: '--bp-primary',
  secondary: '--bp-secondary',
  accent: '--bp-accent',
  background: '--bp-bg',
  surface: '--bp-surface',
  text: '--bp-text',
  muted_text: '--bp-muted',
  border: '--bp-border',
  button_bg: '--bp-btn-bg',
  button_text: '--bp-btn-text',
  button_hover_bg: '--bp-btn-hover',
  button_radius: '--bp-radius',
}

/** Sensible values used until the config arrives, so the first paint is styled. */
const FALLBACK_TOKENS: Record<string, string> = {
  primary: '#b56576',
  secondary: '#7d6f68',
  accent: '#b56576',
  background: '#faf7f5',
  surface: '#ffffff',
  text: '#2b2320',
  muted_text: '#7d6f68',
  border: '#e6ddd8',
  button_bg: '#b56576',
  button_text: '#ffffff',
  button_hover_bg: '#93495a',
  button_radius: '999px',
}

function applyTheme(config: PublicConfig | null): void {
  const root = document.documentElement
  const tokens = config?.theme?.tokens ?? FALLBACK_TOKENS

  for (const [token, variable] of Object.entries(TOKEN_VARS)) {
    const value = tokens[token]
    if (typeof value === 'string' && value !== '') root.style.setProperty(variable, value)
  }

  // The stacks come from the curated font table, never from admin input, so
  // applying them as a font-family is safe.
  const font = config?.font
  if (font !== null && font !== undefined) {
    root.style.setProperty('--bp-heading-font', font.heading_stack)
    root.style.setProperty('--bp-body-font', font.body_stack)
    ensureFontLoaded(font.href, font.id)
  }
}

/**
 * Injects the curated Google Fonts stylesheet once per preset.
 *
 * The href is a static string from the backend's font table, built there from
 * curated family names - not something a visitor or an admin can supply.
 */
const loadedFonts = new Set<string>()

function ensureFontLoaded(href: string, fontId: string): void {
  if (loadedFonts.has(fontId)) return
  loadedFonts.add(fontId)
  if (document.querySelector(`link[data-font="${fontId}"]`) !== null) return

  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = href
  link.dataset.font = fontId
  document.head.appendChild(link)
}

interface SiteState {
  config: PublicConfig | null
  loading: boolean
  error: string | null
  /** Re-fetches the config, used by the boot-failure retry. */
  reload: () => void
  /** A ready-to-open `wa.me` link, or `null` when no number is configured. */
  whatsappLink: (message?: string) => string | null
  hasWhatsapp: boolean
}

const SiteContext = createContext<SiteState | null>(null)

export function SiteProvider({ children }: { children: ReactNode }) {
  const config = useAsync(() => publicApi.config(), [])

  useEffect(() => {
    applyTheme(config.data)
  }, [config.data])

  useEffect(() => {
    if (config.data === null) return
    const identity = config.data.identity
    document.title = identity.business_name
    if (identity.description) {
      const meta = document.querySelector('meta[name="description"]')
      if (meta !== null) meta.setAttribute('content', identity.description.slice(0, 300))
    }
    if (identity.favicon) {
      let icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
      if (icon === null) {
        icon = document.createElement('link')
        icon.rel = 'icon'
        document.head.appendChild(icon)
      }
      icon.href = identity.favicon
    }
  }, [config.data])

  const value = useMemo<SiteState>(() => {
    const raw = config.data?.contact.whatsapp_number ?? ''
    // wa.me expects digits only, with no leading plus or separators.
    const digits = raw.replace(/\D/g, '')

    return {
      config: config.data,
      loading: config.loading,
      error: config.error,
      reload: config.reload,
      hasWhatsapp: digits.length > 0,
      whatsappLink: (message?: string) => {
        if (digits === '') return null
        const base = `https://wa.me/${digits}`
        return message === undefined || message === ''
          ? base
          : `${base}?text=${encodeURIComponent(message)}`
      },
    }
  }, [config.data, config.loading, config.error, config.reload])

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>
}

export function useSite(): SiteState {
  const context = useContext(SiteContext)
  if (context === null) throw new Error('useSite must be used inside <SiteProvider>')
  return context
}
