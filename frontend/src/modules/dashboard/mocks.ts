import { ApiError } from '@/api/client';
import { peekMockSession } from '@/api/mocks';
import { type RunListFilter, type RunSummary } from '@/modules/dashboard/model';
import { mockListEditorNetworks } from '@/modules/network/mocks';
import { mockGetDataLocation } from '@/modules/settings/mocks';
import { useAppStore } from '@/store';

/** Fresh workspace: no networks and no runs. Populated scenario is the default. */
export const DASHBOARD_EMPTY_MOCK = false;

function at(hoursAgoValue: number, durationMs: number): { startedAt: string; endedAt: string } {
  const ended = Date.now() - hoursAgoValue * 60 * 60 * 1000;
  return {
    startedAt: new Date(ended - durationMs).toISOString(),
    endedAt: new Date(ended).toISOString(),
  };
}

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

function delay(ms = 40) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function mockListDashboardNetworks() {
  if (DASHBOARD_EMPTY_MOCK) return { items: [] };
  return mockListEditorNetworks();
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
