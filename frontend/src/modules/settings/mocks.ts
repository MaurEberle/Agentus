import {
  MCP_RECIPE_IDS,
  defaultSettings,
  type AppSettings,
  type AboutInfo,
  type CredentialKind,
  type CredentialListItem,
  type DataLocation,
  type HelpPing,
  type McpRecipe,
  type McpServerListItem,
  type RuntimeModel,
  type RuntimePing,
  type UpsertMcpServerInput,
} from '@/modules/settings/model';

const secrets = new Map<string, string>([
  ['cred-xai', 'sk-xai-mock-4k2a'],
  ['cred-search', 'search-mock-x7f2'],
]);

let settings: AppSettings = {
  ...defaultSettings(),
  helpChat: {
    ...defaultSettings().helpChat,
    credentialId: undefined,
  },
};

const credentials: CredentialListItem[] = [
  { id: 'cred-xai', name: 'xAI Cloud', kind: 'xai', mask: '…4k2a', inUse: true },
  { id: 'cred-search', name: 'Websuche', kind: 'web_search', mask: '…x7f2', inUse: false },
];

function recipeKind(id: string): CredentialKind[] {
  if (id === 'github') return ['github'];
  if (id === 'azure') return ['azure'];
  if (id === 'gitlab') return ['gitlab'];
  if (id === 'slack') return ['slack'];
  if (id === 'notion') return ['notion'];
  if (id === 'atlassian') return ['atlassian'];
  if (id === 'linear') return ['linear'];
  if (id === 'postgres') return ['postgres'];
  if (id === 'sentry') return ['token'];
  if (id === 'context7') return ['token'];
  return [];
}

function recipeNeedsRoot(id: string): boolean {
  return ['filesystem', 'git', 'pdf', 'excel', 'powerpoint', 'word', 'office'].includes(id);
}

function recipeTransport(id: string): 'stdio' | 'http' {
  return id === 'fetch' || id === 'context7' ? 'http' : 'stdio';
}

export const mockRecipes: McpRecipe[] = MCP_RECIPE_IDS.map((id) => ({
  id,
  titleKey: `settings.mcp.recipe.${id}`,
  transport: recipeTransport(id),
  credentialKinds: recipeKind(id),
  needsRoot: recipeNeedsRoot(id),
}));

const servers: McpServerListItem[] = [];

let dataLocation: DataLocation = {
  dataDir: 'C:\\Users\\Demo\\AppData\\Local\\Agentus-Network\\data',
  source: 'default',
  readOnly: false,
  stores: [
    { id: 'settings', fileName: 'settings.sqlite', ok: true, state: 'ok' },
    { id: 'help', fileName: 'help.sqlite', ok: true, state: 'ok' },
    { id: 'workspace', fileName: 'workspace.sqlite', ok: true, state: 'ok' },
    { id: 'history', fileName: 'history.sqlite', ok: true, state: 'ok' },
  ],
};

function delay(ms = 40) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function maskOf(secret: string): string {
  const tail = secret.slice(-4) || '****';
  return `…${tail}`;
}

function refreshInUse() {
  const used = new Set<string>();
  if (settings.helpChat.credentialId) used.add(settings.helpChat.credentialId);
  if (settings.helpChat.webSearchCredentialId) used.add(settings.helpChat.webSearchCredentialId);
  for (const server of servers) {
    for (const id of server.credentialIds ?? []) used.add(id);
  }
  for (const item of credentials) {
    item.inUse = used.has(item.id);
  }
}

export async function mockGetSettings(): Promise<AppSettings> {
  await delay();
  return structuredClone(settings);
}

export async function mockPatchSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  await delay();
  settings = {
    ...settings,
    ...patch,
    helpChat: patch.helpChat ? { ...settings.helpChat, ...patch.helpChat } : settings.helpChat,
  };
  refreshInUse();
  return structuredClone(settings);
}

export async function mockListCredentials(): Promise<{ items: CredentialListItem[] }> {
  await delay();
  refreshInUse();
  return { items: credentials.map((item) => ({ ...item })) };
}

export async function mockCreateCredential(input: {
  name: string;
  kind: CredentialKind;
  secret: string;
}): Promise<CredentialListItem> {
  await delay();
  const id = crypto.randomUUID();
  secrets.set(id, input.secret);
  const item: CredentialListItem = {
    id,
    name: input.name,
    kind: input.kind,
    mask: maskOf(input.secret),
    inUse: false,
  };
  credentials.push(item);
  return { ...item };
}

export async function mockUpdateCredential(
  id: string,
  input: { name?: string; kind?: CredentialKind; secret?: string },
): Promise<CredentialListItem> {
  await delay();
  const item = credentials.find((entry) => entry.id === id);
  if (!item) {
    const error = new Error('not found') as Error & { status: number };
    error.status = 404;
    throw error;
  }
  if (input.name) item.name = input.name;
  if (input.kind) item.kind = input.kind;
  if (input.secret) {
    secrets.set(id, input.secret);
    item.mask = maskOf(input.secret);
  }
  return { ...item };
}

export async function mockDeleteCredential(id: string): Promise<void> {
  await delay();
  refreshInUse();
  const item = credentials.find((entry) => entry.id === id);
  if (!item) return;
  if (item.inUse) {
    const error = new Error('in use') as Error & { status: number; messageKey: string };
    error.status = 409;
    error.messageKey = 'settings.notify.credentialInUse';
    throw error;
  }
  const index = credentials.findIndex((entry) => entry.id === id);
  credentials.splice(index, 1);
  secrets.delete(id);
}

export async function mockPingRuntime(): Promise<RuntimePing> {
  await delay(200);
  const ok = Boolean(settings.ollamaBaseUrl.includes('11434'));
  return { ok, messageKey: ok ? 'settings.runtime.pingOk' : 'settings.runtime.pingFail' };
}

export async function mockListRuntimeModels(): Promise<{ items: RuntimeModel[] }> {
  await delay();
  if (!settings.ollamaBaseUrl.includes('11434')) return { items: [] };
  return {
    items: [
      { name: 'llama3.2:1b', sizeBytes: 1_300_000_000 },
      { name: 'nomic-embed-text', sizeBytes: 274_000_000 },
    ],
  };
}

export async function mockPingHelpChat(): Promise<HelpPing> {
  await delay(200);
  const ok = Boolean(settings.helpChat.provider && settings.helpChat.model);
  return { ok, messageKey: ok ? 'settings.helpChat.pingOk' : 'settings.helpChat.pingFail' };
}

export async function mockClearHelpChatMessages(): Promise<void> {
  await delay();
}

export async function mockReindexHelpChat(): Promise<{ state: 'ready' | 'error'; messageKey?: string }> {
  await delay(250);
  return { state: 'ready' };
}

export async function mockListMcpRecipes(): Promise<{ items: McpRecipe[] }> {
  await delay();
  return { items: mockRecipes.map((item) => ({ ...item })) };
}

export async function mockListMcpServers(): Promise<{ items: McpServerListItem[] }> {
  await delay();
  return { items: servers.map((item) => ({ ...item })) };
}

export async function mockUpsertMcpServer(input: UpsertMcpServerInput): Promise<McpServerListItem> {
  await delay();
  if (input.id) {
    const existing = servers.find((item) => item.id === input.id);
    if (existing) {
      Object.assign(existing, input);
      refreshInUse();
      return { ...existing };
    }
  }
  const created: McpServerListItem = {
    id: crypto.randomUUID(),
    recipeId: input.recipeId,
    name: input.name,
    transport: input.transport,
    enabled: input.enabled ?? false,
    status: 'unknown',
    credentialIds: input.credentialIds,
    rootPath: input.rootPath,
    command: input.command,
    args: input.args,
    url: input.url,
  };
  servers.push(created);
  refreshInUse();
  return { ...created };
}

export async function mockSetMcpEnabled(id: string, enabled: boolean): Promise<McpServerListItem> {
  await delay();
  const item = servers.find((entry) => entry.id === id);
  if (!item) {
    const error = new Error('not found') as Error & { status: number };
    error.status = 404;
    throw error;
  }
  item.enabled = enabled;
  return { ...item };
}

export async function mockPingMcpServer(id: string): Promise<{ status: McpServerListItem['status']; messageKey?: string }> {
  await delay(200);
  const item = servers.find((entry) => entry.id === id);
  if (!item) {
    return { status: 'error', messageKey: 'settings.mcp.pingError' };
  }
  if (item.recipeId === 'playwright') {
    item.status = 'runtime_missing';
    return { status: 'runtime_missing', messageKey: 'settings.mcp.runtimeMissing' };
  }
  item.status = 'ok';
  return { status: 'ok', messageKey: 'settings.mcp.pingOk' };
}

export async function mockDeleteMcpServer(id: string): Promise<void> {
  await delay();
  const index = servers.findIndex((item) => item.id === id);
  if (index >= 0) servers.splice(index, 1);
  refreshInUse();
}

export async function mockGetDataLocation(): Promise<DataLocation> {
  await delay();
  return structuredClone(dataLocation);
}

export async function mockPickDataDir(): Promise<string | null> {
  await delay();
  return 'C:\\Users\\Demo\\AppData\\Local\\Agentus-Network\\data-alt';
}

export async function mockSetDataDir(input: { path: string; copy?: boolean }): Promise<DataLocation> {
  await delay();
  dataLocation = {
    ...dataLocation,
    dataDir: input.path,
    source: 'config',
    stores: dataLocation.stores.map((store) => ({ ...store, ok: true, state: 'ok' })),
  };
  return structuredClone(dataLocation);
}

export async function mockGetAbout(): Promise<AboutInfo> {
  await delay();
  return { apiVersion: '0.1.0', runtime: { ok: settings.ollamaBaseUrl.includes('11434') } };
}


