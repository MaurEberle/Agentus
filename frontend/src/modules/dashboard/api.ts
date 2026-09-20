import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/api/client';
import { useHelpChatStatusQuery } from '@/components/help-chat/api';
import {
  isHistoryStoreOk,
  weekAgoIso,
  type RunListFilter,
  type RunSummary,
} from '@/modules/dashboard/model';
import { listNetworkSummaries } from '@/modules/network/api';
import { pingRuntime, useRuntimeModelsQuery, useStoresQuery } from '@/modules/settings/api';
import { normalizeRun } from '@/modules/history/model/normalize';
import type { ResourceSnapshot } from '@/modules/monitoring/model/types';

export { listNetworkSummaries };

export async function listRuns(filter: RunListFilter = {}): Promise<{ items: RunSummary[]; total: number }> {
  const params = new URLSearchParams();
  if (filter.limit != null) params.set('limit', String(filter.limit));
  if (filter.since) params.set('since', filter.since);
  const query = params.toString();
  const body = await apiFetch<{ items: RunSummary[]; total: number }>(`/runs${query ? `?${query}` : ''}`);
  return { items: (body.items ?? []).map(normalizeRun), total: body.total ?? 0 };
}

export function useNetworksQuery() {
  return useQuery({
    queryKey: ['networks'],
    queryFn: listNetworkSummaries,
  });
}

export function useRecentRunsQuery(enabled: boolean) {
  return useQuery({
    queryKey: ['runs', 'recent'],
    queryFn: () => listRuns({ limit: 5 }),
    enabled,
  });
}

export function useWeekRunsQuery(enabled: boolean) {
  return useQuery({
    queryKey: ['runs', 'week'],
    queryFn: () => listRuns({ since: weekAgoIso() }),
    enabled,
  });
}

export function useRuntimePingQuery() {
  return useQuery({
    queryKey: ['runtime', 'ping'],
    queryFn: pingRuntime,
    retry: false,
  });
}

export function useHostResourcesQuery() {
  return useQuery({
    queryKey: ['runtime', 'resources'],
    queryFn: () => apiFetch<ResourceSnapshot>('/runtime/resources'),
    refetchInterval: 1500,
    staleTime: 0,
  });
}

export function useDashboardQueries() {
  const networks = useNetworksQuery();
  const ping = useRuntimePingQuery();
  const models = useRuntimeModelsQuery();
  const stores = useStoresQuery();
  const help = useHelpChatStatusQuery();
  const resources = useHostResourcesQuery();
  const historyOk = isHistoryStoreOk(stores.data);
  const runsEnabled = stores.isSuccess && historyOk;
  const recentRuns = useRecentRunsQuery(runsEnabled);
  const weekRuns = useWeekRunsQuery(runsEnabled);

  return {
    networks,
    ping,
    models,
    stores,
    help,
    resources,
    historyOk,
    recentRuns,
    weekRuns,
  };
}
