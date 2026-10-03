/**
 * Session state for the admin panel.
 *
 * The session lives in an HttpOnly cookie, so there is no token to keep here.
 * "Signed in" simply means `GET /auth/me` succeeds, which is re-checked once on
 * mount to survive a page reload.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { ApiError, api, clearCsrfToken, setCsrfToken } from './api'
import type { AdminProfile } from '@/types/api'

interface AuthState {
  admin: AdminProfile | null
  /** True while the initial `me` check is in flight, so the shell can wait. */
  initialising: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<AdminProfile | null>(null)
  const [initialising, setInitialising] = useState(true)

  useEffect(() => {
    let active = true

    api
      .auth.me()
      .then((profile) => {
        if (active) setAdmin(profile)
      })
      .catch(() => {
        // Not signed in. This is the normal state on a fresh visit.
        if (active) setAdmin(null)
      })
      .finally(() => {
        if (active) setInitialising(false)
      })

    return () => {
      active = false
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.auth.login(email, password)
    setCsrfToken(result.csrf_token)
    setAdmin(result.admin)
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.auth.logout()
    } catch (cause) {
      // An expired session is already signed out as far as the user is concerned,
      // so only an unexpected failure is worth surfacing.
      if (!(cause instanceof ApiError)) throw cause
    } finally {
      clearCsrfToken()
      setAdmin(null)
    }
  }, [])

  const value = useMemo(
    () => ({ admin, initialising, signIn, signOut }),
    [admin, initialising, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (context === null) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
