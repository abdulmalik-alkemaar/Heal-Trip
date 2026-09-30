import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import type { ChatEntry } from '../../hooks/useChat'
import EmergencyPanel from './EmergencyPanel'
import ProviderCard from './ProviderCard'
import QuickReplies from './QuickReplies'
import UrgencyBanner from './UrgencyBanner'

interface Props {
  entries: ChatEntry[]
  sending: boolean
  onQuickReply: (text: string) => void
}

export default function MessageList({ entries, sending, onQuickReply }: Props) {
  const { t } = useTranslation()
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [entries.length, sending])

  const lastAssistantIndex = entries.map((e) => e.role).lastIndexOf('assistant')

  return (
    <div className="space-y-4" aria-live="polite">
      {entries.map((entry, index) =>
        entry.role === 'user' ? (
          <div key={entry.id} className="flex justify-end">
            <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-ee-sm bg-blue-600 px-4 py-2 text-start text-sm text-white">
              <span className="sr-only">{t('chat.you')}: </span>
              {entry.content}
            </div>
          </div>
        ) : (
          <div key={entry.id} className="flex justify-start">
            <div className="w-full max-w-[95%] space-y-3 rounded-2xl rounded-es-sm border border-slate-200 bg-white px-4 py-3 shadow-sm sm:max-w-[85%] dark:border-slate-700 dark:bg-slate-900">
              <span className="sr-only">{t('chat.assistant')}: </span>
              {entry.turn && <UrgencyBanner urgency={entry.turn.urgency} nextStep={entry.turn.next_step} />}
              <p className="whitespace-pre-wrap text-start text-sm leading-relaxed text-slate-800 dark:text-slate-200">
                {entry.content}
              </p>
              {entry.turn?.emergency && <EmergencyPanel emergency={entry.turn.emergency} />}
              {entry.turn && entry.turn.clarifying_questions.length > 0 && (
                <QuickReplies
                  questions={entry.turn.clarifying_questions}
                  onPick={onQuickReply}
                  disabled={sending || index !== lastAssistantIndex}
                />
              )}
              {entry.turn && entry.turn.providers.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-start text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {t('chat.providersTitle')}
                  </h3>
                  {entry.turn.providers.map((doctor) => (
                    <ProviderCard key={doctor.provider_id} doctor={doctor} />
                  ))}
                </section>
              )}
            </div>
          </div>
        ),
      )}
      {sending && (
        <div className="flex justify-start" role="status">
          <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
            <span className="flex gap-1" aria-hidden>
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
            </span>
            {t('chat.typing')}
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}
