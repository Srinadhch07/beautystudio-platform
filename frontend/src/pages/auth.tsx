import { useState } from 'react'
import type { FormEvent } from 'react'

import { Banner, Button, Card, Field, TextInput } from '@/components/ui'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useMutation } from '@/lib/hooks'

export function LoginPage({ onForgot }: { onForgot: () => void }) {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, run } = useMutation()

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await run(() => signIn(email.trim(), password))
  }

  return (
    <div className="auth">
      <div className="auth__card">
        <div className="auth__head">
          <div className="auth__mark">BP</div>
          <h1>Admin sign in</h1>
          <p className="muted">Manage your parlour content.</p>
        </div>

        <form onSubmit={onSubmit} className="stack">
          {error !== null && <Banner tone="error">{error}</Banner>}

          <Field label="Email">
            {(id) => (
              <TextInput
                id={id}
                type="email"
                value={email}
                onChange={setEmail}
                autoComplete="username"
                required
                autoFocus
              />
            )}
          </Field>

          <Field label="Password">
            {(id) => (
              <TextInput
                id={id}
                type="password"
                value={password}
                onChange={setPassword}
                autoComplete="current-password"
                required
              />
            )}
          </Field>

          <Button type="submit" busy={busy} disabled={busy}>
            Sign in
          </Button>
        </form>

        <div className="auth__foot">
          <button type="button" onClick={onForgot}>
            Forgot your password?
          </button>
        </div>
      </div>
    </div>
  )
}

export function ForgotPasswordPage({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState('')
  const { busy, error, done, run } = useMutation()

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await run(() => api.auth.forgotPassword(email.trim()))
  }

  return (
    <div className="auth">
      <div className="auth__card">
        <div className="auth__head">
          <h1>Reset your password</h1>
          <p className="muted">
            Enter your admin email and we will send you a reset link.
          </p>
        </div>

        {done ? (
          <Card>
            <p>
              If that address belongs to an account, a reset email is on its way. The link
              expires shortly.
            </p>
          </Card>
        ) : (
          <form onSubmit={onSubmit} className="stack">
            {error !== null && <Banner tone="error">{error}</Banner>}

            <Field label="Email">
              {(id) => (
                <TextInput
                  id={id}
                  type="email"
                  value={email}
                  onChange={setEmail}
                  autoComplete="username"
                  required
                  autoFocus
                />
              )}
            </Field>

            <Button type="submit" busy={busy} disabled={busy}>
              Send reset link
            </Button>
          </form>
        )}

        <div className="auth__foot">
          <button type="button" onClick={onBack}>
            Back to sign in
          </button>
        </div>
      </div>
    </div>
  )
}

export function ResetPasswordPage({ token, onDone }: { token: string; onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const { busy, error, run } = useMutation()

  const mismatch = confirm !== '' && password !== confirm

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (mismatch) return
    const ok = await run(() => api.auth.resetPassword(token, password))
    if (ok) onDone()
  }

  return (
    <div className="auth">
      <div className="auth__card">
        <div className="auth__head">
          <h1>Choose a new password</h1>
          <p className="muted">At least 12 characters, with upper and lower case and a digit.</p>
        </div>

        <form onSubmit={onSubmit} className="stack">
          {error !== null && <Banner tone="error">{error}</Banner>}

          <Field label="New password">
            {(id) => (
              <TextInput
                id={id}
                type="password"
                value={password}
                onChange={setPassword}
                autoComplete="new-password"
                required
                autoFocus
              />
            )}
          </Field>

          <Field label="Confirm password" error={mismatch ? 'Passwords do not match' : undefined}>
            {(id) => (
              <TextInput
                id={id}
                type="password"
                value={confirm}
                onChange={setConfirm}
                autoComplete="new-password"
                required
              />
            )}
          </Field>

          <Button type="submit" busy={busy} disabled={busy || mismatch}>
            Update password
          </Button>
        </form>
      </div>
    </div>
  )
}
