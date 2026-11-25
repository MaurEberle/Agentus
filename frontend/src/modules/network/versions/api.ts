import { useQuery } from '@tanstack/react-query';
import { apiFetch, queryClient } from '@/api/client';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import type { NetworkDiff } from '@/modules/network/model/diff';

/** Where a version came from (fix/netz-versionen/entwurf.md, 4). */
export type VersionSource = 'create' | 'editor' | 'architect' | 'restore' | 'import' | 'duplicate' | 'migration';

export type NetworkVersionItem = {
  version: number;
  createdAt: string;
  updatedAt: string;
  source: VersionSource | string;
  note?: string | null;
  pinned: boolean;
  restoredFrom?: number | null;
  nodeCount: number;
  contentHash: string;
};

export type NetworkVersionList = { version: number; revision: number; items: NetworkVersionItem[] };
export type NetworkVersion = NetworkVersionItem & { document: AgentNetworkDocument };

export const versionKeys = {
  list: (id: string) => ['networks', id, 'versions'] as const,
  one: (id: string, version: number) => ['networks', id, 'versions', version] as const,
  diff: (id: string, version: number, revision: number) => ['networks', id, 'versions', version, 'diff', revision] as const,
};

export function useNetworkVersionsQuery(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: versionKeys.list(id ?? ''),
    queryFn: () => apiFetch<NetworkVersionList>(`/networks/${id}/versions`),
    enabled: Boolean(id) && enabled,
  });
}

export function useNetworkVersionQuery(id: string | undefined, version: number | null) {
  return useQuery({
    queryKey: versionKeys.one(id ?? '', version ?? 0),
    queryFn: () => apiFetch<NetworkVersion>(`/networks/${id}/versions/${version}`),
    enabled: Boolean(id) && version !== null,
  });
}

/** What restoring ``version`` would change on the current state; keyed by revision so it follows saves. */
export function useVersionDiffQuery(id: string | undefined, version: number | null, revision: number) {
  return useQuery({
    queryKey: versionKeys.diff(id ?? '', version ?? 0, revision),
    queryFn: () => apiFetch<{ version: number; current: number; diff: NetworkDiff }>(`/networks/${id}/versions/${version}/diff`),
    enabled: Boolean(id) && version !== null,
  });
}

export async function patchNetworkVersion(id: string, version: number, patch: { pinned?: boolean; note?: string }) {
  const updated = await apiFetch<NetworkVersion>(`/networks/${id}/versions/${version}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
  await queryClient.invalidateQueries({ queryKey: versionKeys.list(id) });
  return updated;
}

async function afterWrite(id: string, document: AgentNetworkDocument) {
  queryClient.setQueryData(['networks', id, 'document'], document);
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: versionKeys.list(id) }),
    queryClient.invalidateQueries({ queryKey: ['networks'], exact: true }),
  ]);
}

/** A stored version becomes the newest one (entwurf.md, 9). */
export async function restoreNetworkVersion(id: string, version: number, baseRevision?: number) {
  const restored = await apiFetch<AgentNetworkDocument>(`/networks/${id}/versions/${version}/restore`, {
    method: 'POST',
    body: JSON.stringify({ baseRevision }),
  });
  await afterWrite(id, restored);
  return restored;
}

/** The network as a run saw it becomes the newest version (entwurf.md, 12). */
export async function restoreFromRun(id: string, runId: string, baseRevision?: number) {
  const restored = await apiFetch<AgentNetworkDocument>(`/networks/${id}/restore-run`, {
    method: 'POST',
    body: JSON.stringify({ runId, baseRevision }),
  });
  await afterWrite(id, restored);
  return restored;
}

export async function copyNetworkVersion(id: string, version: number, name: string) {
  const copy = await apiFetch<AgentNetworkDocument>(`/networks/${id}/versions/${version}/copy`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
  await queryClient.invalidateQueries({ queryKey: ['networks'], exact: true });
  return copy;
}

/** Knowledge nodes without an index after a restore (V-3): they get the rebuild offer. */
export function knowledgeWithoutIndex(document: AgentNetworkDocument): { id: string; name: string }[] {
  const states = (document as AgentNetworkDocument & { knowledge?: { nodeId: string; state: string }[] }).knowledge ?? [];
  return document.nodes
    .filter((node) => node.type === 'knowledge')
    .filter((node) => !states.some((item) => item.nodeId === node.id && item.state !== 'missing'))
    .map((node) => ({ id: node.id, name: String((node.data as Record<string, unknown>).displayName || node.id) }));
}
