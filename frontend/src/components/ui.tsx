/**
 * Shared UI primitives.
 *
 * Plain elements with class names rather than a component library: the panel
 * needs a form, a table, a dialog and a toast, and hand-rolling those four is
 * smaller than configuring a library to match.
 */

import { useEffect, useId, useRef } from 'react'
import type { ChangeEvent, ReactNode } from 'react'

// --- Layout ------------------------------------------------------------------

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {description !== undefined && <p className="muted">{description}</p>}
      </div>
      {actions !== undefined && <div className="page-header__actions">{actions}</div>}
    </header>
  )
}

export function Card({
  title,
  description,
  children,
  footer,
}: {
  title?: string
  description?: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <section className="card">
      {title !== undefined && (
        <div className="card__head">
          <h2>{title}</h2>
          {description !== undefined && <p className="muted">{description}</p>}
        </div>
      )}
      <div className="card__body">{children}</div>
      {footer !== undefined && <div className="card__foot">{footer}</div>}
    </section>
  )
}

export function Grid({ children, columns = 2 }: { children: ReactNode; columns?: number }) {
  return (
    <div
      className="grid"
      style={{ '--columns': columns } as React.CSSProperties}
    >
      {children}
    </div>
  )
}

// --- Feedback ----------------------------------------------------------------

export function Banner({
  tone = 'info',
  children,
  onDismiss,
}: {
  tone?: 'info' | 'success' | 'error'
  children: ReactNode
  onDismiss?: () => void
}) {
  return (
    <div className={`banner banner--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span>{children}</span>
      {onDismiss !== undefined && (
        <button type="button" className="banner__close" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="state" role="status">
      <span className="spinner" aria-hidden="true" />
      <p className="muted">{label}…</p>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="state">
      <h3>{title}</h3>
      {description !== undefined && <p className="muted">{description}</p>}
      {action}
    </div>
  )
}

export function Badge({
  tone = 'neutral',
  children,
}: {
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
  children: ReactNode
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}

// --- Controls ----------------------------------------------------------------

interface FieldProps {
  label: string
  hint?: string
  error?: string | null
  children: (id: string) => ReactNode
}

/** A labelled control with hint and error text, wired up for accessibility. */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint !== undefined && error === undefined && <small className="muted">{hint}</small>}
      {error !== undefined && error !== null && (
        <small className="field__error" role="alert">
          {error}
        </small>
      )}
    </div>
  )
}

export function TextInput({
  value,
  onChange,
  ...rest
}: {
  value: string
  onChange: (value: string) => void
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'>) {
  return (
    <input
      {...rest}
      value={value}
      onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
    />
  )
}

export function TextArea({
  value,
  onChange,
  ...rest
}: {
  value: string
  onChange: (value: string) => void
} & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'value' | 'onChange'>) {
  return (
    <textarea
      {...rest}
      value={value}
      onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange(event.target.value)}
    />
  )
}

export function Select({
  value,
  onChange,
  children,
  ...rest
}: {
  value: string
  onChange: (value: string) => void
  children: ReactNode
} & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'value' | 'onChange' | 'children'>) {
  return (
    <select
      {...rest}
      value={value}
      onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value)}
    >
      {children}
    </select>
  )
}

export function Checkbox({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
}) {
  return (
    <label className="checkbox">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.checked)}
      />
      <span>{label}</span>
    </label>
  )
}

export function Button({
  children,
  variant = 'primary',
  busy = false,
  ...rest
}: {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  busy?: boolean
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'>) {
  return (
    <button {...rest} className={`btn btn--${variant}`} disabled={busy || rest.disabled}>
      {busy ? <span className="spinner spinner--small" aria-hidden="true" /> : null}
      {children}
    </button>
  )
}

// --- Dialogs -----------------------------------------------------------------

/** A modal that closes on Escape and on backdrop click, and traps nothing else. */
export function Modal({
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    panel.current?.querySelector<HTMLElement>('input, select, textarea, button')?.focus()
  }, [])

  return (
    <div className="modal-backdrop" onMouseDown={onClose} role="presentation">
      <div
        ref={panel}
        className={wide ? 'modal modal--wide' : 'modal'}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal__head">
          <h2>{title}</h2>
          <button type="button" className="btn btn--ghost" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal__body">{children}</div>
        {footer !== undefined && <div className="modal__foot">{footer}</div>}
      </div>
    </div>
  )
}

/** Confirmation for destructive actions. */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Delete',
  busy = false,
  onConfirm,
  onCancel,
}: {
  title: string
  message: string
  confirmLabel?: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} busy={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p>{message}</p>
    </Modal>
  )
}
