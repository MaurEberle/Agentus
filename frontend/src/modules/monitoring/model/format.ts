import type { ServiceStatus } from '@/store/session';
import type { LogLevel } from '@/modules/monitoring/model/types';

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

export function formatBytes(bytes: number, locale: string): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = Math.max(0, bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 ? 0 : value >= 10 ? 1 : 2;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value)} ${units[unit]}`;
}

export function formatPercent(value: number, locale: string): string {
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value)} %`;
}

export function formatTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function formatDateTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(locale, {
    dateStyle: 'short',
    timeStyle: 'medium',
  });
}

export function shortId(id: string, keep = 8): string {
  return id.length <= keep ? id : id.slice(0, keep);
}

export function serviceBadgeVariant(
  status: ServiceStatus,
): 'default' | 'secondary' | 'destructive' | 'outline' | 'warning' {
  if (status === 'running') return 'default';
  if (status === 'error') return 'destructive';
  if (status === 'starting' || status === 'stopping') return 'warning';
  return 'secondary';
}

export function logLevelRank(level: LogLevel): number {
  if (level === 'debug') return 0;
  if (level === 'info') return 1;
  if (level === 'warn') return 2;
  return 3;
}

export function meterTone(percent: number, alarm: boolean): 'off' | 'normal' | 'warn' | 'hot' {
  if (!alarm) return percent <= 0 ? 'off' : 'normal';
  if (percent >= 95) return 'hot';
  if (percent >= 85) return 'warn';
  return 'normal';
}

export function fileStamp(date = new Date()): string {
  return `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}-${pad2(date.getHours())}${pad2(date.getMinutes())}`;
}

export function safeFilePart(value: string): string {
  const trimmed = value.trim().replace(/[<>:"/\\|?*]+/g, '-').replace(/\s+/g, '_');
  return trimmed.slice(0, 48) || 'run';
}
