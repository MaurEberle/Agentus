import type {
  ChatInputConfig,
  ChatMessage,
  LogEvent,
  LogLevel,
  NodeRuntime,
  RunGraph,
  RunSnapshot,
} from '@/modules/monitoring/model/types';
import { logLevelRank } from '@/modules/monitoring/model/format';

export function hasChatInput(graph: RunGraph | undefined | null): boolean {
  return Boolean(graph?.nodes.some((node) => node.type === 'chat_input'));
}

export function chatInputConfig(graph: RunGraph | undefined | null): ChatInputConfig | null {
  const node = graph?.nodes.find((item) => item.type === 'chat_input');
  if (!node) return null;
  const data = node.data;
  return {
    displayName: typeof data.displayName === 'string' ? data.displayName : undefined,
    placeholder: typeof data.placeholder === 'string' ? data.placeholder : undefined,
    startMessage: typeof data.startMessage === 'string' ? data.startMessage : undefined,
    requireInput: Boolean(data.requireInput),
  };
}

export function nodeDisplayName(node: { id: string; type: string; data: { displayName?: string } }): string {
  const name = node.data.displayName;
  return typeof name === 'string' && name.trim() ? name.trim() : node.type;
}

export function mergeRunSnapshot(
  prev: RunSnapshot | null,
  patch: Partial<RunSnapshot>,
): RunSnapshot | null {
  if (!prev && !patch.runId) return null;
  if (!prev) {
    if (!patch.runId || !patch.networkId || !patch.networkName || !patch.startedAt || !patch.graph) {
      return null;
    }
    return {
      runId: patch.runId,
      networkId: patch.networkId,
      networkName: patch.networkName,
      startedAt: patch.startedAt,
      endedAt: patch.endedAt,
      outcome: patch.outcome,
      archived: patch.archived,
      serviceStatus: patch.serviceStatus ?? 'running',
      errorMessage: patch.errorMessage,
      graph: patch.graph,
      nodesRuntime: patch.nodesRuntime ?? {},
      activity: patch.activity ?? { currentNodeIds: [] },
      chat: patch.chat,
    };
  }
  return {
    ...prev,
    ...patch,
    graph: patch.graph ?? prev.graph,
    nodesRuntime: patch.nodesRuntime
      ? { ...prev.nodesRuntime, ...patch.nodesRuntime }
      : prev.nodesRuntime,
    activity: patch.activity ?? prev.activity,
    chat: patch.chat
      ? {
          messages: patch.chat.messages ?? prev.chat?.messages ?? [],
          generating: patch.chat.generating ?? prev.chat?.generating,
        }
      : prev.chat,
  };
}

export function runTokenStats(run: RunSnapshot): {
  out: number;
  in?: number;
  perSecond?: number;
} {
  const fromActivity = run.activity.tokens;
  if (fromActivity && (fromActivity.out !== undefined || fromActivity.perSecond !== undefined)) {
    return {
      out: fromActivity.out ?? 0,
      in: fromActivity.in,
      perSecond: fromActivity.perSecond,
    };
  }
  let out = 0;
  let inn = 0;
  let rate: number | undefined;
  for (const node of Object.values(run.nodesRuntime)) {
    if (!node.tokens) continue;
    if (node.tokens.out) out += node.tokens.out;
    if (node.tokens.in) inn += node.tokens.in;
    if (node.tokens.perSecond !== undefined && (node.status === 'running' || node.status === 'waiting')) {
      rate = node.tokens.perSecond;
    }
  }
  return { out, in: inn || undefined, perSecond: rate };
}

export function activeLlms(
  graph: RunGraph,
  runtime: Record<string, NodeRuntime>,
): Array<{ model: string; provider: NonNullable<NodeRuntime['llm']>['provider']; nodeId: string }> {
  const list: Array<{
    model: string;
    provider: NonNullable<NodeRuntime['llm']>['provider'];
    nodeId: string;
  }> = [];
  for (const node of graph.nodes) {
    if (node.type !== 'llm') continue;
    const rt = runtime[node.id];
    if (!rt || (rt.status !== 'running' && rt.status !== 'waiting')) continue;
    const provider = (rt.llm?.provider ||
      (typeof node.data.provider === 'string' && node.data.provider) ||
      'ollama') as NonNullable<NodeRuntime['llm']>['provider'];
    const model =
      rt.llm?.model || (typeof node.data.model === 'string' ? node.data.model : '') || '';
    list.push({ nodeId: node.id, model, provider });
  }
  return list;
}

export function activeNonLlm(
  graph: RunGraph,
  runtime: Record<string, NodeRuntime>,
): Array<{ id: string; name: string; status: NodeRuntime['status'] }> {
  const rows: Array<{ id: string; name: string; status: NodeRuntime['status'] }> = [];
  for (const node of graph.nodes) {
    if (node.type === 'llm') continue;
    const status = runtime[node.id]?.status;
    if (status === 'running' || status === 'waiting') {
      rows.push({ id: node.id, name: nodeDisplayName(node), status });
    }
  }
  return rows;
}

export function upsertChat(messages: ChatMessage[], next: ChatMessage): ChatMessage[] {
  const index = messages.findIndex((item) => item.id === next.id);
  if (index === -1) return [...messages, next];
  const copy = messages.slice();
  copy[index] = { ...copy[index], ...next };
  return copy;
}

export function applyChatDelta(
  messages: ChatMessage[],
  runId: string,
  id: string,
  delta: string,
): ChatMessage[] {
  const index = messages.findIndex((item) => item.id === id);
  if (index === -1) {
    return [
      ...messages,
      {
        id,
        runId,
        role: 'assistant',
        content: delta,
        createdAt: new Date().toISOString(),
      },
    ];
  }
  const copy = messages.slice();
  const current = copy[index];
  if (!current) return messages;
  copy[index] = { ...current, content: `${current.content}${delta}` };
  return copy;
}

export function logHasExtra(event: LogEvent): boolean {
  if (event.stack && event.stack.length > 0) return true;
  if (event.payload === undefined || event.payload === null) return false;
  if (typeof event.payload === 'string') return event.payload.length > 0;
  if (Array.isArray(event.payload)) return event.payload.length > 0;
  if (typeof event.payload === 'object') return Object.keys(event.payload).length > 0;
  return true;
}

export function filterLogs(
  logs: LogEvent[],
  opts: {
    levelMin: LogLevel;
    query: string;
    nodeId: string | null;
    errorsOnly: boolean;
  },
): LogEvent[] {
  const q = opts.query.trim().toLowerCase();
  const min = logLevelRank(opts.levelMin);
  return logs.filter((event) => {
    if (logLevelRank(event.level) < min) return false;
    if (opts.errorsOnly && event.level !== 'error' && event.level !== 'warn') return false;
    if (opts.nodeId && event.nodeId !== opts.nodeId) return false;
    if (q) {
      const hay = `${event.message} ${event.nodeName ?? ''} ${event.nodeId ?? ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export function parseMockScenario(value: string | null | undefined): import('./types').MockScenario | null {
  if (!value) return null;
  const allowed = [
    'stopped',
    'disconnected',
    'starting',
    'stopping',
    'running',
    'nochat',
    'cloud',
    'error',
    'wait',
  ] as const;
  return (allowed as readonly string[]).includes(value)
    ? (value as (typeof allowed)[number])
    : null;
}
