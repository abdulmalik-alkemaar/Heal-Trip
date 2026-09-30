import { useTranslation } from 'react-i18next'
import type { NextStep, Urgency } from '../../api/types'

const STYLES: Record<Urgency, string> = {
  EMERGENCY: 'bg-red-600 text-white border-red-700',
  URGENT: 'bg-amber-50 text-amber-900 border-amber-300 dark:bg-amber-950 dark:text-amber-100 dark:border-amber-800',
  ROUTINE: 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700',
  UNKNOWN: 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700',
}

interface Props {
  urgency: Urgency
  nextStep: NextStep
}

export default function UrgencyBanner({ urgency, nextStep }: Props) {
  const { t } = useTranslation()
  const isEmergency = urgency === 'EMERGENCY'
  return (
    <div
      role={isEmergency ? 'alert' : 'status'}
      data-urgency={urgency}
      className={`rounded-lg border px-3 py-2 text-sm ${STYLES[urgency]}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-start">
          <span className="font-bold">{t(`urgency.${urgency}`)}</span>
          <span className="mx-1.5 opacity-60">·</span>
          <span className="font-medium">{t(`nextStep.${nextStep}`)}</span>
          <p className="mt-0.5 opacity-90">{t(`urgency.${urgency}_desc`)}</p>
        </div>
        {isEmergency && (
          <a
            href="tel:997"
            className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-base font-bold text-red-700 shadow hover:bg-red-50"
          >
            <span aria-hidden>📞</span>
            {t('emergency.callNow')}
          </a>
        )}
      </div>
    </div>
  )
}
