import { useQuery } from '@tanstack/react-query';
import { apiFetch, queryClient, USE_MOCKS } from '@/api/client';
import type { NetworkListItem } from '@/modules/dashboard/model';
import {
  mockCreateNetwork,
  mockDuplicateNetwork,
  mockGetEditorNetwork,
  mockListEditorNetworks,
  mockListToolCatalog,
  mockReindexKnowledge,
  mockTestLlm,
  mockUpdateNetwork,
  mockValidateNetwork,
} from '@/modules/network/mocks';
import type { AgentNetworkDocument, ToolCatalogGroup } from '@/modules/network/model/document';
import { listCredentials, listRuntimeModels, useMcpServersQuery } from '@/modules/settings/api';

export async function listNetworkSummaries(): Promise<{ items: NetworkListItem[] }> {
  if (USE_MOCKS) return mockListEditorNetworks();
  return apiFetch<{ items: NetworkListItem[] }>('/networks');
}

export async function getNetwork(id: string): Promise<AgentNetworkDocument> {
  if (USE_MOCKS) return mockGetEditorNetwork(id);
  return apiFetch<AgentNetworkDocument>(`/networks/${id}`);
}

export async function createNetwork(doc: AgentNetworkDocument): Promise<AgentNetworkDocument> {
  const created = USE_MOCKS
    ? await mockCreateNetwork(doc)
    : await apiFetch<AgentNetworkDocument>('/networks', {
        method: 'POST',
        body: JSON.stringify(doc),
      });
  await queryClient.invalidateQueries({ queryKey: ['networks'] });
  return created;
}

export async function updateNetwork(id: string, doc: AgentNetworkDocument): Promise<AgentNetworkDocument> {
  const updated = USE_MOCKS
    ? await mockUpdateNetwork(id, doc)
    : await apiFetch<AgentNetworkDocument>(`/networks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(doc),
      });
  queryClient.setQueryData(['networks', id], updated);
  await queryClient.invalidateQueries({ queryKey: ['networks'] });
  return updated;
}

export async function duplicateNetwork(id: string): Promise<AgentNetworkDocument> {
  const copy = USE_MOCKS
    ? await mockDuplicateNetwork(id)
    : await apiFetch<AgentNetworkDocument>(`/networks/${id}/duplicate`, { method: 'POST' });
  await queryClient.invalidateQueries({ queryKey: ['networks'] });
  return copy;
}

export async function validateNetwork(doc: AgentNetworkDocument) {
  if (USE_MOCKS) return mockValidateNetwork(doc);
  return apiFetch<{ valid: boolean; errors: { nodeId?: string; messageKey: string }[] }>(
    doc.id ? `/networks/${doc.id}/validate` : '/networks/validate',
    { method: 'POST', body: JSON.stringify(doc) },
  );
}

export async function listToolCatalog(): Promise<{ groups: ToolCatalogGroup[] }> {
  if (USE_MOCKS) return mockListToolCatalog();
  return apiFetch('/tools/catalog');
}

export async function testLlmConnection(input: {
  provider: string;
  model: string;
  baseUrl?: string;
  credentialId?: string;
}) {
  if (USE_MOCKS) return mockTestLlm(input);
  return apiFetch<{ ok: boolean; messageKey?: string }>('/runtime/test-llm', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function reindexNetworkKnowledge(networkId: string, nodeId: string) {
  if (USE_MOCKS) return mockReindexKnowledge(networkId, nodeId);
  return apiFetch<{ state: 'ready' | 'error' | 'indexing'; messageKey?: string }>(
    `/networks/${networkId}/knowledge/${nodeId}/reindex`,
    { method: 'POST' },
  );
}

export function useEditorNetworksQuery() {
  return useQuery({
    queryKey: ['networks'],
    queryFn: listNetworkSummaries,
  });
}

export function useEditorNetworkQuery(id: string | undefined) {
  return useQuery({
    queryKey: ['networks', id, 'document'],
    queryFn: () => getNetwork(id as string),
    enabled: Boolean(id),
    retry: false,
  });
}

export function useToolCatalogQuery() {
  return useQuery({
    queryKey: ['tools', 'catalog'],
    queryFn: listToolCatalog,
  });
}

export function useEditorCredentialsQuery() {
  return useQuery({
    queryKey: ['credentials'],
    queryFn: listCredentials,
  });
}

export function useEditorModelsQuery() {
  return useQuery({
    queryKey: ['runtime', 'models'],
    queryFn: listRuntimeModels,
  });
}

export { useMcpServersQuery };
