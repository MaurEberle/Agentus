export const APP_LANGUAGES = ['de', 'en', 'es'] as const;

export type AppLanguage = (typeof APP_LANGUAGES)[number];

export const LANGUAGE_LABEL_KEYS: Record<AppLanguage, `shell.language${Capitalize<AppLanguage>}`> = {
  de: 'shell.languageDe',
  en: 'shell.languageEn',
  es: 'shell.languageEs',
};

export function isAppLanguage(value: string | undefined): value is AppLanguage {
  return value === 'de' || value === 'en' || value === 'es';
}

export function resolveAppLanguage(value: string | undefined): AppLanguage {
  const base = (value ?? 'de').split('-')[0]?.toLowerCase();
  return isAppLanguage(base) ? base : 'de';
}
