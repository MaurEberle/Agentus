import { apiFetch, USE_MOCKS } from '@/api/client';
import {
  mockDeleteRuns,
  mockDeleteRunsOlderThan,
  mockGetRun,
  mockListCalls,
  mockListRunLogs,
  mockListRuns,
} from '@/modules/history/mocks';
import type { LlmCall, LogEvent, LogFilter, RunDetail, RunListFilter, RunSummary } from '@/modules/history/model/types';

function queryString(filter: RunListFilter): string {
  const params = new URLSearchParams();
  if (filter.from) params.set('from', filter.from);
  if (filter.to) params.set('to', filter.to);
  if (filter.since) params.set('since', filter.since);
  if (filter.networkId) params.set('networkId', filter.networkId);
  if (filter.outcome?.length) params.set('outcome', filter.outcome.join(','));
  if (filter.model) params.set('model', filter.model);
  if (filter.q) params.set('q', filter.q);
  if (filter.limit != null) params.set('limit', String(filter.limit));
  if (filter.offset != null) params.set('offset', String(filter.offset));
  const text = params.toString();
  return text ? `?${text}` : '';
}

export async function listRuns(filter: RunListFilter = {}): Promise<{ items: RunSummary[]; total: number }> {
  if (USE_MOCKS) return mockListRuns(filter);
  return apiFetch(`/runs${queryString(filter)}`);
}

export async function getRun(runId: string): Promise<RunDetail | null> {
  if (USE_MOCKS) return mockGetRun(runId);
  try {
    return await apiFetch<RunDetail>(`/runs/${encodeURIComponent(runId)}`);
  } catch {
    return null;
  }
}

export async function listRunLogs(runId: string, logFilter?: LogFilter): Promise<LogEvent[]> {
  if (USE_MOCKS) return mockListRunLogs(runId, logFilter);
  const params = new URLSearchParams();
  if (logFilter?.level) params.set('level', logFilter.level);
  if (logFilter?.q) params.set('q', logFilter.q);
  if (logFilter?.nodeId) params.set('nodeId', logFilter.nodeId);
  const suffix = params.toString() ? `?${params}` : '';
  const body = await apiFetch<{ items: LogEvent[] }>(`/runs/${encodeURIComponent(runId)}/logs${suffix}`);
  return body.items;
}

export async function listCalls(filter: RunListFilter = {}): Promise<LlmCall[]> {
  if (USE_MOCKS) return mockListCalls(filter);
  const body = await apiFetch<{ items: LlmCall[] }>(`/runs/calls${queryString(filter)}`);
  return body.items;
}

export async function deleteRuns(ids: string[]): Promise<void> {
  if (USE_MOCKS) return mockDeleteRuns(ids);
  await apiFetch('/runs', { method: 'DELETE', body: JSON.stringify({ ids }) });
}

export async function deleteRunsOlderThan(days: number): Promise<{ deleted: number }> {
  if (USE_MOCKS) return mockDeleteRunsOlderThan(days);
  return apiFetch('/runs/purge', { method: 'POST', body: JSON.stringify({ olderThanDays: days }) });
}

export function toApiFilter(
  filter: {
    from: string;
    to: string;
    networkId: string;
    outcomes: RunSummary['outcome'][];
    model: string;
    q: string;
  },
  extra?: { limit?: number; offset?: number },
): RunListFilter {
  return {
    from: filter.from,
    to: filter.to,
    networkId: filter.networkId || undefined,
    outcome: filter.outcomes.length ? filter.outcomes : undefined,
    model: filter.model || undefined,
    q: filter.q.trim() || undefined,
    limit: extra?.limit,
    offset: extra?.offset,
  };
}
