/** Shared 401 → `#/auth` redirect for platform-mode SPA sessions. */

export const HERMES_UNAUTHORIZED_EVENT = 'hermes:unauthorized'

/** When true, gateway `/api/*` 401s also jump to `#/auth` (not KeyPromptModal-only). */
let platformUnauthorizedRedirect = false

export function setPlatformUnauthorizedRedirect(enabled: boolean): void {
  platformUnauthorizedRedirect = enabled
}

export function shouldRedirectGatewayUnauthorized(): boolean {
  return platformUnauthorizedRedirect
}

/** Auth write paths: failed login must not bounce the user off the form. */
const PLATFORM_AUTH_EXEMPT = new Set([
  '/auth/login',
  '/auth/register',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/logout',
  '/auth/deactivate',
])

export function isPlatformAuthExemptPath(path: string): boolean {
  const bare = path.split('?')[0] ?? path
  return PLATFORM_AUTH_EXEMPT.has(bare)
}

const GATEWAY_AUTH_EXEMPT = new Set(['/api/auth/login'])

export function isGatewayAuthExemptPath(path: string): boolean {
  const bare = path.split('?')[0] ?? path
  return GATEWAY_AUTH_EXEMPT.has(bare)
}

/**
 * Clear-session signal + navigate to `#/auth` unless already on a public/auth hash.
 * Listeners (App) should `setUser(null)` on {@link HERMES_UNAUTHORIZED_EVENT}.
 */
export function handleUnauthorizedRedirect(): void {
  if (typeof window === 'undefined') return
  const raw = (window.location.hash || '').replace(/^#\/?/, '')
  const path = raw.split('?')[0] ?? ''
  const stay =
    path === 'auth' ||
    path === 'reset-password' ||
    path === 'share' ||
    path.startsWith('share/')
  if (!stay) {
    window.location.hash = '#/auth'
  }
  window.dispatchEvent(new CustomEvent(HERMES_UNAUTHORIZED_EVENT))
}
