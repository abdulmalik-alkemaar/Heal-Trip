// Conversation state: session lifecycle, sending, retry, history restore.
// The session id is remembered per tab so a reload restores the conversation; the
// server still checks ownership via the session cookie (ids alone grant nothing).

import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { Language, Turn } from '../api/types'

const SESSION_KEY = 'healtrip.session'

export interface ChatEntry {
  id: string
  role: 'user' | 'assistant'
  content: string
  turn?: Turn
}

interface StoredSession {
  id: string
  language: Language
}

function loadStored(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as StoredSession) : null
  } catch {
    return null
  }
}

function store(session: StoredSession | null): void {
  try {
    if (session) sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // ignore
  }
}

export function useChat(uiLanguage: Language) {
  const [session, setSession] = useState<StoredSession | null>(loadStored)
  const [entries, setEntries] = useState<ChatEntry[]>([])
  const [sending, setSending] = useState(false)
  const [restoring, setRestoring] = useState(() => loadStored() !== null)
  const [error, setError] = useState<ApiError | null>(null)
  const [failedText, setFailedText] = useState<string | null>(null)
  const [messagesRemaining, setMessagesRemaining] = useState<number | null>(null)
  const inFlight = useRef(false)

  // Restore the conversation after a reload.
  useEffect(() => {
    const stored = loadStored()
    if (!stored) return
    api
      .getSession(stored.id)
      .then((detail) => {
        setEntries(
          detail.messages.map((m) => ({
            id: String(m.id),
            role: m.role,
            content: m.content,
            turn: m.turn ?? undefined,
          })),
        )
        setMessagesRemaining(detail.messages_remaining)
      })
      .catch(() => {
        store(null) // expired / purged / other browser: start fresh
        setSession(null)
      })
      .finally(() => setRestoring(false))
  }, [])

  const send = useCallback(
    async (text: string, language?: Language) => {
      const content = text.trim()
      if (!content || inFlight.current) return
      inFlight.current = true
      setSending(true)
      setError(null)
      setFailedText(null)
      const optimistic: ChatEntry = { id: `local-${Date.now()}`, role: 'user', content }
      setEntries((prev) => [...prev, optimistic])
      try {
        let active = session
        if (!active) {
          const created = await api.createSession(language ?? uiLanguage)
          active = { id: created.session_id, language: created.language }
          store(active)
          setSession(active)
        }
        const turn = await api.sendMessage(active.id, content)
        setEntries((prev) => [
          ...prev,
          { id: String(turn.message_id), role: 'assistant', content: turn.reply_text, turn },
        ])
        setMessagesRemaining((n) => (n === null ? null : Math.max(0, n - 1)))
      } catch (err) {
        const apiError = err instanceof ApiError ? err : new ApiError('server')
        // Remove the optimistic bubble; the text goes back to the composer via retry.
        setEntries((prev) => prev.filter((e) => e.id !== optimistic.id))
        setError(apiError)
        setFailedText(content)
        if (apiError.kind === 'not_found') {
          store(null)
          setSession(null)
        }
      } finally {
        inFlight.current = false
        setSending(false)
      }
    },
    [session, uiLanguage],
  )

  const retry = useCallback(() => {
    if (failedText) void send(failedText)
  }, [failedText, send])

  const reset = useCallback(() => {
    store(null)
    setSession(null)
    setEntries([])
    setError(null)
    setFailedText(null)
    setMessagesRemaining(null)
  }, [])

  const lastTurn = [...entries].reverse().find((e) => e.turn)?.turn ?? null

  return {
    entries,
    sending,
    restoring,
    error,
    failedText,
    retry,
    reset,
    send,
    lastTurn,
    sessionLanguage: session?.language ?? null,
    messagesRemaining,
  }
}
