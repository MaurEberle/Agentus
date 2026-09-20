export const SETTINGS_SECTIONS = [
  'appearance',
  'credentials',
  'runtime',
  'help-chat',
  'mcp',
  'data',
  'about',
] as const;

export type SettingsSectionId = (typeof SETTINGS_SECTIONS)[number];

export const CREDENTIAL_KINDS = [
  'xai',
  'openai',
  'anthropic',
  'gemini',
  'openai_compat',
  'web_search',
  'github',
  'azure',
  'gitlab',
  'slack',
  'notion',
  'atlassian',
  'linear',
  'postgres',
  'token',
] as const;

export type CredentialKind = (typeof CREDENTIAL_KINDS)[number];

export const LLM_PROVIDERS = [
  'ollama',
  'xai',
  'openai',
  'anthropic',
  'gemini',
  'openai_compat',
] as const;

export type LlmProvider = (typeof LLM_PROVIDERS)[number];
export const CLOUD_CATALOG_PROVIDERS = ['xai', 'openai', 'anthropic', 'gemini'] as const;
export type CloudCatalogProvider = (typeof CLOUD_CATALOG_PROVIDERS)[number];
export type HelpProvider = LlmProvider | '';
export type EmbeddingProvider = 'ollama' | 'openai_compat' | '';

export function isCloudCatalogProvider(provider: string): provider is CloudCatalogProvider {
  return (CLOUD_CATALOG_PROVIDERS as readonly string[]).includes(provider);
}

export function providerNeedsCredential(provider: string): boolean {
  return Boolean(provider) && provider !== 'ollama';
}

export function credentialMatchesProvider(kind: string, provider: string): boolean {
  return kind === provider || kind === 'token';
}

export type CredentialListItem = {
  id: string;
  name: string;
  kind: CredentialKind;
  mask: string;
  inUse?: boolean;
};

export type HelpChatSettings = {
  provider: HelpProvider;
  model: string;
  credentialId?: string;
  embeddingProvider?: EmbeddingProvider;
  embeddingModel?: string;
  webSearchEnabled: boolean;
  webSearchCredentialId?: string;
  fallbackModel?: string;
};

export type HistoryRetentionDays = 30 | 90 | 365 | null;

export type AppSettings = {
  ollamaBaseUrl: string;
  openaiCompatBaseUrl?: string;
  helpChatFabVisible: boolean;
  helpChat: HelpChatSettings;
  activeNetworkId?: string | null;
  historyRetentionDays: HistoryRetentionDays;
  chatOnboardingSeen?: boolean;
};

export type StoreId = 'settings' | 'help' | 'workspace' | 'history';

export type StoreStatus = {
  id: StoreId;
  fileName: string;
  ok: boolean;
  state: 'ok' | 'missing' | 'error';
  messageKey?: string;
};

export type DataLocation = {
  dataDir: string;
  source: 'config' | 'env' | 'portable' | 'default';
  readOnly?: boolean;
  stores: StoreStatus[];
};

export type McpTransport = 'stdio' | 'http';
export type McpServerStatus = 'unknown' | 'ok' | 'error' | 'runtime_missing';

export type McpRecipe = {
  id: string;
  titleKey: string;
  transport: McpTransport;
  credentialKinds: CredentialKind[];
  needsRoot?: boolean;
};

export type McpServerListItem = {
  id: string;
  recipeId?: string;
  name: string;
  transport: McpTransport;
  enabled: boolean;
  status: McpServerStatus;
  credentialIds?: string[];
  rootPath?: string;
  command?: string;
  args?: string[];
  url?: string;
};

export type RuntimePing = { ok: boolean; messageKey?: string };
export type RuntimeModel = { name: string; sizeBytes?: number };
export type HelpPing = { ok: boolean; messageKey?: string };
export type AboutInfo = { apiVersion: string; runtime?: { ok: boolean } };

export type UpsertMcpServerInput = {
  id?: string;
  recipeId?: string;
  name: string;
  transport: McpTransport;
  credentialIds?: string[];
  rootPath?: string;
  command?: string;
  args?: string[];
  url?: string;
  enabled?: boolean;
};

export const MCP_RECIPE_IDS = [
  'github',
  'azure',
  'gitlab',
  'filesystem',
  'git',
  'playwright',
  'postgres',
  'context7',
  'slack',
  'notion',
  'atlassian',
  'linear',
  'fetch',
  'sentry',
  'pdf',
  'excel',
  'powerpoint',
  'word',
  'office',
] as const;

export function parseSettingsSection(hash: string): SettingsSectionId {
  const raw = hash.replace(/^#/, '');
  const normalized = raw === 'chatbot' ? 'help-chat' : raw;
  return (SETTINGS_SECTIONS as readonly string[]).includes(normalized)
    ? (normalized as SettingsSectionId)
    : 'appearance';
}

export function isForbiddenDataRoot(path: string): boolean {
  const normalized = path.trim().replace(/\\/g, '/').replace(/\/+$/, '');
  if (!normalized) return true;
  if (normalized === '/' || normalized === 'C:' || /^[A-Za-z]:$/.test(normalized)) return true;
  return false;
}

export function helpChatConfigured(help: HelpChatSettings): boolean {
  if (!help.provider || !help.model.trim()) return false;
  if (providerNeedsCredential(help.provider) && !help.credentialId) {
    return false;
  }
  return true;
}

function optionalText(value: string | null | undefined): string {
  return value?.trim() ? value : '';
}

export function helpChatSnapshot(help: HelpChatSettings): string {
  return JSON.stringify({
    provider: help.provider || '',
    model: help.model || '',
    credentialId: providerNeedsCredential(help.provider) ? optionalText(help.credentialId) : '',
    embeddingProvider: help.embeddingProvider || '',
    embeddingModel: optionalText(help.embeddingModel),
    webSearchEnabled: Boolean(help.webSearchEnabled),
    webSearchCredentialId: help.webSearchEnabled ? optionalText(help.webSearchCredentialId) : '',
    fallbackModel: optionalText(help.fallbackModel),
  });
}

export function helpChatWritePayload(help: HelpChatSettings) {
  const credentialId = providerNeedsCredential(help.provider) ? optionalText(help.credentialId) : '';
  const webSearchCredentialId = help.webSearchEnabled ? optionalText(help.webSearchCredentialId) : '';
  return {
    provider: help.provider,
    model: help.model,
    credentialId: credentialId || null,
    embeddingProvider: help.embeddingProvider || '',
    embeddingModel: optionalText(help.embeddingModel),
    webSearchEnabled: Boolean(help.webSearchEnabled),
    webSearchCredentialId: webSearchCredentialId || null,
    fallbackModel: optionalText(help.fallbackModel) || null,
  };
}

export function isEmbeddingModelName(name: string): boolean {
  return name.toLowerCase().includes('embed');
}

export function defaultHelpChat(): HelpChatSettings {
  return {
    provider: 'ollama',
    model: 'llama3.2:1b',
    embeddingProvider: 'ollama',
    embeddingModel: 'nomic-embed-text',
    webSearchEnabled: false,
    fallbackModel: 'llama3.2:1b',
  };
}

export function defaultSettings(): AppSettings {
  return {
    ollamaBaseUrl: 'http://127.0.0.1:11434',
    helpChatFabVisible: true,
    helpChat: defaultHelpChat(),
    activeNetworkId: null,
    historyRetentionDays: 90,
    chatOnboardingSeen: false,
  };
}
