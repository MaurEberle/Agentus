import { useQuery } from '@tanstack/react-query';
import { API_BASE, ApiError, apiFetch, queryClient } from '@/api/client';
import { getSession } from '@/api/session';
import i18n, { resolveAppLanguage } from '@/i18n';
import { useAppStore } from '@/store';
import type { AgentNetworkDocument } from '@/modules/network/model/document';
import type { LlmProvider } from '@/modules/settings/model';

export const BRIEF_FIELDS = ['goal', 'input', 'output', 'sources', 'deployment', 'tools', 'constraints'] as const;
export type BriefField = (typeof BRIEF_FIELDS)[number];
export type Brief = Partial<Record<BriefField, string>>;

export type ArchitectProblem = { severity: 'error' | 'hint'; text: string; ref?: string; key?: string };
export type ArchitectCheck = { ok: boolean; nodes: number; edges: number; errors: ArchitectProblem[]; hints: ArchitectProblem[] };
export type DraftNode = { ref: string; type: string; data: Record<string, unknown> };
export type Draft = { name: string; description: string; tags: string[]; nodes: DraftNode[]; links: string[][] };
/** One tool call in the chat: an i18n key (architect.tool.*) with its values. */
export type ToolLine = { name: string; key: string; params?: Record<string, unknown>; ok: boolean };

export type ArchitectMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  tools: ToolLine[];
};

export type SessionSummary = {
  id: string;
  title: string;
  provider: LlmProvider;
  model: string;
  credentialId?: string | null;
  state: 'active' | 'ended';
  createdAt: string;
  updatedAt: string;
  networkId?: string | null;
};

export type LoadPurpose = 'change' | 'template';

/** The network the draft builds on (entwurf.md, 7.3). */
export type ArchitectSource = {
  networkId: string;
  name: string;
  purpose: LoadPurpose;
  version?: number | null;
  revision?: number | null;
  /** ref -> folder fields a cloud model does not see; their values stay. */
  hidden?: Record<string, string[]>;
  loadedAt?: string;
};

export type AppliedEntry = {
  networkId: string;
  name: string;
  mode: 'create' | 'update';
  version: number;
  revision: number;
  previousVersion: number | null;
  changed: boolean;
  at: string;
  undone?: boolean;
  undoneAs?: number;
};

export type { DiffEdge, NetworkDiff } from '@/modules/network/model/diff';
import type { NetworkDiff } from '@/modules/network/model/diff';

/** What the model asked for: read a network in, or the closing dialog. Nothing happens without a click. */
export type Proposal =
  | { kind: 'load'; networkId: string; name: string; purpose: LoadPurpose }
  | { kind: 'create' | 'update'; summary: string; createdAt: string };

export type ArchitectState = {
  brief: Brief;
  draft: Draft | null;
  document: AgentNetworkDocument | null;
  check: ArchitectCheck | null;
  ids: Record<string, string>;
  proposal: Proposal | null;
  source: ArchitectSource | null;
  applied: AppliedEntry[];
  diff: NetworkDiff | null;
};

export type SessionDetail = SessionSummary &
  ArchitectState & {
    catalogChanged: boolean;
    messages: ArchitectMessage[];
  };

export type ClosingPreview = {
  mode: 'create' | 'update';
  target: { id: string; name: string; version: number; revision: number } | null;
  name: string;
  description: string;
  summary: string;
  document: AgentNetworkDocument;
  ids: Record<string, string>;
  check: ArchitectCheck;
  diff: NetworkDiff | null;
  changedSince: boolean;
  running: boolean;
  networkRunning: boolean;
  risks: ArchitectProblem[];
  prompts: { id: string; ref?: string; name?: string; chars: number }[];
  stats: { counts: Record<string, number>; models: string[]; tools: string[]; edges: number };
  canUndo: boolean;
};

export type ApplyResult = AppliedEntry & { activeSet: boolean; promptsAdded: number; session: SessionDetail };

/** The last application, if it changed a network and can still be taken back (E-17). */
export function undoable(applied: AppliedEntry[] | undefined): AppliedEntry | null {
  const last = applied && applied.length > 0 ? applied[applied.length - 1] : null;
  if (!last || last.undone || last.mode !== 'update' || !last.changed || !last.previousVersion) return null;
  return last;
}

export type ModelCheck = {
  ok: boolean;
  reasons: string[];
  warnings: string[];
  parametersB: number | null;
  context: number | null;
  local: boolean;
};
export type GpuCheck = {
  needBytes: number;
  freeVramBytes: number;
  freeRamBytes: number;
  fits: boolean;
  canForce: boolean;
  networkRunning: boolean;
};

export type ArchitectStatus = {
  active: {
    sessionId: string;
    provider: LlmProvider;
    model: string;
    local: boolean;
    slow: boolean;
    generating: boolean;
    idleSeconds: number;
    idleLimitSeconds: number;
    idleWarnSeconds: number;
  } | null;
  helpPaused: boolean;
};

/** A start the backend turned down: why, and the check it based that on. */
export class StartRefused extends Error {
  constructor(
    readonly messageKey: string,
    readonly gpu: GpuCheck | undefined,
    readonly model: ModelCheck | undefined,
  ) {
    super(messageKey);
  }
}

export const architectKeys = {
  status: ['architect', 'status'] as const,
  sessions: ['architect', 'sessions'] as const,
  session: (id: string) => ['architect', 'session', id] as const,
};

export function useArchitectStatusQuery() {
  return useQuery({
    queryKey: architectKeys.status,
    queryFn: () => apiFetch<ArchitectStatus>('/architect/status'),
    refetchInterval: 5000,
  });
}

export function useSessionsQuery() {
  return useQuery({
    queryKey: architectKeys.sessions,
    queryFn: async () => (await apiFetch<{ items: SessionSummary[] }>('/architect/sessions')).items,
  });
}

export function useSessionQuery(id: string | null) {
  return useQuery({
    queryKey: architectKeys.session(id ?? ''),
    queryFn: () => apiFetch<SessionDetail>(`/architect/sessions/${id}`),
    enabled: Boolean(id),
  });
}

export async function checkModel(body: { provider: string; model: string; credentialId?: string | null }) {
  return apiFetch<{ model: ModelCheck; gpu?: GpuCheck }>('/architect/model-check', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function createSession(body: { provider: string; model: string; credentialId?: string | null }) {
  const created = await apiFetch<SessionSummary>('/architect/sessions', { method: 'POST', body: JSON.stringify(body) });
  await queryClient.invalidateQueries({ queryKey: architectKeys.sessions });
  return created;
}

export async function startSession(
  id: string,
  body: { provider?: string; model?: string; credentialId?: string | null; forceSlow?: boolean; confirmRunning?: boolean },
) {
  const response = await fetch(`${API_BASE}/architect/sessions/${id}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    messageKey?: string;
    gpu?: GpuCheck;
    model?: ModelCheck;
    slow?: boolean;
  };
  if (!response.ok) {
    throw new StartRefused(payload.messageKey ?? 'architect.failed', payload.gpu, payload.model);
  }
  await refreshArchitect(id);
  return payload;
}

export async function stopSession(id: string) {
  await apiFetch(`/architect/sessions/${id}/stop`, { method: 'POST' });
  await refreshArchitect(id);
}

export async function abortSession(id: string) {
  await apiFetch(`/architect/sessions/${id}/abort`, { method: 'POST' });
}

export async function patchSession(id: string, body: { title?: string; brief?: Brief }) {
  const detail = await apiFetch<SessionDetail>(`/architect/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
  queryClient.setQueryData(architectKeys.session(id), detail);
  await queryClient.invalidateQueries({ queryKey: architectKeys.sessions });
  return detail;
}

export async function deleteSession(id: string) {
  await apiFetch(`/architect/sessions/${id}`, { method: 'DELETE' });
  queryClient.removeQueries({ queryKey: architectKeys.session(id) });
  await refreshArchitect(null);
}

export function useClosingQuery(id: string | null, open: boolean, mode?: 'create' | 'update') {
  return useQuery({
    queryKey: ['architect', 'closing', id ?? '', mode ?? ''],
    queryFn: () =>
      apiFetch<ClosingPreview>(`/architect/sessions/${id}/closing${mode ? `?mode=${mode}` : ''}`),
    enabled: Boolean(id) && open,
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
}

function storeDetail(id: string, detail: SessionDetail) {
  queryClient.setQueryData(architectKeys.session(id), detail);
  void queryClient.invalidateQueries({ queryKey: architectKeys.sessions });
}

/** E-6, E-10, E-12: read a network in, only on the user's click. */
export async function loadNetwork(id: string, networkId: string, purpose: LoadPurpose) {
  const detail = await apiFetch<SessionDetail>(`/architect/sessions/${id}/load`, {
    method: 'POST',
    body: JSON.stringify({ networkId, purpose }),
  });
  storeDetail(id, detail);
  return detail;
}

export async function dismissProposal(id: string) {
  const detail = await apiFetch<SessionDetail>(`/architect/sessions/${id}/proposal/dismiss`, { method: 'POST' });
  storeDetail(id, detail);
  return detail;
}

async function afterNetworkWrite(networkId: string) {
  // The editor must load the new state, not a cached one.
  queryClient.removeQueries({ queryKey: ['networks', networkId, 'document'] });
  await queryClient.invalidateQueries({ queryKey: ['networks'] });
}

export async function applySession(
  id: string,
  body: { mode?: 'create' | 'update'; setActive?: boolean; promptsToLibrary?: boolean; force?: boolean },
) {
  const result = await apiFetch<ApplyResult>(`/architect/sessions/${id}/apply`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  storeDetail(id, result.session);
  await afterNetworkWrite(result.networkId);
  if (result.promptsAdded > 0) void queryClient.invalidateQueries({ queryKey: ['prompts'] });
  if (result.activeSet) {
    useAppStore.getState().hydrateSession(await getSession());
    void queryClient.invalidateQueries({ queryKey: ['session'] });
  }
  return result;
}

export async function undoSession(id: string) {
  const result = await apiFetch<{ networkId: string; version: number; restoredFrom: number; session: SessionDetail }>(
    `/architect/sessions/${id}/undo`,
    { method: 'POST' },
  );
  storeDetail(id, result.session);
  await afterNetworkWrite(result.networkId);
  return result;
}

export async function exportSession(id: string) {
  return apiFetch<{ name: string; markdown: string }>(`/architect/sessions/${id}/export`);
}

export async function refreshArchitect(id: string | null) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: architectKeys.status }),
    queryClient.invalidateQueries({ queryKey: architectKeys.sessions }),
    id ? queryClient.invalidateQueries({ queryKey: architectKeys.session(id) }) : Promise.resolve(),
    queryClient.invalidateQueries({ queryKey: ['help-chat', 'status'] }),
  ]);
}

export type TurnHandlers = {
  onDelta: (chunk: string) => void;
  onTool: (event: { id: string; name: string; status: 'running' | 'done' | 'failed'; key?: string; params?: Record<string, unknown> }) => void;
  onState: (state: ArchitectState) => void;
  onDone: (message: ArchitectMessage) => void;
  onError: (messageKey: string) => void;
  onAborted: () => void;
};

/** Send one message; the answer, tool calls and state changes arrive as server-sent events. */
export function sendMessage(id: string, text: string, handlers: TurnHandlers): { abort: () => void } {
  const controller = new AbortController();
  void (async () => {
    let settled = false;
    try {
      const response = await fetch(`${API_BASE}/architect/sessions/${id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ text, locale: resolveAppLanguage(i18n.language) }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        const body = (await response.json().catch(() => ({}))) as { messageKey?: string };
        handlers.onError(body.messageKey ?? 'architect.failed');
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventName = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventName = line.slice(6).trim();
            continue;
          }
          if (!line.startsWith('data:')) {
            if (line.trim() === '') eventName = '';
            continue;
          }
          const payload = JSON.parse(line.slice(5).trim()) as Record<string, unknown>;
          if (eventName === 'delta' && typeof payload.chunk === 'string') handlers.onDelta(payload.chunk);
          if (eventName === 'tool') handlers.onTool(payload as Parameters<TurnHandlers['onTool']>[0]);
          if (eventName === 'state') handlers.onState(payload as unknown as ArchitectState);
          if (eventName === 'done') {
            settled = true;
            handlers.onDone(payload.message as ArchitectMessage);
          }
          if (eventName === 'error') {
            settled = true;
            handlers.onError(typeof payload.messageKey === 'string' ? payload.messageKey : 'architect.failed');
          }
          if (eventName === 'aborted') {
            settled = true;
            handlers.onAborted();
          }
        }
      }
      if (!settled) handlers.onError('architect.failed');
    } catch (caught) {
      if (controller.signal.aborted) {
        handlers.onAborted();
        return;
      }
      handlers.onError(caught instanceof ApiError && caught.messageKey ? caught.messageKey : 'architect.failed');
    } finally {
      await refreshArchitect(id);
    }
  })();
  return {
    abort: () => {
      void abortSession(id);
    },
  };
}
