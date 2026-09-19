import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import de from '@/i18n/locales/de.json';
import en from '@/i18n/locales/en.json';
import es from '@/i18n/locales/es.json';
import { APP_LANGUAGES, type AppLanguage, resolveAppLanguage } from '@/i18n/languages';

export type { AppLanguage } from '@/i18n/languages';
export { APP_LANGUAGES, LANGUAGE_LABEL_KEYS, isAppLanguage, resolveAppLanguage } from '@/i18n/languages';

const STORAGE_KEY = 'i18nextLng';

function readStoredLanguage(): AppLanguage {
  if (typeof window === 'undefined') return 'de';
  return resolveAppLanguage(window.localStorage.getItem(STORAGE_KEY) ?? undefined);
}

function applyDocumentLang(lng: string) {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = resolveAppLanguage(lng);
}

void i18n.use(initReactI18next).init({
  resources: {
    de: { translation: de },
    en: { translation: en },
    es: { translation: es },
  },
  lng: readStoredLanguage(),
  fallbackLng: 'de',
  supportedLngs: [...APP_LANGUAGES],
  nonExplicitSupportedLngs: true,
  interpolation: { escapeValue: false },
});

applyDocumentLang(i18n.language);

i18n.on('languageChanged', (lng) => {
  const resolved = resolveAppLanguage(lng);
  window.localStorage.setItem(STORAGE_KEY, resolved);
  applyDocumentLang(resolved);
});

export async function setAppLanguage(lng: AppLanguage) {
  await i18n.changeLanguage(lng);
}

export default i18n;
