import type { TFunction } from 'i18next';
import type { DataLocation } from '@/modules/settings/model';
import type { ServiceStatus } from '@/store/session';

export type ValidationStatus = 'valid' | 'invalid' | 'unknown';

export type NetworkListItem = {
  id: string;
  name: string;
  description?: string;
  tags?: string[];
  updatedAt: string;
  lastUsedAt?: string;
  nodeCount: number;
  edgeCount: number;
  validationStatus: ValidationStatus;
  credentialMissing?: boolean;
  isActive: boolean;
  isRunning: boolean;
  lastRunId?: string;
  validationErrors?: NetworkValidationError[];
};

export type NetworkValidationError = {
  nodeId?: string;
  messageKey: string;
};

export type NetworkDetail = NetworkListItem & {
  validationErrors?: NetworkValidationError[];
};

export type RunOutcome = 'running' | 'succeeded' | 'failed' | 'cancelled' | 'timeout';

export type RunSummary = {
  runId: string;
  networkId: string;
  networkName: string;
  startedAt: string;
  endedAt?: string;
  outcome: RunOutcome;
  errorMessage?: string;
  models: Array<{ provider: 'ollama' | 'xai' | 'openai_compat'; model: string }>;
};

export type RunListFilter = {
  limit?: number;
  since?: string;
};

export type WeekStats = {
  runs: number;
  succeeded: number;
  failed: number;
};

export const RECENT_NETWORK_LIMIT = 4;
export const RECENT_RUN_LIMIT = 5;
export const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export function weekAgoIso(now = Date.now()): string {
  return new Date(now - WEEK_MS).toISOString();
}

export function countWeekStats(items: RunSummary[]): WeekStats {
  return {
    runs: items.length,
    succeeded: items.filter((item) => item.outcome === 'succeeded').length,
    failed: items.filter((item) => item.outcome === 'failed' || item.outcome === 'timeout').length,
  };
}

export function isHistoryStoreOk(location?: DataLocation): boolean {
  if (!location) return true;
  const history = location.stores.find((store) => store.id === 'history');
  if (!history) return true;
  return history.ok && history.state === 'ok';
}

export function failingStores(location?: DataLocation) {
  return location?.stores.filter((store) => !store.ok || store.state !== 'ok') ?? [];
}

export function durationMs(startedAt: string, endedAt?: string, now = Date.now()): number {
  const start = Date.parse(startedAt);
  if (Number.isNaN(start)) return 0;
  const end = endedAt ? Date.parse(endedAt) : now;
  return Math.max(0, (Number.isNaN(end) ? now : end) - start);
}

export function formatDuration(ms: number, t: TFunction): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return t('dashboard.duration.seconds', { count: totalSec });
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;
  if (hours > 0) return t('dashboard.duration.hours', { hours, minutes });
  return t('dashboard.duration.minutes', { minutes, seconds });
}

export function serviceBadgeVariant(
  status: ServiceStatus,
): 'default' | 'secondary' | 'destructive' | 'outline' | 'warning' {
  if (status === 'running') return 'default';
  if (status === 'error') return 'destructive';
  if (status === 'starting' || status === 'stopping') return 'warning';
  return 'secondary';
}

export function outcomeBadgeVariant(
  outcome: RunOutcome,
): 'default' | 'secondary' | 'destructive' | 'outline' | 'warning' {
  if (outcome === 'succeeded' || outcome === 'running') return 'default';
  if (outcome === 'failed') return 'destructive';
  if (outcome === 'timeout') return 'warning';
  return 'secondary';
}

export function validationBadgeVariant(
  status: ValidationStatus,
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'valid') return 'default';
  if (status === 'invalid') return 'destructive';
  return 'secondary';
}

export function recentNetworks(items: NetworkListItem[], limit = RECENT_NETWORK_LIMIT): NetworkListItem[] {
  return [...items]
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, Math.min(4, Math.max(limit, 2)));
}
