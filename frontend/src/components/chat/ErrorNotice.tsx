import { useTranslation } from 'react-i18next'
import type { ApiError } from '../../api/client'

interface Props {
  error: ApiError
  onRetry: () => void
  onReset: () => void
}

/** Friendly, bilingual error with the right recovery action for each failure kind. */
export default function ErrorNotice({ error, onRetry, onReset }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ar' ? 'ar' : 'en'
  let message = t(`errors.${error.kind}`)
  if (error.code === 'daily_cap_reached' && error.serverMessage) {
    message = error.serverMessage[lang] // server explains the demo cap in both languages
  } else if (error.kind === 'rate_limited' && error.retryAfterSeconds) {
    message = t('errors.rate_limited_wait', { seconds: error.retryAfterSeconds })
  }
  const needsNewChat = error.kind === 'session_limit' || error.kind === 'not_found'

  return (
    <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
      <p className="text-start font-medium">{message}</p>
      <p className="mt-1 text-start text-xs">{t('errors.emergencyHint')}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {error.retryable && !needsNewChat && (
          <button type="button" onClick={onRetry} className="btn-secondary px-3 py-1.5 text-xs">
            {t('errors.retry')}
          </button>
        )}
        {needsNewChat && (
          <button type="button" onClick={onReset} className="btn-secondary px-3 py-1.5 text-xs">
            {t('errors.newChat')}
          </button>
        )}
      </div>
    </div>
  )
}
