/**
 * Small data-loading helpers.
 *
 * Deliberately not a state library: each screen needs a list, a form and a save
 * action, and `useAsync` covers that without a dependency.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from './api'

/** Turns any thrown value into a message worth showing a user. */
export function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) {
    const fields = cause.fieldMessages
    return fields.length > 0 ? `${cause.message} (${fields.join('; ')})` : cause.message
  }
  if (cause instanceof Error) return cause.message
  return 'Something went wrong.'
}

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  /** Re-runs the loader, e.g. after a mutation. */
  reload: () => void
  setData: (value: T) => void
}

/**
 * Runs `loader` on mount and whenever `deps` change, ignoring results that
 * arrive after the component unmounts or after a newer run has started.
 */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)

  // Guards against a slow earlier request overwriting a newer one.
  const runId = useRef(0)

  useEffect(() => {
    const current = ++runId.current
    let active = true

    setLoading(true)
    loader()
      .then((result) => {
        if (active && current === runId.current) {
          setData(result)
          setError(null)
        }
      })
      .catch((cause: unknown) => {
        if (active && current === runId.current) setError(messageFor(cause))
      })
      .finally(() => {
        if (active && current === runId.current) setLoading(false)
      })

    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return { data, error, loading, reload, setData }
}

/** Tracks a one-shot mutation: in flight, error, and a success flag to clear. */
export function useMutation() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const run = useCallback(async (action: () => Promise<unknown>): Promise<boolean> => {
    setBusy(true)
    setError(null)
    setDone(false)
    try {
      await action()
      setDone(true)
      return true
    } catch (cause) {
      setError(messageFor(cause))
      return false
    } finally {
      setBusy(false)
    }
  }, [])

  return { busy, error, done, run, clear: () => setError(null) }
}
