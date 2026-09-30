// Typed API client. Same-origin requests (Vite proxy in dev, nginx in prod) so the
// session + CSRF cookies stay first-party. Every failure becomes an ApiError with a
// `kind` the UI can turn into a friendly, bilingual message with a retry button.

import type { ApiErrorBody, Language, SessionCreated, SessionDetail, Turn } from './types'

const API_BASE = import.meta.env.VITE_API_URL || ''
// An agent turn can involve several LLM + tool round-trips; allow generous time.
export const MESSAGE_TIMEOUT_MS = 90_000
const DEFAULT_TIMEOUT_MS = 15_000

export type ApiErrorKind =
  | 'network' // offline / DNS / connection refused
  | 'timeout'
  | 'rate_limited' // 429 (per-IP, per-session or the daily demo cap)
  | 'session_limit' // 409: conversation reached its message limit
  | 'not_found' // session missing or not owned by this browser
  | 'csrf' // stale CSRF token/session (reload fixes it)
  | 'validation' // 400
  | 'server' // 5xx or unexpected

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number
  readonly code: string
  readonly serverMessage?: { en: string; ar: string }
  readonly retryAfterSeconds?: number

  constructor(
    kind: ApiErrorKind,
    status = 0,
    body?: ApiErrorBody['error'],
  ) {
    super(body?.message_en ?? kind)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.code = body?.code ?? kind
    if (body) this.serverMessage = { en: body.message_en, ar: body.message_ar }
    const retry = body?.details?.retry_after_seconds
    if (typeof retry === 'number') this.retryAfterSeconds = retry
  }

  /** Worth offering a "Try again" button? */
  get retryable(): boolean {
    return ['network', 'timeout', 'rate_limited', 'server', 'csrf'].includes(this.kind)
  }
}

export function kindForStatus(status: number, code?: string): ApiErrorKind {
  if (status === 429) return 'rate_limited'
  if (status === 409) return 'session_limit'
  if (status === 404) return 'not_found'
  if (status === 403 && code === 'csrf_failed') return 'csrf'
  if (status >= 400 && status < 500) return 'validation'
  return 'server'
}

function getCookie(name: string): string {
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.split('=')[1]) : ''
}

let csrfReady: Promise<void> | null = null

/** Django sets the csrftoken cookie on this endpoint (template convention). */
export function ensureCsrf(force = false): Promise<void> {
  if (force || !csrfReady) {
    csrfReady = fetch(`${API_BASE}/api/csrf-token/`, { credentials: 'include' }).then(() => undefined)
  }
  return csrfReady
}

async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  body?: unknown,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  if (method !== 'GET') await ensureCsrf().catch(() => undefined)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      credentials: 'include',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined && { 'Content-Type': 'application/json' }),
        ...(method !== 'GET' && { 'X-CSRFToken': getCookie('csrftoken') }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (err) {
    throw new ApiError(err instanceof DOMException && err.name === 'AbortError' ? 'timeout' : 'network')
  } finally {
    clearTimeout(timer)
  }

  if (response.ok) return (await response.json()) as T

  let errorBody: ApiErrorBody['error'] | undefined
  try {
    errorBody = ((await response.json()) as ApiErrorBody).error
  } catch {
    errorBody = undefined // non-JSON error (e.g. a proxy's HTML 502 page)
  }
  const kind = kindForStatus(response.status, errorBody?.code)
  if (kind === 'csrf') ensureCsrf(true).catch(() => undefined) // refresh for the retry
  throw new ApiError(kind, response.status, errorBody)
}

export const api = {
  createSession: (language: Language) =>
    request<SessionCreated>('POST', '/api/chat/sessions/', { language }),
  getSession: (sessionId: string) =>
    request<SessionDetail>('GET', `/api/chat/sessions/${sessionId}/`),
  sendMessage: (sessionId: string, content: string) =>
    request<Turn>('POST', `/api/chat/sessions/${sessionId}/messages/`, { content }, MESSAGE_TIMEOUT_MS),
}
