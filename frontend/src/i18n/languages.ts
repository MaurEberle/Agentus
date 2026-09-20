export const APP_LANGUAGES = ['de', 'en', 'es', 'fr', 'tr', 'pt', 'zh', 'ja', 'ar'] as const;

export type AppLanguage = (typeof APP_LANGUAGES)[number];

export const LANGUAGE_LABEL_KEYS: Record<AppLanguage, `shell.language${Capitalize<AppLanguage>}`> = {
  de: 'shell.languageDe',
  en: 'shell.languageEn',
  es: 'shell.languageEs',
  fr: 'shell.languageFr',
  tr: 'shell.languageTr',
  pt: 'shell.languagePt',
  zh: 'shell.languageZh',
  ja: 'shell.languageJa',
  ar: 'shell.languageAr',
};

export const LANGUAGE_NAME_KEYS: Record<AppLanguage, `shell.languageNames.${AppLanguage}`> = {
  de: 'shell.languageNames.de',
  en: 'shell.languageNames.en',
  es: 'shell.languageNames.es',
  fr: 'shell.languageNames.fr',
  tr: 'shell.languageNames.tr',
  pt: 'shell.languageNames.pt',
  zh: 'shell.languageNames.zh',
  ja: 'shell.languageNames.ja',
  ar: 'shell.languageNames.ar',
};

export function formatLanguageOptionLabel(native: string, translated: string): string {
  const own = native.trim();
  const local = translated.trim();
  if (!local || local === own) return own;
  return `${own} (${local})`;
}

const RTL_LANGUAGES: ReadonlySet<AppLanguage> = new Set(['ar']);

export function isAppLanguage(value: string | undefined): value is AppLanguage {
  return Boolean(value) && (APP_LANGUAGES as readonly string[]).includes(value as string);
}

export function languageDirection(value: AppLanguage): 'ltr' | 'rtl' {
  return RTL_LANGUAGES.has(value) ? 'rtl' : 'ltr';
}

export function resolveAppLanguage(value: string | undefined): AppLanguage {
  const base = (value ?? 'de').split('-')[0]?.toLowerCase();
  return isAppLanguage(base) ? base : 'de';
}
