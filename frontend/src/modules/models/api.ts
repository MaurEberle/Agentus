import { API_BASE, ApiError, apiFetch, queryClient } from '@/api/client';
import type { HubFiles, HubHit, InstalledModel, PullEvent } from '@/modules/models/model';

export async function listInstalled(): Promise<{ items: InstalledModel[]; messageKey?: string }> {
  return apiFetch('/models');
}

export async function saveModelTags(name: string, tags: string[]): Promise<void> {
  await apiFetch('/models/tags', { method: 'PUT', body: JSON.stringify({ name, tags }) });
  await queryClient.invalidateQueries({ queryKey: ['models'] });
}

export async function searchHub(params: {
  search: string;
  pipeline: string;
  size: string;
  sort: string;
}): Promise<{ items: HubHit[]; messageKey?: string }> {
  const query = new URLSearchParams(params);
  return apiFetch(`/models/hub?${query.toString()}`);
}

export async function hubFiles(id: string): Promise<HubFiles> {
  const query = new URLSearchParams({ id });
  return apiFetch(`/models/hub/files?${query.toString()}`);
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
