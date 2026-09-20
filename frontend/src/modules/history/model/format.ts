import type { LlmProvider, RunOutcome } from '@/modules/history/model/types';

export function pad2(value: number): string {
  return value.toString().padStart(2, '0');
}

export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours > 0) return `${hours}:${pad2(minutes)}:${pad2(seconds)}`;
  return `${minutes}:${pad2(seconds)}`;
}

export function durationMs(startedAt: string, endedAt?: string): number | null {
  const start = Date.parse(startedAt);
  if (Number.isNaN(start)) return null;
  if (!endedAt) return null;
  const end = Date.parse(endedAt);
  if (Number.isNaN(end)) return null;
  return Math.max(0, end - start);
}

export function formatPercent(value: number, locale: string): string {
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value)} %`;
}

export function formatInt(value: number, locale: string): string {
  return new Intl.NumberFormat(locale).format(value);
}

export function formatDateTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(locale, { dateStyle: 'short', timeStyle: 'medium' });
}

export function formatTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function shortId(id: string, keep = 8): string {
  return id.length <= keep ? id : id.slice(0, keep);
}

export function modelKey(provider: LlmProvider, model: string): string {
  return `${model}@${provider}`;
}

export function parseModelKey(value: string): { model: string; provider: LlmProvider } | null {
  const at = value.lastIndexOf('@');
  if (at <= 0) return null;
  const model = value.slice(0, at);
  const provider = value.slice(at + 1);
  if (
    provider !== 'ollama' &&
    provider !== 'xai' &&
    provider !== 'openai' &&
    provider !== 'anthropic' &&
    provider !== 'gemini' &&
    provider !== 'openai_compat'
  ) {
    return null;
  }
  if (!model) return null;
  return { model, provider };
}

export function outcomeBadgeVariant(
  outcome: RunOutcome,
): 'default' | 'secondary' | 'destructive' | 'outline' | 'warning' {
  if (outcome === 'succeeded' || outcome === 'running') return 'default';
  if (outcome === 'failed') return 'destructive';
  if (outcome === 'timeout') return 'warning';
  return 'secondary';
}

export function fileStamp(date = new Date()): string {
  return `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}-${pad2(date.getHours())}${pad2(date.getMinutes())}`;
}

export function safeFilePart(value: string): string {
  const trimmed = value.trim().replace(/[<>:"/\\|?*]+/g, '-').replace(/\s+/g, '_');
  return trimmed.slice(0, 48) || 'run';
}

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const a = sorted[mid];
  if (a === undefined) return null;
  if (sorted.length % 2 === 1) return a;
  const b = sorted[mid - 1];
  if (b === undefined) return a;
  return (a + b) / 2;
}

export function percentile(values: number[], p: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[index] ?? null;
}

export function startOfLocalDay(value: Date | string | number): Date {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
}

export function endOfLocalDay(value: Date | string | number): Date {
  const date = new Date(value);
  date.setHours(23, 59, 59, 999);
  return date;
}

export function toDateInput(isoOrDate: string | Date): string {
  const date = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}
