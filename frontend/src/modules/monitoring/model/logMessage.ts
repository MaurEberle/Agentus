import type { TFunction } from 'i18next';
import { maskText } from '@/modules/monitoring/model/mask';

export function formatRunLogMessage(
  message: string,
  t: TFunction,
  payload?: unknown,
): string {
  const vars =
    payload && typeof payload === 'object' && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : {};
  const key = `runLog.${message}`;
  const translated = t(key, vars);
  if (typeof translated === 'string' && translated && translated !== key) return translated;
  return maskText(message);
}
