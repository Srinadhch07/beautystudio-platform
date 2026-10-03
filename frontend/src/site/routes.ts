/**
 * Public route definitions.
 *
 * The admin panel shares the same hash namespace, so the boundary between the
 * two apps is declared here rather than inside a component.
 */

export const ADMIN_PREFIX = '/admin'

/** True when the hash points at the admin panel rather than the public site. */
export function isAdminRoute(path: string): boolean {
  return path === ADMIN_PREFIX || path.startsWith(`${ADMIN_PREFIX}/`)
}
