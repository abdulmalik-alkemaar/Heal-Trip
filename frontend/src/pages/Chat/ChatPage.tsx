import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Language } from '../../api/types'
import Composer from '../../components/chat/Composer'
import ErrorNotice from '../../components/chat/ErrorNotice'
import ExamplePrompts from '../../components/chat/ExamplePrompts'
import MessageList from '../../components/chat/MessageList'
import TracePanel from '../../components/chat/TracePanel'
import { useChat } from '../../hooks/useChat'
import { setLanguage } from '../../i18n'

export default function ChatPage() {
  const { t, i18n } = useTranslation()
  const uiLanguage: Language = i18n.language === 'ar' ? 'ar' : 'en'
  const chat = useChat(uiLanguage)
  const [traceOpen, setTraceOpen] = useState(false)

  const pickExample = async (text: string, lang: Language) => {
    if (lang !== uiLanguage) await setLanguage(lang)
    void chat.send(text, lang)
  }

  const languageMismatch = chat.sessionLanguage !== null && chat.sessionLanguage !== uiLanguage
  const empty = chat.entries.length === 0

  return (
    <div className="flex gap-6">
      <section className="flex min-h-[calc(100vh-9.5rem)] min-w-0 flex-1 flex-col">
        <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
          {!empty && (
            <button type="button" onClick={chat.reset} disabled={chat.sending} className="btn-secondary px-3 py-1.5 text-xs">
              {t('nav.newChat')}
            </button>
          )}
          <button
            type="button"
            onClick={() => setTraceOpen((o) => !o)}
            aria-expanded={traceOpen}
            aria-controls="agent-trace"
            className="btn-secondary px-3 py-1.5 text-xs"
          >
            {traceOpen ? t('nav.hideTrace') : t('nav.showTrace')}
          </button>
        </div>

        <div className="flex-1">
          {chat.restoring ? (
            <p className="py-10 text-center text-sm text-slate-500">{t('chat.loadingHistory')}</p>
          ) : empty ? (
            <ExamplePrompts onPick={pickExample} disabled={chat.sending} />
          ) : (
            <MessageList entries={chat.entries} sending={chat.sending} onQuickReply={(text) => void chat.send(text)} />
          )}
        </div>

        <div className="sticky bottom-0 mt-4 space-y-2 bg-slate-50 pb-2 pt-2 dark:bg-slate-950">
          {chat.error && <ErrorNotice error={chat.error} onRetry={chat.retry} onReset={chat.reset} />}
          {languageMismatch && (
            <p className="text-start text-xs text-slate-500">
              {t('chat.languageLocked', { language: t(`languages.${chat.sessionLanguage}`) })}
            </p>
          )}
          {chat.messagesRemaining !== null && chat.messagesRemaining <= 10 && (
            <p className="text-start text-xs text-amber-600">{t('chat.messagesRemaining', { count: chat.messagesRemaining })}</p>
          )}
          <Composer onSend={(text) => void chat.send(text)} disabled={chat.sending || chat.restoring} />
        </div>
      </section>

      {traceOpen && (
        <>
          {/* Mobile: overlay drawer. Desktop: side column. */}
          <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setTraceOpen(false)} aria-hidden />
          <aside
            id="agent-trace"
            aria-label={t('trace.title')}
            className="fixed inset-y-0 end-0 z-40 w-full max-w-md overflow-y-auto border-s border-slate-200 bg-white p-4 shadow-xl lg:static lg:z-auto lg:w-96 lg:max-w-none lg:shrink-0 lg:rounded-xl lg:border lg:shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="mb-2 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">{t('trace.title')}</h2>
              <button type="button" onClick={() => setTraceOpen(false)} className="rounded p-1 text-slate-500 hover:bg-slate-100 lg:hidden dark:hover:bg-slate-800" aria-label={t('nav.hideTrace')}>
                ✕
              </button>
            </div>
            <TracePanel turn={chat.lastTurn} />
          </aside>
        </>
      )}
    </div>
  )
}
