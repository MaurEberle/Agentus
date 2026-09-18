import { apiFetch, queryClient, USE_MOCKS } from '@/api/client';
import { mockSetActiveNetwork } from '@/api/mocks';
import { selectActiveNetwork } from '@/api/session';
import type { NetworkListItem } from '@/modules/dashboard/model';
import {
  createNetwork,
  duplicateNetwork,
  getNetwork,
  listNetworkSummaries,
} from '@/modules/network/api';
import {
  mockAddTags,
  mockDeleteNetworks,
  mockExportNetwork,
  mockImportNetwork,
  mockRenameNetwork,
} from '@/modules/network/mocks';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import { useAppStore } from '@/store';

export { createNetwork, duplicateNetwork, getNetwork, listNetworkSummaries };

async function refreshLists() {
  await queryClient.invalidateQueries({ queryKey: ['networks'] });
  await queryClient.invalidateQueries({ queryKey: ['session'] });
}

export async function deleteNetworks(ids: string[]): Promise<void> {
  if (USE_MOCKS) await mockDeleteNetworks(ids);
  else if (ids.length === 1) await apiFetch<void>(`/networks/${ids[0]}`, { method: 'DELETE' });
  else await apiFetch<void>('/networks', { method: 'DELETE', body: JSON.stringify({ ids }) });
  const store = useAppStore.getState();
  if (store.activeNetworkId && ids.includes(store.activeNetworkId)) {
    if (USE_MOCKS) {
      const session = await mockSetActiveNetwork(null);
      store.hydrateSession(session);
    } else {
      store.setActiveNetwork(null);
    }
  }
  await refreshLists();
}

export async function renameNetwork(
  id: string,
  patch: { name: string; description?: string },
): Promise<NetworkListItem> {
  const item = USE_MOCKS
    ? await mockRenameNetwork(id, patch)
    : await apiFetch<NetworkListItem>(`/networks/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      });
  await refreshLists();
  return item;
}

export async function addTags(ids: string[], tags: string[]): Promise<{ items: NetworkListItem[] }> {
  const result = USE_MOCKS
    ? await mockAddTags(ids, tags)
    : await apiFetch<{ items: NetworkListItem[] }>('/networks/tags', {
        method: 'POST',
        body: JSON.stringify({ ids, tags }),
      });
  await refreshLists();
  return result;
}

export async function exportNetwork(id: string): Promise<AgentNetworkDocument & { exportedAt: string }> {
  if (USE_MOCKS) return mockExportNetwork(id);
  return apiFetch<AgentNetworkDocument & { exportedAt: string }>(`/networks/${id}/export`);
}

export async function importNetwork(document: AgentNetworkDocument): Promise<AgentNetworkDocument> {
  const created = USE_MOCKS
    ? await mockImportNetwork(document)
    : await apiFetch<AgentNetworkDocument>('/networks/import', {
        method: 'POST',
        body: JSON.stringify({ document }),
      });
  await refreshLists();
  return created;
}

export async function setLibraryActive(id: string): Promise<void> {
  await selectActiveNetwork(id);
}
