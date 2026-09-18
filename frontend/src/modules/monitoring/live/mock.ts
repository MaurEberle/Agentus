import i18n from '@/i18n';
import { mockApplyService, peekMockSession } from '@/api/mocks';
import { useAppStore } from '@/store';
import type { ServiceStatus } from '@/store/session';
import { queryClient } from '@/api/client';
import { maskText } from '@/modules/monitoring/model/mask';
import type {
  ChatMessage,
  LogEvent,
  LogLevel,
  MockScenario,
  MonitoringEvent,
  MonitoringHandle,
  NodeRuntime,
  ResourceSnapshot,
  RunGraph,
  RunSnapshot,
} from '@/modules/monitoring/model/types';

type Flavor = 'chat' | 'nochat' | 'cloud' | 'wait';

type Engine = {
  serviceStatus: ServiceStatus;
  errorMessage?: string;
  run: RunSnapshot | null;
  resources: ResourceSnapshot | null;
  flavor: Flavor;
  tick: number;
  logSeq: number;
  chatSeq: number;
  generatingId: string | null;
  generateTimer: number | null;
};

const listeners = new Set<(evt: MonitoringEvent) => void>();
let intervalId: number | null = null;
const engine: Engine = createEngine();

function createEngine(): Engine {
  return {
    serviceStatus: 'stopped',
    run: null,
    resources: null,
    flavor: 'chat',
    tick: 0,
    logSeq: 0,
    chatSeq: 0,
    generatingId: null,
    generateTimer: null,
  };
}

function emit(evt: MonitoringEvent) {
  for (const listener of listeners) listener(evt);
}

function nowIso() {
  return new Date().toISOString();
}

function jitter(base: number, spread: number, min = 0, max = 100) {
  return Math.min(max, Math.max(min, base + (Math.random() * 2 - 1) * spread));
}

function t(key: string, values?: Record<string, string>) {
  return i18n.t(key, values);
}

function chatGraph(opts?: { requireInput?: boolean; startMessage?: string; cloud?: boolean }): RunGraph {
  const llmData = opts?.cloud
    ? { displayName: 'Cloud', provider: 'xai', model: 'grok-3' }
    : { displayName: 'Lokal', provider: 'ollama', model: 'llama3.2:1b' };
  return {
    nodes: [
      {
        id: 'chat-1',
        type: 'chat_input',
        position: { x: 0, y: 160 },
        data: {
          displayName: 'Eingabe',
          placeholder: 'Frage…',
          requireInput: Boolean(opts?.requireInput),
          startMessage: opts?.startMessage,
        },
      },
      { id: 'llm-1', type: 'llm', position: { x: 0, y: 0 }, data: llmData },
      { id: 'agent-1', type: 'agent', position: { x: 280, y: 120 }, data: { displayName: 'Assistent' } },
      { id: 'tool-1', type: 'tool', position: { x: 280, y: 280 }, data: { displayName: 'Suche' } },
      { id: 'end-1', type: 'end', position: { x: 560, y: 160 }, data: { displayName: 'Ende' } },
    ],
    edges: [
      { id: 'e1', source: 'chat-1', sourceHandle: 'message', target: 'agent-1', targetHandle: 'message' },
      { id: 'e2', source: 'llm-1', sourceHandle: 'llm', target: 'agent-1', targetHandle: 'llm' },
      { id: 'e3', source: 'tool-1', sourceHandle: 'tool', target: 'agent-1', targetHandle: 'tool' },
      { id: 'e4', source: 'agent-1', sourceHandle: 'message', target: 'end-1', targetHandle: 'message' },
    ],
  };
}

function noChatGraph(): RunGraph {
  return {
    nodes: [
      {
        id: 'llm-1',
        type: 'llm',
        position: { x: 0, y: 40 },
        data: { displayName: 'Lokal', provider: 'ollama', model: 'llama3.2:1b' },
      },
      { id: 'agent-1', type: 'agent', position: { x: 280, y: 80 }, data: { displayName: 'Ops' } },
      { id: 'tool-1', type: 'tool', position: { x: 280, y: 240 }, data: { displayName: 'HTTP' } },
      { id: 'end-1', type: 'end', position: { x: 560, y: 120 }, data: { displayName: 'Ende' } },
    ],
    edges: [
      { id: 'e1', source: 'llm-1', sourceHandle: 'llm', target: 'agent-1', targetHandle: 'llm' },
      { id: 'e2', source: 'tool-1', sourceHandle: 'tool', target: 'agent-1', targetHandle: 'tool' },
      { id: 'e3', source: 'agent-1', sourceHandle: 'message', target: 'end-1', targetHandle: 'message' },
    ],
  };
}

function llmRuntime(flavor: Flavor, status: NodeRuntime['status'] = 'running'): NodeRuntime {
  const cloud = flavor === 'cloud';
  return {
    status,
    role: 'llm',
    waitReason: status === 'waiting' ? 'none' : 'none',
    llm: {
      nodeId: 'llm-1',
      provider: cloud ? 'xai' : 'ollama',
      model: cloud ? 'grok-3' : 'llama3.2:1b',
    },
    tokens: { in: 420, out: 88, perSecond: 18, contextUsed: 1800, contextMax: 8192 },
    lastMessage: t('monitoring.mock.lastLlm'),
  };
}

function runningRuntime(flavor: Flavor): Record<string, NodeRuntime> {
  if (flavor === 'wait') {
    return {
      'chat-1': { status: 'waiting', role: 'chat_input', waitReason: 'human', lastMessage: t('monitoring.mock.waitInput') },
      'llm-1': { status: 'idle', role: 'llm', llm: llmRuntime(flavor, 'idle').llm },
      'agent-1': { status: 'waiting', role: 'agent', waitReason: 'human' },
      'tool-1': { status: 'idle', role: 'tool' },
      'end-1': { status: 'idle', role: 'end' },
    };
  }
  const llm = llmRuntime(flavor, 'running');
  return {
    ...(flavor === 'nochat' ? {} : { 'chat-1': { status: 'done', role: 'chat_input', waitReason: 'none' } }),
    'llm-1': llm,
    'agent-1': {
      status: 'running',
      role: 'agent',
      waitReason: 'llm',
      lastMessage: t('monitoring.mock.lastAgent'),
    },
    'tool-1': { status: 'waiting', role: 'tool', waitReason: 'tool', lastMessage: t('monitoring.mock.lastTool') },
    'end-1': { status: 'idle', role: 'end' },
  };
}

function hostResources(cloud: boolean): ResourceSnapshot {
  const cores = [jitter(22, 10), jitter(18, 8), jitter(30, 12), jitter(14, 8)];
  const cpuPercent = cores.reduce((sum, n) => sum + n, 0) / cores.length;
  return {
    ts: nowIso(),
    cpuPercent,
    cpuPerCore: cores,
    ramUsedBytes: 18.4 * 1024 ** 3,
    ramTotalBytes: 32 * 1024 ** 3,
    gpus: cloud
      ? []
      : [
          {
            index: 0,
            name: 'NVIDIA GeForce RTX 4070',
            utilPercent: jitter(48, 16),
            vramUsedBytes: 6.1 * 1024 ** 3,
            vramTotalBytes: 12 * 1024 ** 3,
          },
        ],
    scope: 'host',
  };
}

function sessionMeta() {
  const session = peekMockSession();
  return {
    networkId: session.activeNetworkId ?? 'net-demo',
    networkName: session.activeNetworkName ?? 'Demo-Netz',
    runId: session.runId ?? `run-${crypto.randomUUID().slice(0, 8)}`,
    startedAt: session.startedAt ?? nowIso(),
  };
}

function seedUser(runId: string): ChatMessage {
  return {
    id: 'msg-user-1',
    runId,
    role: 'user',
    content: t('monitoring.mock.userLine'),
    createdAt: nowIso(),
  };
}

function buildRun(status: ServiceStatus, flavor: Flavor): RunSnapshot {
  const meta = sessionMeta();
  const graph = flavor === 'nochat' ? noChatGraph() : chatGraph({
    requireInput: flavor === 'wait',
    cloud: flavor === 'cloud',
  });
  const wait = flavor === 'wait';
  const messages = flavor === 'nochat' || wait ? [] : [seedUser(meta.runId)];
  const stepError =
    status === 'error'
      ? { nodeId: 'agent-1', message: t('monitoring.mock.stepError') }
      : undefined;
  const runtime = runningRuntime(flavor);
  if (status === 'error') {
    runtime['agent-1'] = {
      status: 'error',
      role: 'agent',
      waitReason: 'none',
      error: t('monitoring.mock.stepError'),
    };
    runtime['llm-1'] = { ...runtime['llm-1']!, status: 'idle' };
  }
  if (status === 'starting') {
    for (const key of Object.keys(runtime)) {
      runtime[key] = { ...runtime[key]!, status: 'idle', waitReason: 'none' };
    }
  }
  return {
    runId: meta.runId,
    networkId: meta.networkId,
    networkName: meta.networkName,
    startedAt: meta.startedAt,
    serviceStatus: status,
    errorMessage: status === 'error' ? t('monitoring.mock.serviceError') : undefined,
    graph,
    nodesRuntime: runtime,
    activity: {
      currentNodeIds: wait ? ['chat-1'] : status === 'error' ? ['agent-1'] : ['llm-1', 'agent-1'],
      dag: flavor === 'nochat' ? { completed: 1, total: 4, pendingNodeIds: ['agent-1', 'tool-1', 'end-1'] } : undefined,
      stepError,
    },
    chat:
      flavor === 'nochat'
        ? undefined
        : { messages, generating: false },
  };
}

function pushLog(partial: Omit<LogEvent, 'id' | 'ts' | 'runId'> & { runId?: string }) {
  const runId = partial.runId ?? engine.run?.runId ?? 'run-unknown';
  engine.logSeq += 1;
  const log: LogEvent = {
    id: `log-${engine.logSeq}`,
    ts: nowIso(),
    runId,
    level: partial.level,
    nodeId: partial.nodeId,
    nodeName: partial.nodeName,
    message: maskText(partial.message),
    payload: partial.payload,
    stack: partial.stack,
  };
  emit({ type: 'log', log });
}

function seedLogs(run: RunSnapshot) {
  const levels: Array<[LogLevel, string, string, string]> = [
    ['info', 'chat-1', 'Eingabe', t('monitoring.mock.log.start')],
    ['debug', 'llm-1', 'Lokal', t('monitoring.mock.log.debug')],
    ['info', 'agent-1', 'Assistent', t('monitoring.mock.log.agent')],
    ['warn', 'tool-1', 'Suche', t('monitoring.mock.log.warn')],
  ];
  for (const [level, nodeId, nodeName, message] of levels) {
    pushLog({ level, nodeId, nodeName, message, runId: run.runId });
  }
  pushLog({
    level: 'info',
    nodeId: 'llm-1',
    nodeName: 'Lokal',
    message: t('monitoring.mock.log.secret'),
    payload: { apiKey: 'sk-live-demo-should-mask', model: 'llama3.2:1b' },
    runId: run.runId,
  });
  if (run.serviceStatus === 'error') {
    pushLog({
      level: 'error',
      nodeId: 'agent-1',
      nodeName: 'Assistent',
      message: t('monitoring.mock.stepError'),
      stack: 'ToolError: timeout\n    at executor (run.py:41)',
      payload: { waitReason: 'tool' },
      runId: run.runId,
    });
  }
}

function emitService() {
  emit({
    type: 'service',
    serviceStatus: engine.serviceStatus,
    errorMessage: engine.errorMessage,
  });
}

function emitRun() {
  if (engine.run) emit({ type: 'run', run: engine.run });
}

function emitResources() {
  if (engine.resources) emit({ type: 'resources', resources: engine.resources });
}

function applyStatus(status: ServiceStatus, flavor = engine.flavor) {
  const prev = engine.serviceStatus;
  engine.flavor = flavor;
  engine.serviceStatus = status;
  engine.errorMessage = status === 'error' ? t('monitoring.mock.serviceError') : undefined;

  if (status === 'stopped') {
    engine.run = null;
    engine.resources = null;
  } else if (status === 'disconnected') {
    engine.resources = engine.resources ?? hostResources(flavor === 'cloud');
    if (!engine.run) engine.run = buildRun('running', flavor);
    engine.run = { ...engine.run, serviceStatus: 'disconnected' };
  } else {
    engine.run = buildRun(status, flavor);
    engine.resources = hostResources(flavor === 'cloud');
  }

  if (status !== prev || !engine.run) {
    emitService();
    emitRun();
    emitResources();
    if (engine.run && (status === 'running' || status === 'error' || status === 'starting')) {
      seedLogs(engine.run);
    }
  } else {
    emitService();
    emitRun();
    emitResources();
  }
}

function flavorOf(scenario: MockScenario): Flavor {
  if (scenario === 'nochat') return 'nochat';
  if (scenario === 'cloud') return 'cloud';
  if (scenario === 'wait') return 'wait';
  if (scenario === 'running') return 'chat';
  return engine.flavor;
}

function statusOf(scenario: MockScenario): ServiceStatus {
  if (scenario === 'running' || scenario === 'nochat' || scenario === 'cloud' || scenario === 'wait') {
    return 'running';
  }
  return scenario;
}

function syncAppSession(status: ServiceStatus) {
  const keep = status === 'disconnected' || status === 'error' || status === 'starting' || status === 'stopping';
  const session = mockApplyService(status, {
    runId: engine.run?.runId,
    keepRun: keep,
  });
  const store = useAppStore.getState();
  store.setServiceStatus(session.serviceStatus);
  store.setRunId(session.runId ?? null);
  void queryClient.invalidateQueries({ queryKey: ['session'] });
}

function followSession() {
  const session = peekMockSession();
  if (session.serviceStatus === engine.serviceStatus) return;
  applyStatus(session.serviceStatus, engine.flavor);
}

function tick() {
  followSession();
  if (engine.serviceStatus !== 'running' && engine.serviceStatus !== 'error') return;
  if (!engine.run) return;
  engine.tick += 1;
  engine.resources = hostResources(engine.flavor === 'cloud');
  emitResources();

  const runtime = { ...engine.run.nodesRuntime };
  const llm = runtime['llm-1'];
  if (llm?.tokens && llm.status === 'running') {
    runtime['llm-1'] = {
      ...llm,
      tokens: {
        ...llm.tokens,
        out: (llm.tokens.out ?? 0) + Math.round(jitter(12, 6, 4, 24)),
        perSecond: jitter(16, 8, 4, 36),
      },
    };
  }
  engine.run = { ...engine.run, nodesRuntime: runtime };
  emit({ type: 'run', run: { nodesRuntime: runtime, activity: engine.run.activity } });

  if (engine.tick % 2 === 0) {
    const nodes = [
      { id: 'llm-1', name: engine.flavor === 'cloud' ? 'Cloud' : 'Lokal' },
      { id: 'agent-1', name: 'Assistent' },
      { id: 'tool-1', name: engine.flavor === 'nochat' ? 'HTTP' : 'Suche' },
    ];
    const pick = nodes[engine.tick % nodes.length]!;
    const level: LogLevel = engine.tick % 7 === 0 ? 'warn' : engine.tick % 11 === 0 ? 'debug' : 'info';
    pushLog({
      level,
      nodeId: pick.id,
      nodeName: pick.name,
      message: t('monitoring.mock.log.tick', { node: pick.name }),
    });
  }
}

function startTicks() {
  if (intervalId !== null) return;
  intervalId = window.setInterval(tick, 1000);
}

function stopTicks() {
  if (intervalId === null) return;
  window.clearInterval(intervalId);
  intervalId = null;
}

function stopGenerate() {
  if (engine.generateTimer !== null) {
    window.clearInterval(engine.generateTimer);
    engine.generateTimer = null;
  }
  engine.generatingId = null;
}

function sendChat(text: string) {
  if (engine.serviceStatus !== 'running' || !engine.run) return;
  if (engine.flavor === 'nochat') return;
  const runId = engine.run.runId;
  const user: ChatMessage = {
    id: `msg-user-${++engine.chatSeq}`,
    runId,
    role: 'user',
    content: maskText(text),
    createdAt: nowIso(),
  };
  emit({ type: 'chat', runId, message: user });
  pushLog({
    level: 'info',
    nodeId: 'chat-1',
    nodeName: 'Eingabe',
    message: t('monitoring.mock.log.user'),
  });

  stopGenerate();
  const assistantId = `msg-asst-${engine.chatSeq}`;
  engine.generatingId = assistantId;
  const reply = t('monitoring.mock.chatReply');
  const chunks = reply.split(/(\s+)/).filter((part) => part.length > 0);
  let index = 0;
  engine.generateTimer = window.setInterval(() => {
    if (index < chunks.length) {
      const chunk = chunks[index] ?? '';
      index += 1;
      emit({ type: 'chat', runId, id: assistantId, delta: chunk });
      return;
    }
    stopGenerate();
    emit({
      type: 'chat',
      runId,
      message: {
        id: assistantId,
        runId,
        role: 'assistant',
        content: reply,
        createdAt: nowIso(),
      },
    });
    pushLog({
      level: 'info',
      nodeId: 'end-1',
      nodeName: 'Ende',
      message: t('monitoring.mock.log.assistant'),
    });
  }, 40);
}

function abortChat() {
  if (!engine.run || !engine.generatingId) {
    stopGenerate();
    return;
  }
  stopGenerate();
  emit({
    type: 'run',
    run: { chat: { messages: engine.run.chat?.messages ?? [], generating: false } },
  });
}

function setMockScenario(id: MockScenario) {
  const status = statusOf(id);
  const flavor = flavorOf(id);
  applyStatus(status, flavor);
  syncAppSession(status);
}

export function createMockHandle(): MonitoringHandle {
  return {
    subscribe(cb) {
      listeners.add(cb);
      if (listeners.size === 1) {
        const before = engine.serviceStatus;
        followSession();
        const live =
          engine.serviceStatus === 'running' ||
          engine.serviceStatus === 'error' ||
          engine.serviceStatus === 'starting';
        if (engine.run && live && engine.serviceStatus === before) {
          seedLogs(engine.run);
        }
        startTicks();
      }
      return () => {
        listeners.delete(cb);
        if (listeners.size === 0) {
          stopTicks();
          stopGenerate();
        }
      };
    },
    getSnapshot() {
      const session = peekMockSession();
      if (session.serviceStatus !== engine.serviceStatus && listeners.size === 0) {
        engine.serviceStatus = session.serviceStatus;
        if (session.serviceStatus === 'running') {
          engine.run = buildRun('running', engine.flavor);
          engine.resources = hostResources(engine.flavor === 'cloud');
        } else if (session.serviceStatus === 'stopped') {
          engine.run = null;
          engine.resources = null;
        }
      }
      return {
        serviceStatus: engine.serviceStatus,
        run: engine.run,
        resources: engine.resources,
      };
    },
    sendChat,
    abortChat,
    setMockScenario,
  };
}
