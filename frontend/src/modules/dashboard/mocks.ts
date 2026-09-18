import { ApiError } from '@/api/client';
import { type RunListFilter, type RunSummary } from '@/modules/dashboard/model';
import { mockListRuns as mockListHistoryRuns } from '@/modules/history/mocks';
import { mockListEditorNetworks } from '@/modules/network/mocks';
import { mockGetDataLocation } from '@/modules/settings/mocks';

/** Fresh workspace: no networks and no runs. Populated scenario is the default. */
export const DASHBOARD_EMPTY_MOCK = false;

function delay(ms = 40) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function mockListDashboardNetworks() {
  if (DASHBOARD_EMPTY_MOCK) return { items: [] };
  return mockListEditorNetworks();
}

export async function mockListRuns(filter: RunListFilter): Promise<{ items: RunSummary[]; total: number }> {
  if (DASHBOARD_EMPTY_MOCK) {
    await delay();
    const location = await mockGetDataLocation();
    const history = location.stores.find((store) => store.id === 'history');
    if (history && (!history.ok || history.state !== 'ok')) {
      throw new ApiError(503, 'dashboard.runs.storeError');
    }
    return { items: [], total: 0 };
  }
  return mockListHistoryRuns({ since: filter.since, limit: filter.limit });
}
