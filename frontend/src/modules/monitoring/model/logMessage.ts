import type { TFunction } from 'i18next';

import i18n from '@/i18n';
import { maskText } from '@/modules/monitoring/model/mask';

const GIB = 1024 ** 3;
const MIB = 1024 ** 2;

function asBytes(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() && value !== '—') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function formatSigned(bytes: number, locale: string): string {
  const abs = Math.abs(bytes);
  const mib = abs / MIB;
  const body =
    mib >= 1024
      ? formatGiB(abs, locale)
      : `${new Intl.NumberFormat(locale, {
          minimumFractionDigits: mib >= 10 || mib === 0 ? 0 : 1,
          maximumFractionDigits: mib >= 10 || mib === 0 ? 0 : 1,
        }).format(mib)} MiB`;
  if (bytes > 0) return `+${body}`;
  if (bytes < 0) return `−${body}`;
  return body;
}

function formatGiB(bytes: number, locale: string): string {
  const value = bytes / GIB;
  const digits = Math.abs(value) >= 10 ? 1 : 2;
  return `${new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)} GiB`;
}

function formatShare(delta: number, actual: number, locale: string): string {
  if (!actual) return '—';
  const pct = (delta / actual) * 100;
  const body = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Math.abs(pct));
  if (pct > 0) return `+${body} %`;
  if (pct < 0) return `−${body} %`;
  return `${body} %`;
}

function countText(value: unknown): string | null {
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'string' && value.trim() && value !== '—') return value;
  return null;
}

/** Human units for the VRAM compare line. Raw byte fields stay on the payload. */
export function vramLogVars(payload: Record<string, unknown>, locale: string): Record<string, unknown> {
  const estimated = asBytes(payload.estimatedBytes);
  const used = asBytes(payload.actualVramBytes);
  const delta =
    asBytes(payload.deltaBytes) ?? (estimated != null && used != null ? used - estimated : null);
  const gpu = countText(payload.numGpu);
  const cpu = countText(payload.numCpuMoe);
  const placement = [gpu != null ? `num_gpu ${gpu}` : '', cpu != null ? `num_cpu_moe ${cpu}` : '']
    .filter(Boolean)
    .join(', ');
  return {
    ...payload,
    estimated: estimated == null ? '—' : formatGiB(estimated, locale),
    used: used == null ? '—' : formatGiB(used, locale),
    delta: delta == null ? '—' : formatSigned(delta, locale),
    percent: delta == null || used == null ? '—' : formatShare(delta, used, locale),
    placement: placement ? `, ${placement}` : '',
  };
}

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
  const translated = t(key, message === 'run.llm.vram' ? vramLogVars(vars, i18n.language) : vars);
  if (typeof translated === 'string' && translated && translated !== key) return translated;
  return maskText(message);
}

export function formatChatBody(
  message: { content: string; messageKey?: string; messageParams?: Record<string, unknown> },
  t: TFunction,
): string {
  const key = message.messageKey;
  if (key) {
    const translated = t(key, message.messageParams ?? {});
    if (typeof translated === 'string' && translated && translated !== key) return translated;
  }
  return message.content;
}
