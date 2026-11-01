import type { ServiceStatus } from '@/store/session';
import type { LogLevel } from '@/modules/monitoring/model/types';

export {
  fileStamp,
  formatBytes,
  formatDateTime,
  formatDuration,
  formatPercent,
  formatTime,
  pad2,
  safeFilePart,
  shortId,
} from '@/lib/format';

export const LOG_PREVIEW_CHARS = 300;

export function clipPreview(text: string, limit = LOG_PREVIEW_CHARS): string {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trimEnd()}...`;
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


