import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, kindForStatus } from '../api/client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('kindForStatus', () => {
  it.each([
    [429, undefined, 'rate_limited'],
    [409, undefined, 'session_limit'],
    [404, undefined, 'not_found'],
    [403, 'csrf_failed', 'csrf'],
    [400, 'validation_error', 'validation'],
    [500, undefined, 'server'],
    [502, undefined, 'server'],
  ])('%i %s -> %s', (status, code, kind) => {
    expect(kindForStatus(status, code)).toBe(kind)
  })
})

describe('api client errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('turns a 429 into a retryable ApiError with retry-after', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes('csrf-token')
        ? jsonResponse(200, {})
        : jsonResponse(429, {
            error: { code: 'rate_limited', message_en: 'Too many', message_ar: 'كثير', details: { retry_after_seconds: 42 } },
          }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const error = await api.sendMessage('abc', 'hi').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).kind).toBe('rate_limited')
    expect((error as ApiError).retryAfterSeconds).toBe(42)
    expect((error as ApiError).retryable).toBe(true)
  })

  it('maps a network failure to kind=network', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    const error = (await api.getSession('abc').catch((e: unknown) => e)) as ApiError
    expect(error.kind).toBe('network')
  })

  it('handles a non-JSON 502 from a proxy', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>Bad Gateway</html>', { status: 502 })))
    const error = (await api.getSession('abc').catch((e: unknown) => e)) as ApiError
    expect(error.kind).toBe('server')
  })
})
