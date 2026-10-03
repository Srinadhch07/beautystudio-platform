/**
 * Hash-based route reading, shared by the public site and the admin panel.
 *
 * The whole app is served as static files, so hash routes are what let a deep
 * link like `#/services` work on any host without a rewrite rule.
 */

import { useEffect, useState } from 'react'

/** Normalised path from `location.hash`, e.g. `/`, `/services`, `/admin/gallery`. */
export function currentPath(): string {
  const hash = window.location.hash.replace(/^#/, '')
  const path = hash.split('?')[0]
  return path === '' ? '/' : path.startsWith('/') ? path : `/${path}`
}

/** Subscribes to hash changes so components re-render on navigation. */
export function useHashPath(): string {
  const [path, setPath] = useState(currentPath)

  useEffect(() => {
    const onChange = () => setPath(currentPath())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return path
}

/** Returns the reader to the top of the page on navigation; a hash link alone does not. */
export function useScrollToTop(path: string): void {
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [path])
}
