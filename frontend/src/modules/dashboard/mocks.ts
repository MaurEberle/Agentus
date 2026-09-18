import { ApiError } from '@/api/client';
import { peekMockSession } from '@/api/mocks';
import {
  type NetworkDetail,
  type NetworkListItem,
  type RunListFilter,
  type RunSummary,
} from '@/modules/dashboard/model';
import { mockGetDataLocation } from '@/modules/settings/mocks';
import { useAppStore } from '@/store';

/** Fresh workspace: no networks and no runs. Populated scenario is the default. */
export const DASHBOARD_EMPTY_MOCK = false;

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

function at(hoursAgoValue: number, durationMs: number): { startedAt: string; endedAt: string } {
  const ended = Date.now() - hoursAgoValue * 60 * 60 * 1000;
  return {
    startedAt: new Date(ended - durationMs).toISOString(),
    endedAt: new Date(ended).toISOString(),
  };
}

const populatedNetworks: NetworkListItem[] = [
  {
    id: 'net-demo',
    name: 'Demo-Netz',
    description: 'Beispielnetz für den lokalen Lauf.',
    tags: ['demo'],
    updatedAt: hoursAgo(2),
    lastUsedAt: hoursAgo(2),
    nodeCount: 5,
    edgeCount: 4,
    validationStatus: 'valid',
    isActive: true,
    isRunning: false,
    lastRunId: 'run-succeeded',
  },
  {
    id: 'net-support',
    name: 'Support-Netz',
    description: 'Zweitnetz mit fehlendem Modell am LLM-Knoten.',
    updatedAt: hoursAgo(30),
    lastUsedAt: hoursAgo(26),
    nodeCount: 3,
    edgeCount: 2,
    validationStatus: 'invalid',
    isActive: false,
    isRunning: false,
    lastRunId: 'run-failed',
  },
];

const populatedRuns: RunSummary[] = [
  {
    runId: 'run-succeeded',
    networkId: 'net-demo',
    networkName: 'Demo-Netz',
    ...at(2, 45_000),
    outcome: 'succeeded',
    models: [{ provider: 'ollama', model: 'llama3.2:1b' }],
  },
  {
    runId: 'run-failed',
    networkId: 'net-support',
    networkName: 'Support-Netz',
    ...at(26, 12_000),
    outcome: 'failed',
    errorMessage: 'dashboard.validation.missingModel',
    models: [{ provider: 'xai', model: 'grok-3' }],
  },
  {
    runId: 'run-cancelled',
    networkId: 'net-demo',
    networkName: 'Demo-Netz',
    ...at(72, 8_000),
    outcome: 'cancelled',
    models: [{ provider: 'ollama', model: 'llama3.2:1b' }],
  },
  {
    runId: 'run-old',
    networkId: 'net-demo',
    networkName: 'Demo-Netz',
    ...at(240, 30_000),
    outcome: 'succeeded',
    models: [{ provider: 'ollama', model: 'llama3.2:1b' }],
  },
];

const validationById: Record<string, NetworkDetail['validationErrors']> = {
  'net-support': [{ nodeId: 'llm-1', messageKey: 'dashboard.validation.missingModel' }],
};

function delay(ms = 40) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function withSessionFlags(items: NetworkListItem[]): NetworkListItem[] {
  const { activeNetworkId, serviceStatus } = useAppStore.getState();
  const running = serviceStatus === 'starting' || serviceStatus === 'running';
  return items.map((item) => ({
    ...item,
    isActive: item.id === activeNetworkId,
    isRunning: running && item.id === activeNetworkId,
  }));
}

export async function mockListDashboardNetworks(): Promise<{ items: NetworkListItem[] }> {
  await delay();
  if (DASHBOARD_EMPTY_MOCK) return { items: [] };
  return { items: withSessionFlags(populatedNetworks) };
}

export async function mockGetNetwork(id: string): Promise<NetworkDetail> {
  await delay();
  const items = withSessionFlags(DASHBOARD_EMPTY_MOCK ? [] : populatedNetworks);
  const item = items.find((entry) => entry.id === id);
  if (!item) {
    throw new ApiError(404, 'dashboard.error.networkMissing');
  }
  return {
    ...item,
    validationErrors: validationById[id] ? [...(validationById[id] ?? [])] : undefined,
  };
}

export async function mockListRuns(filter: RunListFilter): Promise<{ items: RunSummary[]; total: number }> {
  await delay();
  const location = await mockGetDataLocation();
  const history = location.stores.find((store) => store.id === 'history');
  if (history && (!history.ok || history.state !== 'ok')) {
    throw new ApiError(503, 'dashboard.runs.storeError');
  }

  if (DASHBOARD_EMPTY_MOCK) return { items: [], total: 0 };

  const items = [...populatedRuns];
  const session = peekMockSession();
  const store = useAppStore.getState();
  const liveStatus = store.serviceStatus;
  if (liveStatus === 'running' || liveStatus === 'starting') {
    items.unshift({
      runId: store.runId ?? session.runId ?? 'run-live',
      networkId: store.activeNetworkId ?? session.activeNetworkId ?? 'net-demo',
      networkName: store.activeNetworkName ?? session.activeNetworkName ?? 'Demo-Netz',
      startedAt: session.startedAt ?? new Date().toISOString(),
      outcome: 'running',
      models: [{ provider: 'ollama', model: 'llama3.2:1b' }],
    });
  }

  items.sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
  const sinceMs = filter.since ? Date.parse(filter.since) : Number.NaN;
  const filtered = Number.isNaN(sinceMs)
    ? items
    : items.filter((item) => Date.parse(item.startedAt) >= sinceMs);
  const limited = filter.limit != null ? filtered.slice(0, filter.limit) : filtered;
  return { items: limited, total: filtered.length };
}
