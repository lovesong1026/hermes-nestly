/**
 * Hermes Platform SaaS — 50 VU chat SSE load test (FakeRunner, no real LLM).
 *
 * Prerequisites:
 *   - Platform + Gateway running (e.g. ./startplatform.sh)
 *   - Gateway started with HERMES_WEB_CHAT_FAKE_RUNNER=1
 *   - Test user has upstream key bound (or AutoProvisioner ready)
 *
 * Usage:
 *   k6 run -e BASE_URL=http://127.0.0.1:8700 \
 *     -e GATEWAY_URL=http://127.0.0.1:8643 \
 *     -e EMAIL=sse50@example.com -e PASSWORD='loadtest-password-123' \
 *     deploy/loadtest/k6-chat-sse.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { Trend, Rate, Counter } from 'k6/metrics'

const chatTtfb = new Trend('chat_sse_ttfb_ms')
const chatDone = new Trend('chat_sse_done_ms')
const chatOk = new Rate('chat_sse_ok')
const chatErrors = new Counter('chat_sse_errors')

const BASE = (__ENV.BASE_URL || 'http://127.0.0.1:8700').replace(/\/$/, '')
const EMAIL = __ENV.EMAIL || 'sse50@example.com'
const PASSWORD = __ENV.PASSWORD || 'loadtest-password-123'
const SKIP_REGISTER = (__ENV.SKIP_REGISTER || '') === '1'
const UPSTREAM_KEY = __ENV.UPSTREAM_KEY || 'sk-loadtest-fake-key'

function defaultGatewayUrl() {
  if (__ENV.GATEWAY_URL) return __ENV.GATEWAY_URL.replace(/\/$/, '')
  try {
    const u = new URL(BASE)
    if (u.port === '8700') {
      u.port = '8643'
      return u.toString().replace(/\/$/, '')
    }
  } catch (_) {
    /* keep BASE */
  }
  return BASE
}

const GATEWAY = defaultGatewayUrl()

export const options = {
  vus: Number(__ENV.VUS || 50),
  duration: __ENV.DURATION || '2m',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    chat_sse_ok: ['rate>0.95'],
    chat_sse_ttfb_ms: ['p(95)<3000'],
    chat_sse_done_ms: ['p(95)<8000'],
  },
}

export function setup() {
  const jar = http.cookieJar()
  if (!SKIP_REGISTER) {
    http.post(
      `${BASE}/api/v1/auth/register`,
      JSON.stringify({ email: EMAIL, password: PASSWORD }),
      {
        headers: { 'Content-Type': 'application/json' },
        jar,
        tags: { name: 'register' },
      },
    )
  }
  const login = http.post(
    `${BASE}/api/v1/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    {
      headers: { 'Content-Type': 'application/json' },
      jar,
      tags: { name: 'login' },
    },
  )
  if (login.status !== 200) {
    throw new Error(`login failed: ${login.status} ${login.body}`)
  }
  // Best-effort bind so pending_bind users can chat under FakeRunner
  http.post(
    `${BASE}/api/v1/auth/bind-key`,
    JSON.stringify({ api_key: UPSTREAM_KEY }),
    {
      headers: { 'Content-Type': 'application/json' },
      jar,
      tags: { name: 'bind_key' },
    },
  )
  return { ok: true }
}

export default function () {
  const jar = http.cookieJar()
  // Re-login per VU so cookies are present (setup jar does not transfer to VUs)
  const login = http.post(
    `${BASE}/api/v1/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    {
      headers: { 'Content-Type': 'application/json' },
      jar,
      tags: { name: 'login_vu' },
    },
  )
  if (login.status !== 200) {
    chatErrors.add(1)
    chatOk.add(0)
    sleep(1)
    return
  }

  const started = Date.now()
  const res = http.post(
    `${GATEWAY}/api/chat`,
    JSON.stringify({ message: `ping from vu ${__VU} iter ${__ITER}` }),
    {
      headers: { 'Content-Type': 'application/json' },
      jar,
      tags: { name: 'chat_sse' },
      timeout: '60s',
    },
  )
  const elapsed = Date.now() - started
  chatTtfb.add(res.timings.waiting)
  chatDone.add(elapsed)

  const body = res.body || ''
  const ok =
    res.status === 200 &&
    body.indexOf('event: done') >= 0 &&
    body.indexOf('event: error') < 0
  chatOk.add(ok ? 1 : 0)
  if (!ok) chatErrors.add(1)

  check(res, {
    'chat status 200': (r) => r.status === 200,
    'chat has done': (r) => (r.body || '').indexOf('event: done') >= 0,
  })

  sleep(Number(__ENV.SLEEP || 1))
}
