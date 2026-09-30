import { useTranslation } from 'react-i18next'
import type { Emergency, Language } from '../../api/types'
import { pick } from '../../lib/format'

export default function EmergencyPanel({ emergency }: { emergency: Emergency }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Language
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-900 dark:bg-red-950/40">
      <h4 className="mb-2 font-semibold text-red-800 dark:text-red-200">{t('emergency.numbersTitle')}</h4>
      <div className="mb-3 flex flex-wrap gap-2">
        {emergency.numbers.map((n) => (
          <a
            key={n.number}
            href={`tel:${n.number}`}
            className="rounded-md border border-red-300 bg-white px-3 py-1.5 text-red-800 hover:bg-red-100 dark:border-red-800 dark:bg-slate-900 dark:text-red-200"
          >
            <span className="font-bold" dir="ltr">{n.number}</span>
            <span className="ms-2 text-xs">{pick(n, 'label', lang)}</span>
          </a>
        ))}
      </div>
      {emergency.hospitals.length > 0 && (
        <>
          <h4 className="mb-1 font-semibold text-red-800 dark:text-red-200">{t('emergency.nearestEr')}</h4>
          <ul className="space-y-1.5">
            {emergency.hospitals.map((h) => (
              <li key={h.hospital_id} className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-start">
                  <span className="font-medium text-slate-900 dark:text-slate-100">{pick(h, 'name', lang)}</span>
                  <span className="ms-1 text-slate-600 dark:text-slate-400">— {pick(h, 'city_name', lang)}</span>
                </span>
                {h.emergency_phone && (
                  <a href={`tel:${h.emergency_phone.replace(/\s/g, '')}`} className="text-red-700 underline dark:text-red-300" dir="ltr">
                    {h.emergency_phone}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
