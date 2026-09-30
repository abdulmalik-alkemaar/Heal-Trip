import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import type { Language } from '../api/types'
import ar from './locales/ar.json'
import en from './locales/en.json'

const STORAGE_KEY = 'healtrip.lang'

function initialLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'ar' || stored === 'en') return stored
  } catch {
    // storage unavailable (private mode): fall through
  }
  return navigator.language?.toLowerCase().startsWith('ar') ? 'ar' : 'en'
}

/** Keep <html lang dir> in sync: Arabic is right-to-left. */
export function applyDocumentLanguage(language: Language): void {
  document.documentElement.lang = language
  document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr'
}

export async function setLanguage(language: Language): Promise<void> {
  await i18n.changeLanguage(language)
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // ignore
  }
}

i18n.on('languageChanged', (lng) => applyDocumentLanguage(lng === 'ar' ? 'ar' : 'en'))

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, ar: { translation: ar } },
  lng: initialLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false }, // React already escapes
})
applyDocumentLanguage(i18n.language === 'ar' ? 'ar' : 'en')

export default i18n
