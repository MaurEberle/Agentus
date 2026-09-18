import { useQuery } from '@tanstack/react-query';
import { apiFetch, USE_MOCKS } from '@/api/client';
import { useHelpChatStatusQuery } from '@/components/help-chat/api';
import {
  mockGetNetwork,
  mockListDashboardNetworks,
  mockListRuns,
} from '@/modules/dashboard/mocks';
import {
  isHistoryStoreOk,
  weekAgoIso,
  type NetworkDetail,
  type NetworkListItem,
  type RunListFilter,
  type RunSummary,
} from '@/modules/dashboard/model';
import { pingRuntime, useRuntimeModelsQuery, useStoresQuery } from '@/modules/settings/api';

export async function listNetworkSummaries(): Promise<{ items: NetworkListItem[] }> {
  if (USE_MOCKS) return mockListDashboardNetworks();
  return apiFetch<{ items: NetworkListItem[] }>('/networks');
}

export async function getNetwork(id: string): Promise<NetworkDetail> {
  if (USE_MOCKS) return mockGetNetwork(id);
  return apiFetch<NetworkDetail>(`/networks/${id}`);
}

export async function listRuns(filter: RunListFilter = {}): Promise<{ items: RunSummary[]; total: number }> {
  if (USE_MOCKS) return mockListRuns(filter);
  const params = new URLSearchParams();
  if (filter.limit != null) params.set('limit', String(filter.limit));
  if (filter.since) params.set('since', filter.since);
  const query = params.toString();
  return apiFetch<{ items: RunSummary[]; total: number }>(`/runs${query ? `?${query}` : ''}`);
}

export function useNetworksQuery() {
  return useQuery({
    queryKey: ['networks'],
    queryFn: listNetworkSummaries,
  });
}

export function useNetworkQuery(id: string | null) {
  return useQuery({
    queryKey: ['networks', id],
    queryFn: () => getNetwork(id as string),
    enabled: Boolean(id),
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

export function useDashboardQueries() {
  const networks = useNetworksQuery();
  const ping = useRuntimePingQuery();
  const models = useRuntimeModelsQuery();
  const stores = useStoresQuery();
  const help = useHelpChatStatusQuery();
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
    historyOk,
    recentRuns,
    weekRuns,
  };
}
