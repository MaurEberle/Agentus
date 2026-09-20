import { apiFetch } from '@/api/client';
import { normalizeRun, normalizeRunDetail } from '@/modules/history/model/normalize';
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
  const body = await apiFetch<{ items: RunSummary[]; total: number }>(`/runs${queryString(filter)}`);
  return { items: (body.items ?? []).map(normalizeRun), total: body.total ?? 0 };
}

export async function getRun(runId: string): Promise<RunDetail | null> {
  try {
    const raw = await apiFetch<RunDetail>(`/runs/${encodeURIComponent(runId)}`);
    return normalizeRunDetail(raw);
  } catch {
    return null;
  }
}

export async function listRunLogs(runId: string, logFilter?: LogFilter): Promise<LogEvent[]> {
  const params = new URLSearchParams();
  if (logFilter?.level) params.set('level', logFilter.level);
  if (logFilter?.q) params.set('q', logFilter.q);
  if (logFilter?.nodeId) params.set('nodeId', logFilter.nodeId);
  const suffix = params.toString() ? `?${params}` : '';
  const body = await apiFetch<{ items: LogEvent[] }>(`/runs/${encodeURIComponent(runId)}/logs${suffix}`);
  return body.items;
}

export async function listCalls(filter: RunListFilter = {}): Promise<LlmCall[]> {
  const body = await apiFetch<{ items: LlmCall[] }>(`/runs/calls${queryString(filter)}`);
  return body.items;
}

export async function deleteRuns(ids: string[]): Promise<void> {
  await apiFetch('/runs', { method: 'DELETE', body: JSON.stringify({ ids }) });
}

export async function deleteRunsOlderThan(days: number): Promise<{ deleted: number }> {
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
