import { ApiError } from '@/api/client';
import { peekMockSession } from '@/api/mocks';
import { mockGetDataLocation } from '@/modules/settings/mocks';
import { useAppStore } from '@/store';
import { maskLog } from '@/modules/monitoring/model/mask';
import { modelKey } from '@/modules/history/model/format';
import type {
  ErrorClass,
  GraphSnapshot,
  LlmCall,
  LlmProvider,
  LogEvent,
  LogFilter,
  RunChatMessage,
  RunDetail,
  RunListFilter,
  RunOutcome,
  RunStep,
  RunSummary,
} from '@/modules/history/model/types';

type RunRecord = {
  summary: RunSummary;
  steps?: RunStep[];
  calls: LlmCall[];
  graphSnapshot?: GraphSnapshot;
  chat?: RunChatMessage[];
  logs: LogEvent[];
};

function delay(ms = 40) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function atHours(hoursAgo: number, durationMs: number): { startedAt: string; endedAt: string } {
  const ended = Date.now() - hoursAgo * 60 * 60 * 1000;
  return {
    startedAt: new Date(ended - durationMs).toISOString(),
    endedAt: new Date(ended).toISOString(),
  };
}

const demoGraph: GraphSnapshot = {
  nodes: [
    { id: 'chat-1', type: 'chat_input', position: { x: 0, y: 160 }, data: { displayName: 'Eingabe' } },
    { id: 'llm-1', type: 'llm', position: { x: 0, y: 0 }, data: { displayName: 'Lokal' } },
    { id: 'agent-1', type: 'agent', position: { x: 280, y: 120 }, data: { displayName: 'Assistent' } },
    { id: 'end-1', type: 'end', position: { x: 560, y: 160 }, data: { displayName: 'Ende' } },
  ],
  edges: [
    { id: 'e1', source: 'chat-1', target: 'agent-1', sourceHandle: 'message', targetHandle: 'message' },
    { id: 'e2', source: 'llm-1', target: 'agent-1', sourceHandle: 'llm', targetHandle: 'llm' },
    { id: 'e3', source: 'agent-1', target: 'end-1', sourceHandle: 'message', targetHandle: 'message' },
  ],
};

function stepsFor(outcome: RunOutcome, errorNode?: string): RunStep[] {
  const agentStatus = outcome === 'failed' || outcome === 'timeout' ? 'error' : 'done';
  return [
    { nodeId: 'chat-1', nodeName: 'Eingabe', role: 'chat_input', type: 'chat_input', status: 'done' },
    { nodeId: 'llm-1', nodeName: 'Lokal', role: 'llm', type: 'llm', status: outcome === 'running' ? 'running' : 'done' },
    {
      nodeId: 'agent-1',
      nodeName: 'Assistent',
      role: 'agent',
      type: 'agent',
      status: errorNode === 'agent-1' ? 'error' : agentStatus,
      errorMessage: errorNode === 'agent-1' ? 'tool_error' : undefined,
    },
    { nodeId: 'end-1', nodeName: 'Ende', role: 'end', type: 'end', status: outcome === 'succeeded' ? 'done' : 'idle' },
  ];
}

function logsFor(runId: string, startedAt: string, secret: boolean): LogEvent[] {
  const start = Date.parse(startedAt);
  const line = (
    offsetSec: number,
    level: LogEvent['level'],
    nodeId: string,
    nodeName: string,
    message: string,
    extra?: Partial<LogEvent>,
  ): LogEvent => ({
    id: `${runId}-${offsetSec}-${level}`,
    ts: new Date(start + offsetSec * 1000).toISOString(),
    level,
    runId,
    nodeId,
    nodeName,
    message,
    ...extra,
  });
  const rows: LogEvent[] = [
    line(0, 'info', 'chat-1', 'Eingabe', 'Lauf gestartet.'),
    line(2, 'debug', 'llm-1', 'Lokal', 'Prompt vorbereitet.'),
    line(6, 'info', 'agent-1', 'Assistent', 'Agent arbeitet.'),
    line(12, 'info', 'llm-1', 'Lokal', 'Antwort empfangen.', { payload: { tokensOut: 88 } }),
  ];
  if (secret) {
    rows.push(
      line(14, 'warn', 'agent-1', 'Assistent', 'Anfrage mit apiKey=sk-history-demo-secret', {
        payload: { apiKey: 'sk-history-demo-secret', authorization: 'Bearer super-secret-token' },
      }),
      line(16, 'error', 'agent-1', 'Assistent', 'Werkzeuglauf fehlgeschlagen.', {
        stack: 'ToolError: timeout\n    at executor (run.py:41)',
        payload: { waitReason: 'tool' },
      }),
    );
  }
  rows.push(line(20, 'info', 'end-1', 'Ende', 'Lauf beendet.'));
  return rows;
}

function call(
  runId: string,
  id: string,
  provider: LlmProvider,
  model: string,
  ok: boolean,
  durationMs: number,
  extra?: Partial<LlmCall>,
): LlmCall {
  return {
    id,
    runId,
    nodeId: 'llm-1',
    nodeName: provider === 'xai' ? 'Cloud' : 'Lokal',
    provider,
    model,
    ok,
    durationMs,
    tokensIn: extra?.tokensIn ?? 420,
    tokensOut: extra?.tokensOut ?? 90,
    errorMessage: ok ? undefined : extra?.errorMessage ?? 'llm_error',
  };
}

function record(partial: {
  runId: string;
  networkId: string;
  networkName: string;
  hoursAgo: number;
  durationMs: number;
  outcome: RunOutcome;
  provider: LlmProvider;
  model: string;
  errorMessage?: string;
  errorClass?: ErrorClass;
  errorNodeName?: string;
  graph?: boolean;
  chat?: boolean;
  secret?: boolean;
  extraCalls?: LlmCall[];
}): RunRecord {
  const times = atHours(partial.hoursAgo, partial.durationMs);
  const models = [{ provider: partial.provider, model: partial.model }];
  const summary: RunSummary = {
    runId: partial.runId,
    networkId: partial.networkId,
    networkName: partial.networkName,
    startedAt: times.startedAt,
    endedAt: times.endedAt,
    outcome: partial.outcome,
    errorMessage: partial.errorMessage,
    errorClass: partial.errorClass,
    errorNodeId: partial.errorNodeName ? 'agent-1' : undefined,
    errorNodeName: partial.errorNodeName,
    models,
  };
  const callOk =
    partial.outcome === 'timeout' || partial.errorClass === 'llm_error'
      ? false
      : partial.outcome !== 'failed' || partial.errorClass === 'tool_error' || partial.errorClass === 'validation';
  const mainCall = call(
    partial.runId,
    `${partial.runId}-c1`,
    partial.provider,
    partial.model,
    callOk,
    Math.round(partial.durationMs * 0.6),
    callOk ? undefined : { errorMessage: partial.errorClass ?? 'llm_error' },
  );
  const chat: RunChatMessage[] | undefined = partial.chat
    ? [
        {
          id: `${partial.runId}-u`,
          role: 'user',
          content: 'Fasse den letzten Lauf kurz zusammen.',
          createdAt: times.startedAt,
        },
        {
          id: `${partial.runId}-a`,
          role: 'assistant',
          content: 'Der Lauf ist im Archiv. Diese Nachricht ist nur gelesen.',
          createdAt: times.endedAt,
        },
      ]
    : undefined;
  return {
    summary,
    steps: stepsFor(partial.outcome, partial.errorNodeName ? 'agent-1' : undefined),
    calls: [mainCall, ...(partial.extraCalls ?? [])],
    graphSnapshot: partial.graph === false ? undefined : demoGraph,
    chat,
    logs: logsFor(partial.runId, times.startedAt, Boolean(partial.secret)),
  };
}

function seed(): RunRecord[] {
  const demo = { networkId: 'net-demo', networkName: 'Demo-Netz' };
  const support = { networkId: 'net-support', networkName: 'Support-Netz' };
  const specials: RunRecord[] = [
    record({
      runId: 'run-chat',
      ...demo,
      hoursAgo: 2,
      durationMs: 48_000,
      outcome: 'succeeded',
      provider: 'ollama',
      model: 'llama3.2:1b',
      graph: true,
      chat: true,
    }),
    record({
      runId: 'run-secret',
      ...support,
      hoursAgo: 5,
      durationMs: 18_000,
      outcome: 'failed',
      provider: 'xai',
      model: 'grok-3',
      errorMessage: 'Werkzeuglauf fehlgeschlagen',
      errorClass: 'tool_error',
      errorNodeName: 'Assistent',
      secret: true,
    }),
    record({
      runId: 'run-nograph',
      ...demo,
      hoursAgo: 26,
      durationMs: 33_000,
      outcome: 'succeeded',
      provider: 'ollama',
      model: 'llama3.2:1b',
      graph: false,
    }),
    record({
      runId: 'run-timeout',
      ...support,
      hoursAgo: 30,
      durationMs: 120_000,
      outcome: 'timeout',
      provider: 'xai',
      model: 'grok-3',
      errorMessage: 'Schritt überschritt das Zeitlimit',
      errorClass: 'timeout',
      errorNodeName: 'Assistent',
    }),
    record({
      runId: 'run-cancelled',
      ...demo,
      hoursAgo: 54,
      durationMs: 9_000,
      outcome: 'cancelled',
      provider: 'ollama',
      model: 'llama3.2:1b',
    }),
    record({
      runId: 'run-badcall',
      ...demo,
      hoursAgo: 8,
      durationMs: 41_000,
      outcome: 'succeeded',
      provider: 'ollama',
      model: 'llama3.2:1b',
      extraCalls: [
        call('run-badcall', 'run-badcall-c2', 'xai', 'grok-3', false, 900, {
          tokensIn: 200,
          tokensOut: 12,
          errorMessage: 'provider 429',
        }),
      ],
    }),
    record({
      runId: 'run-llm-error',
      ...support,
      hoursAgo: 14,
      durationMs: 11_000,
      outcome: 'failed',
      provider: 'xai',
      model: 'grok-3',
      errorMessage: 'Modellantwort ungültig',
      errorClass: 'llm_error',
      errorNodeName: 'Lokal',
    }),
    record({
      runId: 'run-old',
      ...demo,
      hoursAgo: 100 * 24,
      durationMs: 28_000,
      outcome: 'succeeded',
      provider: 'ollama',
      model: 'llama3.2:1b',
    }),
  ];

  const bulk: RunRecord[] = [];
  const plan: Array<{ hours: number; outcome: RunOutcome; net: 'demo' | 'support'; cloud: boolean }> = [
    { hours: 3, outcome: 'succeeded', net: 'demo', cloud: false },
    { hours: 10, outcome: 'succeeded', net: 'support', cloud: true },
    { hours: 16, outcome: 'failed', net: 'support', cloud: true },
    { hours: 22, outcome: 'succeeded', net: 'demo', cloud: false },
    { hours: 38, outcome: 'cancelled', net: 'demo', cloud: false },
    { hours: 46, outcome: 'succeeded', net: 'support', cloud: true },
    { hours: 62, outcome: 'failed', net: 'demo', cloud: false },
    { hours: 70, outcome: 'succeeded', net: 'demo', cloud: false },
    { hours: 86, outcome: 'succeeded', net: 'support', cloud: true },
    { hours: 98, outcome: 'failed', net: 'support', cloud: true },
    { hours: 120, outcome: 'succeeded', net: 'demo', cloud: false },
    { hours: 150, outcome: 'cancelled', net: 'support', cloud: true },
    { hours: 170, outcome: 'succeeded', net: 'demo', cloud: false },
    { hours: 200, outcome: 'succeeded', net: 'support', cloud: true },
    { hours: 230, outcome: 'failed', net: 'demo', cloud: false },
  ];
  plan.forEach((item, index) => {
    const net = item.net === 'demo' ? demo : support;
    bulk.push(
      record({
        runId: `run-bulk-${index + 1}`,
        ...net,
        hoursAgo: item.hours,
        durationMs: 15_000 + index * 2_400,
        outcome: item.outcome,
        provider: item.cloud ? 'xai' : 'ollama',
        model: item.cloud ? 'grok-3' : 'llama3.2:1b',
        errorMessage: item.outcome === 'failed' ? 'Validierung fehlgeschlagen' : undefined,
        errorClass: item.outcome === 'failed' ? 'validation' : undefined,
        errorNodeName: item.outcome === 'failed' ? 'Assistent' : undefined,
      }),
    );
  });
  return [...specials, ...bulk];
}

let records: RunRecord[] = seed();

async function assertStore() {
  const location = await mockGetDataLocation();
  const history = location.stores.find((store) => store.id === 'history');
  if (history && (!history.ok || history.state !== 'ok')) {
    throw new ApiError(503, 'history.error.store');
  }
}

function liveRecord(): RunRecord | null {
  const session = peekMockSession();
  const store = useAppStore.getState();
  const live = store.serviceStatus === 'running' || store.serviceStatus === 'starting';
  if (!live) return null;
  const runId = store.runId ?? session.runId ?? 'run-live';
  const startedAt = session.startedAt ?? new Date().toISOString();
  const summary: RunSummary = {
    runId,
    networkId: store.activeNetworkId ?? session.activeNetworkId ?? 'net-demo',
    networkName: store.activeNetworkName ?? session.activeNetworkName ?? 'Demo-Netz',
    startedAt,
    outcome: 'running',
    models: [{ provider: 'ollama', model: 'llama3.2:1b' }],
  };
  return {
    summary,
    calls: [],
    logs: logsFor(runId, startedAt, false),
    steps: stepsFor('running'),
  };
}

function parseModel(value?: string) {
  if (!value) return null;
  const at = value.lastIndexOf('@');
  if (at <= 0) return { raw: value };
  return { model: value.slice(0, at), provider: value.slice(at + 1) };
}

function matches(summary: RunSummary, filter: RunListFilter): boolean {
  const start = Date.parse(summary.startedAt);
  const from = filter.from ? Date.parse(filter.from) : filter.since ? Date.parse(filter.since) : Number.NaN;
  const to = filter.to ? Date.parse(filter.to) : Number.NaN;
  if (!Number.isNaN(from) && start < from) return false;
  if (!Number.isNaN(to) && start > to) return false;
  if (filter.networkId && summary.networkId !== filter.networkId) return false;
  if (filter.outcome && filter.outcome.length > 0 && !filter.outcome.includes(summary.outcome)) return false;
  const wanted = parseModel(filter.model);
  if (wanted && 'model' in wanted && wanted.model) {
    const hit = summary.models.some(
      (item) => item.model === wanted.model && item.provider === wanted.provider,
    );
    if (!hit) return false;
  } else if (wanted && 'raw' in wanted && wanted.raw) {
    const raw = wanted.raw.toLowerCase();
    const hit = summary.models.some(
      (item) => item.model.toLowerCase().includes(raw) || modelKey(item.provider, item.model).toLowerCase().includes(raw),
    );
    if (!hit) return false;
  }
  const q = filter.q?.trim().toLowerCase();
  if (q) {
    const hay = [
      summary.runId,
      summary.networkName,
      summary.errorMessage ?? '',
      summary.errorClass ?? '',
      summary.errorNodeName ?? '',
    ]
      .join(' ')
      .toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

function allRecords(): RunRecord[] {
  const live = liveRecord();
  const list = live ? [live, ...records.filter((item) => item.summary.runId !== live.summary.runId)] : records;
  return [...list].sort(
    (a, b) => Date.parse(b.summary.startedAt) - Date.parse(a.summary.startedAt),
  );
}

export async function mockListRuns(filter: RunListFilter = {}): Promise<{ items: RunSummary[]; total: number }> {
  await delay();
  await assertStore();
  const matched = allRecords()
    .map((item) => item.summary)
    .filter((item) => matches(item, filter));
  const offset = filter.offset ?? 0;
  const limit = filter.limit ?? matched.length;
  return { items: matched.slice(offset, offset + limit), total: matched.length };
}

export async function mockGetRun(runId: string): Promise<RunDetail | null> {
  await delay();
  await assertStore();
  const found = allRecords().find((item) => item.summary.runId === runId);
  if (!found) return null;
  return {
    ...found.summary,
    steps: found.steps,
    calls: found.calls,
    graphSnapshot: found.graphSnapshot,
    chat: found.chat,
  };
}

export async function mockListRunLogs(runId: string, logFilter?: LogFilter): Promise<LogEvent[]> {
  await delay();
  await assertStore();
  const found = allRecords().find((item) => item.summary.runId === runId);
  if (!found) return [];
  return found.logs
    .filter((event) => {
      if (logFilter?.nodeId && event.nodeId !== logFilter.nodeId) return false;
      if (logFilter?.level && event.level !== logFilter.level) return false;
      if (logFilter?.q) {
        const hay = `${event.message} ${event.nodeName ?? ''}`.toLowerCase();
        if (!hay.includes(logFilter.q.toLowerCase())) return false;
      }
      return true;
    })
    .map((event) => ({ ...event, ...maskLog(event) }));
}

export async function mockListCalls(filter: RunListFilter = {}): Promise<LlmCall[]> {
  await delay();
  await assertStore();
  const matched = allRecords().filter((item) => matches(item.summary, filter));
  const wanted = parseModel(filter.model);
  return matched.flatMap((item) =>
    item.calls.filter((entry) => {
      if (wanted && 'model' in wanted && wanted.model) {
        return entry.model === wanted.model && entry.provider === wanted.provider;
      }
      return true;
    }),
  );
}

export async function mockDeleteRuns(ids: string[]): Promise<void> {
  await delay();
  await assertStore();
  const live = liveRecord();
  if (live && ids.includes(live.summary.runId)) {
    throw new ApiError(409, 'history.error.runningDelete');
  }
  const blocked = records.filter((item) => ids.includes(item.summary.runId) && item.summary.outcome === 'running');
  if (blocked.length) throw new ApiError(409, 'history.error.runningDelete');
  records = records.filter((item) => !ids.includes(item.summary.runId));
}

export async function mockDeleteRunsOlderThan(days: number): Promise<{ deleted: number }> {
  await delay();
  await assertStore();
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  const before = records.length;
  records = records.filter((item) => {
    if (item.summary.outcome === 'running') return true;
    return Date.parse(item.summary.startedAt) >= cutoff;
  });
  return { deleted: before - records.length };
}
