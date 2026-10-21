import { apiFetch, queryClient } from '@/api/client';
import { applyTagEdit } from '@/lib/tags';
import type { PromptDetail, PromptDraft, PromptListItem } from '@/modules/prompts/model';

async function refresh() {
  await queryClient.invalidateQueries({ queryKey: ['prompts'] });
}

export async function listPrompts(): Promise<{ items: PromptListItem[] }> {
  return apiFetch('/prompts');
}

export async function getPrompt(id: string): Promise<PromptDetail> {
  return apiFetch(`/prompts/${id}`);
}

export async function createPrompt(draft: PromptDraft): Promise<PromptDetail> {
  const item = await apiFetch<PromptDetail>('/prompts', { method: 'POST', body: JSON.stringify(draft) });
  await refresh();
  return item;
}

export async function updatePrompt(id: string, draft: PromptDraft): Promise<PromptDetail> {
  const item = await apiFetch<PromptDetail>(`/prompts/${id}`, { method: 'PATCH', body: JSON.stringify(draft) });
  await refresh();
  return item;
}

export async function deletePrompts(ids: string[]): Promise<void> {
  if (ids.length === 1) await apiFetch<void>(`/prompts/${ids[0]}`, { method: 'DELETE' });
  else await apiFetch<void>('/prompts', { method: 'DELETE', body: JSON.stringify({ ids }) });
  await refresh();
}

export async function duplicatePrompt(id: string): Promise<PromptDetail> {
  const item = await apiFetch<PromptDetail>(`/prompts/${id}/duplicate`, { method: 'POST' });
  await refresh();
  return item;
}

export async function savePromptTags(items: PromptListItem[], seed: string[], next: string[]): Promise<void> {
  await Promise.all(
    items.map((item) =>
      apiFetch(`/prompts/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ tags: applyTagEdit(item.tags, seed, next) }),
      }),
    ),
  );
  await refresh();
}

export async function exportPrompt(id: string): Promise<PromptDraft & { schemaVersion: number; kind: string; exportedAt: string }> {
  return apiFetch(`/prompts/${id}/export`);
}

export async function importPrompts(items: PromptDraft[]): Promise<{ items: PromptDetail[] }> {
  const result = await apiFetch<{ items: PromptDetail[] }>('/prompts/import', {
    method: 'POST',
    body: JSON.stringify({
      items: items.map((item) => ({ schemaVersion: 1, kind: 'agentus.prompt', ...item })),
    }),
  });
  await refresh();
  return result;
}
