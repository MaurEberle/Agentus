import { API_BASE, ApiError, apiFetch, queryClient } from '@/api/client';
import type { DownloadList, HubFiles, HubHit, InstalledModel, PullEvent } from '@/modules/models/model';

export async function listInstalled(): Promise<{ items: InstalledModel[]; messageKey?: string }> {
  return apiFetch('/models');
}

export async function saveModelTags(edits: { name: string; tags: string[] }[]): Promise<void> {
  for (const edit of edits) {
    await apiFetch('/models/tags', { method: 'PUT', body: JSON.stringify(edit) });
  }
  await queryClient.invalidateQueries({ queryKey: ['models'] });
}

export async function searchHub(params: {
  search: string;
  pipeline: string;
  size: string;
  sort: string;
  direction: 'asc' | 'desc';
  limit: number;
  cursor?: string;
  caps?: string;
}): Promise<{ items: HubHit[]; messageKey?: string; hasNext: boolean; nextCursor?: string; pageSize: number }> {
  const query = new URLSearchParams({
    search: params.search,
    pipeline: params.pipeline,
    size: params.size,
    sort: params.sort,
    direction: params.direction,
    limit: String(params.limit),
  });
  if (params.cursor) query.set('cursor', params.cursor);
  if (params.caps) query.set('caps', params.caps);
  return apiFetch(`/models/hub?${query.toString()}`);
}

export async function hubFiles(id: string): Promise<HubFiles> {
  const query = new URLSearchParams({ id });
  return apiFetch(`/models/hub/files?${query.toString()}`);
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
