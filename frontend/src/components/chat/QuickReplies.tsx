import { useTranslation } from 'react-i18next'
import type { ClarifyingQuestion } from '../../api/types'

interface Props {
  questions: ClarifyingQuestion[]
  onPick: (answer: string) => void
  disabled: boolean
}

/** Clarifying questions with tap-to-answer chips (tapping sends the chip text). */
export default function QuickReplies({ questions, onPick, disabled }: Props) {
  const { t } = useTranslation()
  return (
    <ol className="space-y-2.5" aria-label={t('chat.quickRepliesLabel')}>
      {questions.map((q, index) => (
        <li key={q.question} className="text-start">
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
            {index + 1}. {q.question}
          </p>
          {q.quick_replies.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {q.quick_replies.map((reply) => (
                <button
                  key={reply}
                  type="button"
                  disabled={disabled}
                  onClick={() => onPick(reply)}
                  className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs text-blue-800 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200 dark:hover:bg-blue-900"
                >
                  {reply}
                </button>
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  )
}
