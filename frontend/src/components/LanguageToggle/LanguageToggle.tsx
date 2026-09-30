import { useTranslation } from 'react-i18next'
import { setLanguage } from '../../i18n'

/** Switches UI language; i18n keeps <html lang dir> in sync (ar => rtl). */
export default function LanguageToggle() {
  const { t, i18n } = useTranslation()
  const next = i18n.language === 'ar' ? 'en' : 'ar'
  return (
    <button
      type="button"
      onClick={() => void setLanguage(next)}
      aria-label={t('nav.switchLanguageLabel')}
      lang={next}
      className="rounded-md px-2.5 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
    >
      {t('nav.switchLanguage')}
    </button>
  )
}
