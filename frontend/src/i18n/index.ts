import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import ar from '@/i18n/locales/ar.json';
import de from '@/i18n/locales/de.json';
import en from '@/i18n/locales/en.json';
import es from '@/i18n/locales/es.json';
import fr from '@/i18n/locales/fr.json';
import ja from '@/i18n/locales/ja.json';
import pt from '@/i18n/locales/pt.json';
import tr from '@/i18n/locales/tr.json';
import zh from '@/i18n/locales/zh.json';
import {
  APP_LANGUAGES,
  type AppLanguage,
  languageDirection,
  resolveAppLanguage,
} from '@/i18n/languages';

export type { AppLanguage } from '@/i18n/languages';
export {
  APP_LANGUAGES,
  LANGUAGE_LABEL_KEYS,
  isAppLanguage,
  languageDirection,
  resolveAppLanguage,
} from '@/i18n/languages';

const STORAGE_KEY = 'i18nextLng';

function readStoredLanguage(): AppLanguage {
  if (typeof window === 'undefined') return 'de';
  return resolveAppLanguage(window.localStorage.getItem(STORAGE_KEY) ?? undefined);
}

function applyDocumentLang(lng: string) {
  if (typeof document === 'undefined') return;
  const resolved = resolveAppLanguage(lng);
  document.documentElement.lang = resolved;
  document.documentElement.dir = languageDirection(resolved);
}

void i18n.use(initReactI18next).init({
  resources: {
    de: { translation: de },
    en: { translation: en },
    es: { translation: es },
    fr: { translation: fr },
    tr: { translation: tr },
    pt: { translation: pt },
    zh: { translation: zh },
    ja: { translation: ja },
    ar: { translation: ar },
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
