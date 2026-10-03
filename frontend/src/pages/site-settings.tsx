import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  Banner,
  Button,
  Card,
  Checkbox,
  Field,
  Grid,
  PageHeader,
  Select,
  Spinner,
  TextArea,
  TextInput,
} from '@/components/ui'
import { api } from '@/lib/api'
import { useAsync, useMutation } from '@/lib/hooks'
import type { FontCatalogueEntry, SiteSettings, SiteSettingsInput, ThemeCatalogueEntry } from '@/types/api'

type ThemeEntry = ThemeCatalogueEntry
type FontEntry = FontCatalogueEntry

const DAYS = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
]

const CTA_BEHAVIOURS = [
  'services',
  'offers',
  'gallery',
  'contact',
  'testimonials',
  'book',
  'none',
]

const SOCIAL_FIELDS = [
  ['facebook', 'Facebook'],
  ['instagram', 'Instagram'],
  ['twitter', 'Twitter / X'],
  ['linkedin', 'LinkedIn'],
  ['youtube', 'YouTube'],
] as const

/**
 * The colour tokens the backend accepts as overrides, in presentation order.
 * Kept in step with `OVERRIDABLE_TOKENS` in `backend/app/core/themes.py`: the
 * backend rejects anything outside this set, so a drift here would surface as a
 * save-time validation error rather than a silent no-op.
 */
const COLOR_TOKENS = [
  { key: 'primary', label: 'Primary' },
  { key: 'secondary', label: 'Secondary' },
  { key: 'accent', label: 'Accent' },
  { key: 'background', label: 'Background' },
  { key: 'surface', label: 'Surface' },
  { key: 'text', label: 'Text' },
  { key: 'muted_text', label: 'Muted text' },
  { key: 'border', label: 'Border' },
  { key: 'button_bg', label: 'Button background' },
  { key: 'button_text', label: 'Button text' },
  { key: 'button_hover_bg', label: 'Button hover' },
] as const

const HEX_COLOR = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

/** A 3-digit hex expands to 6 so `<input type="color">` can display it. */
function expandHex(value: string): string {
  if (value.length === 4 && HEX_COLOR.test(value)) {
    return `#${value[1]}${value[1]}${value[2]}${value[2]}${value[3]}${value[3]}`
  }
  return value
}

function hexToRgb(value: string): [number, number, number] | null {
  if (!HEX_COLOR.test(value)) return null
  const hex = expandHex(value)
  return [
    Number.parseInt(hex.slice(1, 3), 16),
    Number.parseInt(hex.slice(3, 5), 16),
    Number.parseInt(hex.slice(5, 7), 16),
  ]
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const channel = (component: number) => {
    const scaled = component / 255
    return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

/** WCAG 2.1 contrast ratio, or `null` when either colour is not valid hex. */
function contrastRatio(first: string, second: string): number | null {
  const a = hexToRgb(first)
  const b = hexToRgb(second)
  if (a === null || b === null) return null
  const light = Math.max(relativeLuminance(a), relativeLuminance(b))
  const dark = Math.min(relativeLuminance(a), relativeLuminance(b))
  return (light + 0.05) / (dark + 0.05)
}

type OpeningHour = { day: string; is_closed: boolean; open_time: string; close_time: string }

export function SiteSettingsPage() {
  const settings = useAsync(() => api.settings.read(), [])
  const themes = useAsync(() => api.themes(), [])
  const fonts = useAsync(() => api.fonts(), [])

  if (settings.loading || themes.loading || fonts.loading) {
    return <Spinner label="Loading settings" />
  }

  if (settings.error !== null) return <Banner tone="error">{settings.error}</Banner>

  // Keyed on the stored document so a save re-seeds the form from the server's
  // response rather than keeping whatever was typed.
  return (
    <SettingsForm
      key={settings.data?.updated_at ?? 'unset'}
      initial={stripServerFields(settings.data)}
      themes={themes.data ?? []}
      fonts={fonts.data ?? []}
    />
  )
}

function stripServerFields(
  data: SiteSettings | null,
): Omit<SiteSettings, 'id' | 'created_at' | 'updated_at'> | null {
  if (data === null) return null
  const { id, created_at, updated_at, ...rest } = data
  void id
  void created_at
  void updated_at
  return rest
}

function SettingsForm({
  initial,
  themes,
  fonts,
}: {
  initial: Omit<SiteSettings, 'id' | 'created_at' | 'updated_at'> | null
  themes: ThemeEntry[]
  fonts: FontEntry[]
}) {
  const [form, setForm] = useState<SiteSettingsInput>(initial ?? {})
  const { busy, error, done, run } = useMutation()

  const set = <K extends keyof SiteSettingsInput>(key: K, value: SiteSettingsInput[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  const setAddress = (key: string, value: string) =>
    set('address', { ...(form.address ?? {}), [key]: value || null })

  const overrides = form.theme_overrides ?? {}
  const hasInvalidOverrides = Object.values(overrides).some((value) => !HEX_COLOR.test(value))

  const setOverride = (key: string, value: string | null) =>
    setForm((current) => {
      const next = { ...(current.theme_overrides ?? {}) }
      if (value === null) delete next[key]
      else next[key] = value
      return { ...current, theme_overrides: next }
    })

  const resetOverrides = () => set('theme_overrides', {})

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await run(() => api.settings.update(form))
  }

  const hours: OpeningHour[] = DAYS.map((day) => {
    const existing = (form.opening_hours ?? []).find((entry) => entry.day === day)
    return {
      day,
      is_closed: existing?.is_closed ?? true,
      open_time: existing?.open_time ?? '',
      close_time: existing?.close_time ?? '',
    }
  })

  const setHour = (day: string, patch: Partial<OpeningHour>) => {
    const next = hours.map((entry) => (entry.day === day ? { ...entry, ...patch } : entry))
    set(
      'opening_hours',
      // A closed day stores no times, matching the backend's rule that a closed
      // day may omit them but an open one may not.
      next.map((entry) => ({
        day: entry.day,
        is_closed: entry.is_closed,
        open_time: entry.is_closed || entry.open_time === '' ? null : entry.open_time,
        close_time: entry.is_closed || entry.close_time === '' ? null : entry.close_time,
      })),
    )
  }

  return (
    <form onSubmit={onSubmit}>
      <PageHeader
        title="Site settings"
        description="Business identity, contact details, opening hours and presentation."
        actions={
          <Button type="submit" busy={busy} disabled={busy || hasInvalidOverrides}>
            {busy ? 'Saving' : 'Save changes'}
          </Button>
        }
      />

      {error !== null && <Banner tone="error">{error}</Banner>}
      {done && (
        <Banner tone="success" onDismiss={() => undefined}>
          Settings saved.
        </Banner>
      )}

      <Card title="Business" description="How the parlour is named and described.">
        <Grid>
          <Field label="Business name">
            {(id) => (
              <TextInput
                id={id}
                value={form.business_name ?? ''}
                onChange={(value) => set('business_name', value)}
                required
                maxLength={160}
              />
            )}
          </Field>
          <Field label="Tagline">
            {(id) => (
              <TextInput
                id={id}
                value={form.tagline ?? ''}
                onChange={(value) => set('tagline', value)}
                maxLength={200}
              />
            )}
          </Field>
        </Grid>

        <Field label="Description">
          {(id) => (
            <TextArea
              id={id}
              value={form.description ?? ''}
              onChange={(value) => set('description', value)}
              maxLength={2000}
            />
          )}
        </Field>

        <Grid>
          <Field label="Logo URL">
            {(id) => (
              <TextInput
                id={id}
                type="url"
                value={form.logo ?? ''}
                onChange={(value) => set('logo', value)}
                placeholder="https://…"
              />
            )}
          </Field>
          <Field label="Favicon URL">
            {(id) => (
              <TextInput
                id={id}
                type="url"
                value={form.favicon ?? ''}
                onChange={(value) => set('favicon', value)}
                placeholder="https://…"
              />
            )}
          </Field>
        </Grid>
      </Card>

      <Card title="Contact" description="Shown on the public site and used for enquiries.">
        <Grid columns={3}>
          <Field label="Phone">
            {(id) => (
              <TextInput
                id={id}
                value={form.phone ?? ''}
                onChange={(value) => set('phone', value)}
                maxLength={40}
              />
            )}
          </Field>
          <Field label="WhatsApp number">
            {(id) => (
              <TextInput
                id={id}
                value={form.whatsapp_number ?? ''}
                onChange={(value) => set('whatsapp_number', value)}
                maxLength={40}
              />
            )}
          </Field>
          <Field label="Email">
            {(id) => (
              <TextInput
                id={id}
                type="email"
                value={form.email ?? ''}
                onChange={(value) => set('email', value)}
              />
            )}
          </Field>
        </Grid>

        <Grid>
          <Field label="Address line 1">
            {(id) => (
              <TextInput
                id={id}
                value={form.address?.line1 ?? ''}
                onChange={(value) => setAddress('line1', value)}
              />
            )}
          </Field>
          <Field label="Address line 2">
            {(id) => (
              <TextInput
                id={id}
                value={form.address?.line2 ?? ''}
                onChange={(value) => setAddress('line2', value)}
              />
            )}
          </Field>
          <Field label="City">
            {(id) => (
              <TextInput
                id={id}
                value={form.address?.city ?? ''}
                onChange={(value) => setAddress('city', value)}
              />
            )}
          </Field>
          <Field label="State">
            {(id) => (
              <TextInput
                id={id}
                value={form.address?.state ?? ''}
                onChange={(value) => setAddress('state', value)}
              />
            )}
          </Field>
          <Field label="Postal code">
            {(id) => (
              <TextInput
                id={id}
                value={form.address?.postal_code ?? ''}
                onChange={(value) => setAddress('postal_code', value)}
              />
            )}
          </Field>
          <Field label="Country">
            {(id) => (
              <TextInput
                id={id}
                value={form.address?.country ?? ''}
                onChange={(value) => setAddress('country', value)}
              />
            )}
          </Field>
        </Grid>

        <div>
          <h3 style={{ marginBottom: 8 }}>Social links</h3>
          <Grid>
            {SOCIAL_FIELDS.map(([key, label]) => (
              <Field key={key} label={label}>
                {(id) => (
                  <TextInput
                    id={id}
                    type="url"
                    value={form.social_links?.[key] ?? ''}
                    onChange={(value) =>
                      set('social_links', {
                        ...(form.social_links ?? {}),
                        [key]: value || null,
                      })
                    }
                    placeholder="https://…"
                  />
                )}
              </Field>
            ))}
          </Grid>
        </div>
      </Card>

      <Card title="Opening hours" description="Leave a day closed to hide its times.">
        <div className="stack">
          {hours.map((entry) => (
            <div className="hours-row" key={entry.day}>
              <strong style={{ textTransform: 'capitalize' }}>{entry.day}</strong>
              <Checkbox
                checked={!entry.is_closed}
                onChange={(open) => setHour(entry.day, { is_closed: !open })}
                label={entry.is_closed ? 'Closed' : 'Open'}
              />
              {entry.is_closed ? (
                <span className="muted">—</span>
              ) : (
                <>
                  <TextInput
                    type="time"
                    value={entry.open_time}
                    onChange={(value) => setHour(entry.day, { open_time: value })}
                    aria-label={`${entry.day} opening time`}
                  />
                  <TextInput
                    type="time"
                    value={entry.close_time}
                    onChange={(value) => setHour(entry.day, { close_time: value })}
                    aria-label={`${entry.day} closing time`}
                  />
                </>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Card title="Hero" description="The banner at the top of the home page.">
        <Grid>
          <Field label="Headline">
            {(id) => (
              <TextInput
                id={id}
                value={form.hero_title ?? ''}
                onChange={(value) => set('hero_title', value)}
                maxLength={200}
              />
            )}
          </Field>
          <Field label="Image URL">
            {(id) => (
              <TextInput
                id={id}
                type="url"
                value={form.hero_image ?? ''}
                onChange={(value) => set('hero_image', value)}
                placeholder="https://…"
              />
            )}
          </Field>
        </Grid>

        <Field label="Subheading">
          {(id) => (
            <TextArea
              id={id}
              value={form.hero_description ?? ''}
              onChange={(value) => set('hero_description', value)}
              maxLength={1000}
            />
          )}
        </Field>

        <Grid columns={3}>
          <Field label="Button text">
            {(id) => (
              <TextInput
                id={id}
                value={form.hero_cta_text ?? ''}
                onChange={(value) => set('hero_cta_text', value)}
                maxLength={80}
              />
            )}
          </Field>
          <Field label="Button link">
            {(id) => (
              <TextInput
                id={id}
                type="url"
                value={form.hero_cta_url ?? ''}
                onChange={(value) => set('hero_cta_url', value)}
                placeholder="https://…"
              />
            )}
          </Field>
          <Field label="Button goes to">
            {(id) => (
              <Select
                id={id}
                value={form.hero_cta_behaviour ?? 'services'}
                onChange={(value) =>
                  set('hero_cta_behaviour', value as SiteSettingsInput['hero_cta_behaviour'])
                }
              >
                {CTA_BEHAVIOURS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </Grid>
      </Card>

      <Card title="About" description="The story shown in the about section.">
        <Grid>
          <Field label="Title">
            {(id) => (
              <TextInput
                id={id}
                value={form.about_title ?? ''}
                onChange={(value) => set('about_title', value)}
                maxLength={200}
              />
            )}
          </Field>
          <Field label="Image URL">
            {(id) => (
              <TextInput
                id={id}
                type="url"
                value={form.about_image ?? ''}
                onChange={(value) => set('about_image', value)}
                placeholder="https://…"
              />
            )}
          </Field>
        </Grid>
        <Field label="Content">
          {(id) => (
            <TextArea
              id={id}
              value={form.about_content ?? ''}
              onChange={(value) => set('about_content', value)}
              maxLength={5000}
              style={{ minHeight: 160 }}
            />
          )}
        </Field>
      </Card>

      <ThemePicker
        themes={themes}
        active={form.active_theme ?? null}
        onSelect={(id) => {
          set('active_theme', id)
          // A preset is a complete colour set, so switching clears any manual
          // overrides rather than carrying the old theme's tweaks across.
          set('theme_overrides', {})
        }}
        busy={busy}
      />

      <ColorOverrides
        themes={themes}
        activeTheme={form.active_theme ?? null}
        overrides={overrides}
        onChange={setOverride}
        onReset={resetOverrides}
      />

      <FontPicker
        fonts={fonts}
        active={form.active_font ?? null}
        onSelect={(id) => set('active_font', id)}
      />
    </form>
  )
}

function ThemePicker({
  themes,
  active,
  onSelect,
  busy,
}: {
  themes: ThemeEntry[]
  active: string | null
  onSelect: (id: string) => void
  busy: boolean
}) {
  return (
    <Card
      title="Theme"
      description="A curated preset. Custom CSS is not supported, by design."
    >
      <div className="picker-grid">
        {themes.map((theme) => (
          <button
            key={theme.id}
            type="button"
            disabled={busy}
            className={theme.id === active ? 'picker picker--active' : 'picker'}
            onClick={() => onSelect(theme.id)}
            aria-pressed={theme.id === active}
          >
            <div className="swatch-row">
              {['primary', 'secondary', 'accent', 'background', 'surface', 'text'].map((token) => (
                <div
                  key={token}
                  className="swatch"
                  style={{ background: theme.tokens[token] }}
                  title={`${token}: ${theme.tokens[token]}`}
                />
              ))}
            </div>
            <div className="cell-title">{theme.name}</div>
            <div className="cell-sub">{theme.description}</div>
          </button>
        ))}
      </div>
    </Card>
  )
}

function ColorOverrides({
  themes,
  activeTheme,
  overrides,
  onChange,
  onReset,
}: {
  themes: ThemeEntry[]
  activeTheme: string | null
  overrides: Record<string, string>
  onChange: (key: string, value: string | null) => void
  onReset: () => void
}) {
  const theme = themes.find((entry) => entry.id === activeTheme) ?? themes[0]
  const base = theme?.tokens ?? {}
  const preview = { ...base, ...overrides }

  const invalid = COLOR_TOKENS.filter(
    ({ key }) => overrides[key] !== undefined && !HEX_COLOR.test(overrides[key]),
  )
  const problems = invalid.map(({ label }) => `${label}: enter a HEX colour such as #B76E79.`)

  const contrastWarnings = (
    [
      ['Text on background', 'text', 'background'],
      ['Text on surface', 'text', 'surface'],
      ['Button label on button', 'button_text', 'button_bg'],
    ] as const
  ).flatMap(([label, first, second]) => {
    const ratio = contrastRatio(preview[first] ?? '', preview[second] ?? '')
    if (ratio === null || ratio >= 4.5) return []
    return [`${label} (${ratio.toFixed(2)}:1, below WCAG AA 4.5:1)`]
  })

  return (
    <Card
      title="Website colours"
      description={`Override colours for the public site. Values left at their theme default follow "${
        theme?.name ?? 'the active theme'
      }".`}
      footer={
        <Button
          type="button"
          variant="secondary"
          onClick={onReset}
          disabled={Object.keys(overrides).length === 0}
        >
          Reset to theme defaults
        </Button>
      }
    >
      {problems.length > 0 && <Banner tone="error">{problems.join(' ')}</Banner>}
      {contrastWarnings.length > 0 && (
        <p className="color-note">
          Contrast check: {contrastWarnings.join('; ')}. Choose a darker or lighter colour for
          legibility.
        </p>
      )}

      <div className="color-grid">
        {COLOR_TOKENS.map(({ key, label }) => {
          const value = overrides[key]
          const shown = preview[key] ?? '#000000'
          const isCustom = value !== undefined
          const isValid = !isCustom || HEX_COLOR.test(value)
          return (
            <Field
              key={key}
              label={label}
              hint={isCustom ? 'Custom' : 'Theme default'}
              error={isValid ? undefined : 'Invalid HEX colour'}
            >
              {(id) => (
                <div className="color-field">
                  <input
                    type="color"
                    id={`${id}-swatch`}
                    aria-label={`${label} colour picker`}
                    value={HEX_COLOR.test(shown) ? expandHex(shown) : '#000000'}
                    onChange={(event) => onChange(key, event.target.value)}
                  />
                  <TextInput
                    id={id}
                    value={value ?? ''}
                    placeholder={base[key] ?? '#000000'}
                    onChange={(next) => onChange(key, next === '' ? null : next)}
                    spellCheck={false}
                    autoComplete="off"
                  />
                </div>
              )}
            </Field>
          )
        })}
      </div>

      <div className="color-preview">
        <p className="muted">Live preview</p>
        <div
          className="color-preview__surface"
          style={{ background: preview.surface, color: preview.text, borderColor: preview.border }}
        >
          <strong>Priya Sharma</strong>
          <p style={{ color: preview.muted_text }}>Bridal makeup · 60 min</p>
          <span className="color-preview__accent" style={{ background: preview.accent }} />
          <span
            className="color-preview__button"
            style={{ background: preview.button_bg, color: preview.button_text }}
          >
            Book now
          </span>
        </div>
      </div>
    </Card>
  )
}

function FontPicker({
  fonts,
  active,
  onSelect,
}: {
  fonts: FontEntry[]
  active: string | null
  onSelect: (id: string) => void
}) {
  return (
    <Card title="Fonts" description="A curated heading and body pairing. Custom font URLs are not accepted.">
      <div className="picker-grid">
        {fonts.map((font) => (
          <button
            key={font.id}
            type="button"
            className={font.id === active ? 'picker picker--active' : 'picker'}
            onClick={() => onSelect(font.id)}
            aria-pressed={font.id === active}
          >
            {/* The stacks are curated static strings from the backend catalogue,
                never admin input, so they are safe to apply as a font-family. */}
            <div className="font-sample" style={{ fontFamily: font.heading_stack }}>
              {font.name}
            </div>
            <div className="font-sample--body" style={{ fontFamily: font.body_stack }}>
              {font.heading_family} + {font.body_family}
            </div>
            <div className="cell-sub">{font.description}</div>
          </button>
        ))}
      </div>
    </Card>
  )
}
