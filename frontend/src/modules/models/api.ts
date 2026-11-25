import { useQuery } from '@tanstack/react-query';
import { API_BASE, ApiError, apiFetch, queryClient } from '@/api/client';
import type { DownloadList, HubCard, HubFiles, HubHit, InstalledModel, PullEvent } from '@/modules/models/model';

export async function listInstalled(): Promise<{ items: InstalledModel[]; messageKey?: string }> {
  return apiFetch('/models');
}

export async function saveModelTags(edits: { name: string; tags: string[] }[]): Promise<void> {
  for (const edit of edits) {
    await apiFetch('/models/tags', { method: 'PUT', body: JSON.stringify(edit) });
  }
  await queryClient.invalidateQueries({ queryKey: ['models'], exact: true });
}

export async function searchHub(params: {
  search: string;
  pipeline: string;
  size: string;
  sort: string;
  limit: number;
  cursor?: string;
  /** Capabilities a model must have, and must not have (comma-separated). */
  caps?: string;
  without?: string;
  /** Minimum context window in tokens. */
  context?: number;
  hideInstalled?: boolean;
}, signal?: AbortSignal): Promise<{
  items: HubHit[];
  messageKey?: string;
  /** Seconds until Hugging Face takes requests again (with models.hub.rateLimited). */
  retryAfter?: number;
  hasNext: boolean;
  nextCursor?: string;
  pageSize: number;
}> {
  const query = new URLSearchParams({
    search: params.search,
    pipeline: params.pipeline,
    size: params.size,
    sort: params.sort,
    limit: String(params.limit),
  });
  if (params.cursor) query.set('cursor', params.cursor);
  if (params.caps) query.set('caps', params.caps);
  if (params.without) query.set('without', params.without);
  if (params.context) query.set('context', String(params.context));
  if (params.hideInstalled) query.set('hideInstalled', 'true');
  return apiFetch(`/models/hub?${query.toString()}`, { signal });
}

export async function hubFiles(id: string): Promise<HubFiles> {
  const query = new URLSearchParams({ id });
  return apiFetch(`/models/hub/files?${query.toString()}`);
}

export async function hubCard(id: string): Promise<HubCard> {
  const query = new URLSearchParams({ id });
  return apiFetch(`/models/hub/card?${query.toString()}`);
}

/** Worth asking again: the Hub was busy or slow, not "there is no card". */
export const PASSING_CARD_KEYS = new Set(['models.hub.rateLimited', 'models.hub.timeout', 'models.hub.unreachable', 'models.hub.failed']);

/** A repo's model card; shared by the hub and the installed tab, so each repo is asked once. */
export function useHubCardQuery(repo: string | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['models', 'hub', 'card', (repo ?? '').toLowerCase()],
    queryFn: () => hubCard(repo as string),
    enabled: enabled && Boolean(repo),
    retry: false,
    // A busy Hub is asked again on the next opening; a card or "no card" holds for an hour.
    staleTime: (state) => (PASSING_CARD_KEYS.has(state.state.data?.messageKey ?? '') ? 0 : 60 * 60 * 1000),
  });
}

function rememberDownloads(data: DownloadList): DownloadList {
  queryClient.setQueryData(['models', 'downloads'], data);
  return data;
}

export async function listDownloads(): Promise<DownloadList> {
  return apiFetch('/models/downloads');
}

export async function enqueueDownload(body: {
  model: string;
  label: string;
  publisher?: string | null;
  sizeBytes?: number;
}): Promise<DownloadList> {
  const data = await apiFetch<DownloadList>('/models/downloads', { method: 'POST', body: JSON.stringify(body) });
  return rememberDownloads(data);
}

export async function pauseDownloads(): Promise<DownloadList> {
  return rememberDownloads(await apiFetch('/models/downloads/pause', { method: 'POST' }));
}

export async function resumeDownloads(): Promise<DownloadList> {
  return rememberDownloads(await apiFetch('/models/downloads/resume', { method: 'POST' }));
}

export async function pauseDownload(id: string): Promise<DownloadList> {
  return rememberDownloads(await apiFetch(`/models/downloads/${id}/pause`, { method: 'POST' }));
}

export async function resumeDownload(id: string): Promise<DownloadList> {
  return rememberDownloads(await apiFetch(`/models/downloads/${id}/resume`, { method: 'POST' }));
}

export async function stopDownload(id: string): Promise<DownloadList> {
  return rememberDownloads(await apiFetch(`/models/downloads/${id}/stop`, { method: 'POST' }));
}

export async function removeDownloads(ids: string[]): Promise<DownloadList> {
  return rememberDownloads(await apiFetch('/models/downloads/remove', { method: 'POST', body: JSON.stringify({ ids }) }));
}

export async function pullModel(
  model: string,
  onEvent: (event: PullEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/models/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, 'models.pull.failed');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = '';
  for (;;) {
    const step = await reader.read();
    if (step.done) break;
    pending += decoder.decode(step.value, { stream: true });
    const lines = pending.split('\n');
    pending = lines.pop() ?? '';
    for (const line of lines) {
      const text = line.trim();
      if (!text) continue;
      onEvent(JSON.parse(text) as PullEvent);
    }
  }
  const tail = pending.trim();
  if (tail) onEvent(JSON.parse(tail) as PullEvent);
}
