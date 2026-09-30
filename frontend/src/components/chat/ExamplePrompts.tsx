import { useTranslation } from 'react-i18next'
import type { Language } from '../../api/types'

// Examples in both languages regardless of the UI language. Each carries its own
// language so picking an Arabic example switches the UI (and the new session) to Arabic.
const EXAMPLES: { key: string; lang: Language }[] = [
  { key: 'chestPainTask', lang: 'en' }, // the exact example from the HealTrip brief
  { key: 'secondOpinion', lang: 'en' },
  { key: 'notFound', lang: 'en' },
  { key: 'arChestPain', lang: 'ar' },
  { key: 'arEmergency', lang: 'ar' },
  { key: 'arKnee', lang: 'ar' },
]

interface Props {
  onPick: (text: string, lang: Language) => void
  disabled: boolean
}

export default function ExamplePrompts({ onPick, disabled }: Props) {
  const { t } = useTranslation()
  return (
    <div className="mx-auto max-w-2xl py-8 text-center">
      <h2 className="text-xl font-bold text-slate-900 sm:text-2xl dark:text-slate-100">{t('chat.emptyTitle')}</h2>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{t('chat.emptySubtitle')}</p>
      <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">{t('chat.examplesTitle')}</h3>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {EXAMPLES.map(({ key, lang }) => {
          const text = t(`examples.${key}`)
          return (
            <button
              key={key}
              type="button"
              lang={lang}
              dir={lang === 'ar' ? 'rtl' : 'ltr'}
              disabled={disabled}
              onClick={() => onPick(text, lang)}
              className="rounded-lg border border-slate-200 bg-white p-3 text-start text-sm text-slate-700 hover:border-blue-300 hover:bg-blue-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              {text}
            </button>
          )
        })}
      </div>
    </div>
  )
}
