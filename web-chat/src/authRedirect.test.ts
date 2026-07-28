import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  HERMES_UNAUTHORIZED_EVENT,
  handleUnauthorizedRedirect,
  isGatewayAuthExemptPath,
  isPlatformAuthExemptPath,
  setPlatformUnauthorizedRedirect,
  shouldRedirectGatewayUnauthorized,
} from './authRedirect'

describe('authRedirect', () => {
  afterEach(() => {
    setPlatformUnauthorizedRedirect(false)
    window.location.hash = ''
  })

  it('exempts platform auth write paths', () => {
    expect(isPlatformAuthExemptPath('/auth/login')).toBe(true)
    expect(isPlatformAuthExemptPath('/auth/register')).toBe(true)
    expect(isPlatformAuthExemptPath('/auth/forgot-password')).toBe(true)
    expect(isPlatformAuthExemptPath('/auth/reset-password')).toBe(true)
    expect(isPlatformAuthExemptPath('/auth/logout')).toBe(true)
    expect(isPlatformAuthExemptPath('/auth/deactivate')).toBe(true)
    expect(isPlatformAuthExemptPath('/auth/me')).toBe(false)
    expect(isPlatformAuthExemptPath('/workspaces/w1/files')).toBe(false)
  })

  it('exempts gateway key login only', () => {
    expect(isGatewayAuthExemptPath('/api/auth/login')).toBe(true)
    expect(isGatewayAuthExemptPath('/api/me')).toBe(false)
    expect(isGatewayAuthExemptPath('/api/chat')).toBe(false)
  })

  it('toggles gateway redirect flag', () => {
    expect(shouldRedirectGatewayUnauthorized()).toBe(false)
    setPlatformUnauthorizedRedirect(true)
    expect(shouldRedirectGatewayUnauthorized()).toBe(true)
  })

  it('navigates to #/auth and dispatches event', () => {
    window.location.hash = '#/chat'
    const spy = vi.fn()
    window.addEventListener(HERMES_UNAUTHORIZED_EVENT, spy)
    handleUnauthorizedRedirect()
    expect(window.location.hash).toBe('#/auth')
    expect(spy).toHaveBeenCalledTimes(1)
    window.removeEventListener(HERMES_UNAUTHORIZED_EVENT, spy)
  })

  it('does not rewrite hash when already on auth', () => {
    window.location.hash = '#/auth?mode=register'
    handleUnauthorizedRedirect()
    expect(window.location.hash).toBe('#/auth?mode=register')
  })

  it('does not leave public share hash', () => {
    window.location.hash = '#/share/tok_abc'
    handleUnauthorizedRedirect()
    expect(window.location.hash).toBe('#/share/tok_abc')
  })
})
