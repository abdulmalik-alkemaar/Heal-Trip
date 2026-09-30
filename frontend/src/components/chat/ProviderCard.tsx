// Rendered ONLY from API `providers[]`, which the backend serializes from the database.
// Nothing here comes from LLM text.

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { DoctorCard, Language } from '../../api/types'
import { formatNumber, formatSlot, pick } from '../../lib/format'

function Badge({ children, tone }: { children: ReactNode; tone: 'blue' | 'green' | 'slate' }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
    green: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
    slate: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  }
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>
}

export default function ProviderCard({ doctor }: { doctor: DoctorCard }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Language
  const hospital = doctor.hospital
  const sep = lang === 'ar' ? '، ' : ', '
  return (
    <article
      data-provider-id={doctor.provider_id}
      className="rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 text-start">
          <h4 className="font-semibold text-slate-900 dark:text-slate-100">{pick(doctor, 'name', lang)}</h4>
          <p className="text-slate-600 dark:text-slate-400">
            {doctor.specialties.map((s) => pick(s, 'name', lang)).join(sep)}
          </p>
        </div>
        {doctor.rating && <Badge tone="slate">★ {doctor.rating}</Badge>}
      </div>

      <p className="mt-1.5 text-start text-slate-700 dark:text-slate-300">
        {pick(hospital, 'name', lang)} — {pick(hospital, 'city_name', lang)}
        {hospital.accreditation && (
          <span className="ms-1 text-xs text-slate-500">({t('provider.accreditation', { value: hospital.accreditation })})</span>
        )}
      </p>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {doctor.offers_second_opinion && <Badge tone="blue">{t('provider.secondOpinion')}</Badge>}
        {doctor.offers_telemedicine && <Badge tone="green">{t('provider.telemedicine')}</Badge>}
        {hospital.has_emergency && <Badge tone="slate">{t('provider.er')}</Badge>}
      </div>

      <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 text-xs text-slate-600 sm:grid-cols-2 dark:text-slate-400">
        <div>
          <dt className="inline">{t('provider.languages')}: </dt>
          <dd className="inline">{doctor.languages.map((l) => t(`languages.${l}`)).join(sep)}</dd>
        </div>
        <div>
          <dt className="inline">{t('provider.feeLabel')}: </dt>
          <dd className="inline">{t('provider.fee', { fee: formatNumber(doctor.consultation_fee_sar, lang) })}</dd>
        </div>
        <div>
          <dd className="inline">{t('provider.experience', { count: doctor.years_experience })}</dd>
        </div>
        <div>
          <dt className="inline">{t('provider.nextAvailable')}: </dt>
          <dd className="inline">
            {doctor.next_available ? formatSlot(doctor.next_available, lang) : t('provider.noSlots')}
          </dd>
        </div>
      </dl>
    </article>
  )
}
