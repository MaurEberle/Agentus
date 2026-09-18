import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import de from '@/i18n/locales/de.json';
import en from '@/i18n/locales/en.json';

const STORAGE_KEY = 'i18nextLng';

function readStoredLanguage(): 'de' | 'en' {
  if (typeof window === 'undefined') return 'de';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'en' ? 'en' : 'de';
}

function applyDocumentLang(lng: string) {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = lng;
}

void i18n.use(initReactI18next).init({
  resources: {
    de: { translation: de },
    en: { translation: en },
  },
  lng: readStoredLanguage(),
  fallbackLng: 'de',
  supportedLngs: ['de', 'en'],
  interpolation: { escapeValue: false },
});

applyDocumentLang(i18n.language);

i18n.on('languageChanged', (lng) => {
  window.localStorage.setItem(STORAGE_KEY, lng);
  applyDocumentLang(lng);
});

export async function setAppLanguage(lng: 'de' | 'en') {
  await i18n.changeLanguage(lng);
}

export default i18n;
