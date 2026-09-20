import { useQuery } from '@tanstack/react-query';
import { ApiError, apiFetch, queryClient } from '@/api/client';
import { pickFolderPath } from '@/lib/pickFolder';
import type {
  AboutInfo,
  AppSettings,
  CredentialKind,
  CredentialListItem,
  DataLocation,
  HelpPing,
  LlmProvider,
  McpRecipe,
  McpServerListItem,
  RuntimeModel,
  RuntimePing,
  UpsertMcpServerInput,
} from '@/modules/settings/model';

export async function getSettings(): Promise<AppSettings> {
  return apiFetch<AppSettings>('/settings');
}

export async function patchSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  const next = await apiFetch<AppSettings>('/settings', { method: 'PATCH', body: JSON.stringify(patch) });
  queryClient.setQueryData(['settings'], next);
  await queryClient.invalidateQueries({ queryKey: ['settings'] });
  await queryClient.invalidateQueries({ queryKey: ['runtime'] });
  await queryClient.invalidateQueries({ queryKey: ['help-chat', 'status'] });
  return next;
}

export async function listCredentials(): Promise<{ items: CredentialListItem[] }> {
  return apiFetch<{ items: CredentialListItem[] }>('/credentials');
}

export async function createCredential(input: {
  name: string;
  kind: CredentialKind;
  secret: string;
}): Promise<CredentialListItem> {
  const item = await apiFetch<CredentialListItem>('/credentials', {
    method: 'POST',
    body: JSON.stringify(input),
  });
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
  await queryClient.invalidateQueries({ queryKey: ['runtime', 'models'] });
  return item;
}

export async function updateCredential(
  id: string,
  input: { name?: string; kind?: CredentialKind; secret?: string },
): Promise<CredentialListItem> {
  const item = await apiFetch<CredentialListItem>(`/credentials/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
  await queryClient.invalidateQueries({ queryKey: ['runtime', 'models'] });
  return item;
}

export async function deleteCredential(id: string): Promise<void> {
  try {
    await apiFetch<void>(`/credentials/${id}`, { method: 'DELETE' });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const status = (error as { status?: number }).status;
    if (status === 409) {
      throw new ApiError(409, 'settings.notify.credentialInUse');
    }
    throw error;
  }
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
  await queryClient.invalidateQueries({ queryKey: ['runtime', 'models'] });
}

export async function pingRuntime(): Promise<RuntimePing> {
  return apiFetch<RuntimePing>('/runtime/ping', { method: 'POST' });
}

export type RuntimeModelsParams = {
  provider?: LlmProvider;
  credentialId?: string;
  baseUrl?: string;
};

export type RuntimeModelList = { items: RuntimeModel[]; messageKey?: string };

export async function listRuntimeModels(params: RuntimeModelsParams = {}): Promise<RuntimeModelList> {
  const query = new URLSearchParams();
  if (params.provider) query.set('provider', params.provider);
  if (params.credentialId) query.set('credentialId', params.credentialId);
  if (params.baseUrl) query.set('baseUrl', params.baseUrl);
  const suffix = query.toString();
  return apiFetch<RuntimeModelList>(`/runtime/models${suffix ? `?${suffix}` : ''}`);
}

export async function pingHelpChat(): Promise<HelpPing> {
  return apiFetch<HelpPing>('/help-chat/ping', { method: 'POST' });
}

export async function clearHelpChatMessages(): Promise<void> {
  await apiFetch<void>('/help-chat/clear', { method: 'POST' });
  await queryClient.invalidateQueries({ queryKey: ['help-chat', 'messages'] });
}

export async function reindexHelpChat(): Promise<{ state: 'ready' | 'error'; messageKey?: string }> {
  return apiFetch('/help-chat/reindex', { method: 'POST' });
}

export async function listMcpRecipes(): Promise<{ items: McpRecipe[] }> {
  return apiFetch<{ items: McpRecipe[] }>('/mcp/recipes');
}

export async function listMcpServers(): Promise<{ items: McpServerListItem[] }> {
  return apiFetch<{ items: McpServerListItem[] }>('/mcp/servers');
}

export async function upsertMcpServer(input: UpsertMcpServerInput): Promise<McpServerListItem> {
  const item = input.id
    ? await apiFetch<McpServerListItem>(`/mcp/servers/${input.id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      })
    : await apiFetch<McpServerListItem>('/mcp/servers', {
        method: 'POST',
        body: JSON.stringify(input),
      });
  await queryClient.invalidateQueries({ queryKey: ['mcp'] });
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
  return item;
}

export async function setMcpEnabled(id: string, enabled: boolean): Promise<McpServerListItem> {
  const item = await apiFetch<McpServerListItem>(`/mcp/servers/${id}/enabled`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  });
  await queryClient.invalidateQueries({ queryKey: ['mcp'] });
  return item;
}

export async function pingMcpServer(id: string) {
  const result = await apiFetch<{ status: McpServerListItem['status']; messageKey?: string }>(
    `/mcp/servers/${id}/ping`,
    { method: 'POST' },
  );
  await queryClient.invalidateQueries({ queryKey: ['mcp'] });
  return result;
}

export async function deleteMcpServer(id: string): Promise<void> {
  await apiFetch<void>(`/mcp/servers/${id}`, { method: 'DELETE' });
  await queryClient.invalidateQueries({ queryKey: ['mcp'] });
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
}

export async function getDataLocation(): Promise<DataLocation> {
  return apiFetch<DataLocation>('/data-location');
}

export async function pickDataDir(): Promise<string | null> {
  return pickFolderPath();
}

export async function setDataDir(input: { path: string; copy?: boolean }): Promise<DataLocation> {
  const location = await apiFetch<DataLocation>('/data-location', {
    method: 'POST',
    body: JSON.stringify(input),
  });
  await queryClient.invalidateQueries({ queryKey: ['stores'] });
  await queryClient.invalidateQueries({ queryKey: ['settings'] });
  return location;
}

export async function getAbout(): Promise<AboutInfo> {
  return apiFetch<AboutInfo>('/about');
}

export async function resetHelpChatOnboarding(): Promise<AppSettings> {
  return patchSettings({ chatOnboardingSeen: false });
}

export function useSettingsQuery() {
  return useQuery({ queryKey: ['settings'], queryFn: getSettings });
}

export function useCredentialsQuery() {
  return useQuery({ queryKey: ['credentials'], queryFn: listCredentials });
}

export function useRuntimeModelsQuery(params: RuntimeModelsParams & { enabled?: boolean } = {}) {
  const provider = params.provider ?? 'ollama';
  const credentialId = params.credentialId ?? '';
  const baseUrl = params.baseUrl ?? '';
  const ollamaDefault = provider === 'ollama' && !credentialId && !baseUrl;
  return useQuery({
    queryKey: ollamaDefault
      ? ['runtime', 'models']
      : ['runtime', 'models', provider, credentialId, baseUrl],
    queryFn: () =>
      listRuntimeModels({
        provider: params.provider,
        credentialId: params.credentialId,
        baseUrl: params.baseUrl,
      }),
    enabled: params.enabled ?? true,
  });
}

export function useMcpRecipesQuery() {
  return useQuery({ queryKey: ['mcp', 'recipes'], queryFn: listMcpRecipes });
}

export function useMcpServersQuery() {
  return useQuery({ queryKey: ['mcp', 'servers'], queryFn: listMcpServers });
}

export function useStoresQuery() {
  return useQuery({ queryKey: ['stores'], queryFn: getDataLocation });
}

export function useAboutQuery() {
  return useQuery({ queryKey: ['about'], queryFn: getAbout });
}
