import { useQuery } from '@tanstack/react-query';
import { ApiError, apiFetch, queryClient, USE_MOCKS } from '@/api/client';
import { clearHelpMessageCache } from '@/components/help-chat/messageStore';
import { pickFolderPath } from '@/lib/pickFolder';
import {
  mockClearHelpChatMessages,
  mockCreateCredential,
  mockDeleteCredential,
  mockDeleteMcpServer,
  mockGetAbout,
  mockGetDataLocation,
  mockGetSettings,
  mockListCredentials,
  mockListMcpRecipes,
  mockListMcpServers,
  mockListRuntimeModels,
  mockPatchSettings,
  mockPingHelpChat,
  mockPingMcpServer,
  mockPingRuntime,
  mockReindexHelpChat,
  mockSetDataDir,
  mockSetMcpEnabled,
  mockUpdateCredential,
  mockUpsertMcpServer,
} from '@/modules/settings/mocks';
import type {
  AboutInfo,
  AppSettings,
  CredentialKind,
  CredentialListItem,
  DataLocation,
  HelpPing,
  McpRecipe,
  McpServerListItem,
  RuntimeModel,
  RuntimePing,
  UpsertMcpServerInput,
} from '@/modules/settings/model';

export async function getSettings(): Promise<AppSettings> {
  if (USE_MOCKS) return mockGetSettings();
  return apiFetch<AppSettings>('/settings');
}

export async function patchSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  const next = USE_MOCKS
    ? await mockPatchSettings(patch)
    : await apiFetch<AppSettings>('/settings', { method: 'PATCH', body: JSON.stringify(patch) });
  queryClient.setQueryData(['settings'], next);
  await queryClient.invalidateQueries({ queryKey: ['settings'] });
  await queryClient.invalidateQueries({ queryKey: ['runtime'] });
  await queryClient.invalidateQueries({ queryKey: ['help-chat', 'status'] });
  return next;
}

export async function listCredentials(): Promise<{ items: CredentialListItem[] }> {
  if (USE_MOCKS) return mockListCredentials();
  return apiFetch<{ items: CredentialListItem[] }>('/credentials');
}

export async function createCredential(input: {
  name: string;
  kind: CredentialKind;
  secret: string;
}): Promise<CredentialListItem> {
  const item = USE_MOCKS
    ? await mockCreateCredential(input)
    : await apiFetch<CredentialListItem>('/credentials', {
        method: 'POST',
        body: JSON.stringify(input),
      });
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
  return item;
}

export async function updateCredential(
  id: string,
  input: { name?: string; kind?: CredentialKind; secret?: string },
): Promise<CredentialListItem> {
  const item = USE_MOCKS
    ? await mockUpdateCredential(id, input)
    : await apiFetch<CredentialListItem>(`/credentials/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      });
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
  return item;
}

export async function deleteCredential(id: string): Promise<void> {
  try {
    if (USE_MOCKS) await mockDeleteCredential(id);
    else await apiFetch<void>(`/credentials/${id}`, { method: 'DELETE' });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const status = (error as { status?: number }).status;
    if (status === 409) {
      throw new ApiError(409, 'settings.notify.credentialInUse');
    }
    throw error;
  }
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
}

export async function pingRuntime(): Promise<RuntimePing> {
  if (USE_MOCKS) return mockPingRuntime();
  return apiFetch<RuntimePing>('/runtime/ping', { method: 'POST' });
}

export async function listRuntimeModels(): Promise<{ items: RuntimeModel[] }> {
  if (USE_MOCKS) return mockListRuntimeModels();
  return apiFetch<{ items: RuntimeModel[] }>('/runtime/models');
}

export async function pingHelpChat(): Promise<HelpPing> {
  if (USE_MOCKS) return mockPingHelpChat();
  return apiFetch<HelpPing>('/help-chat/ping', { method: 'POST' });
}

export async function clearHelpChatMessages(): Promise<void> {
  if (USE_MOCKS) {
    await mockClearHelpChatMessages();
    clearHelpMessageCache();
  } else await apiFetch<void>('/help-chat/clear', { method: 'POST' });
  await queryClient.invalidateQueries({ queryKey: ['help-chat', 'messages'] });
}

export async function reindexHelpChat(): Promise<{ state: 'ready' | 'error'; messageKey?: string }> {
  if (USE_MOCKS) return mockReindexHelpChat();
  return apiFetch('/help-chat/reindex', { method: 'POST' });
}

export async function listMcpRecipes(): Promise<{ items: McpRecipe[] }> {
  if (USE_MOCKS) return mockListMcpRecipes();
  return apiFetch<{ items: McpRecipe[] }>('/mcp/recipes');
}

export async function listMcpServers(): Promise<{ items: McpServerListItem[] }> {
  if (USE_MOCKS) return mockListMcpServers();
  return apiFetch<{ items: McpServerListItem[] }>('/mcp/servers');
}

export async function upsertMcpServer(input: UpsertMcpServerInput): Promise<McpServerListItem> {
  const item = USE_MOCKS
    ? await mockUpsertMcpServer(input)
    : input.id
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
  const item = USE_MOCKS
    ? await mockSetMcpEnabled(id, enabled)
    : await apiFetch<McpServerListItem>(`/mcp/servers/${id}/enabled`, {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      });
  await queryClient.invalidateQueries({ queryKey: ['mcp'] });
  return item;
}

export async function pingMcpServer(id: string) {
  const result = USE_MOCKS
    ? await mockPingMcpServer(id)
    : await apiFetch<{ status: McpServerListItem['status']; messageKey?: string }>(
        `/mcp/servers/${id}/ping`,
        { method: 'POST' },
      );
  await queryClient.invalidateQueries({ queryKey: ['mcp'] });
  return result;
}

export async function deleteMcpServer(id: string): Promise<void> {
  if (USE_MOCKS) await mockDeleteMcpServer(id);
  else await apiFetch<void>(`/mcp/servers/${id}`, { method: 'DELETE' });
  await queryClient.invalidateQueries({ queryKey: ['mcp'] });
  await queryClient.invalidateQueries({ queryKey: ['credentials'] });
}

export async function getDataLocation(): Promise<DataLocation> {
  if (USE_MOCKS) return mockGetDataLocation();
  return apiFetch<DataLocation>('/data-location');
}

export async function pickDataDir(): Promise<string | null> {
  return pickFolderPath();
}

export async function setDataDir(input: { path: string; copy?: boolean }): Promise<DataLocation> {
  const location = USE_MOCKS
    ? await mockSetDataDir(input)
    : await apiFetch<DataLocation>('/data-location', {
        method: 'POST',
        body: JSON.stringify(input),
      });
  await queryClient.invalidateQueries({ queryKey: ['stores'] });
  await queryClient.invalidateQueries({ queryKey: ['settings'] });
  return location;
}

export async function getAbout(): Promise<AboutInfo> {
  if (USE_MOCKS) return mockGetAbout();
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

export function useRuntimeModelsQuery() {
  return useQuery({ queryKey: ['runtime', 'models'], queryFn: listRuntimeModels });
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
