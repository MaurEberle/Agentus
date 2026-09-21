import type { ServiceStatus } from '@/store/session';

export type NodeRuntimeStatus = 'idle' | 'waiting' | 'running' | 'done' | 'error';
export type WaitReason = 'none' | 'llm' | 'tool' | 'human' | 'index';
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';
export type LlmProvider = 'ollama' | 'xai' | 'openai' | 'anthropic' | 'gemini' | 'openai_compat';

export const LOG_LEVELS: LogLevel[] = ['debug', 'info', 'warn', 'error'];
export const LOG_BUFFER_SIZE = 2000;

export type ResourceGpu = {
  index: number;
  name?: string;
  utilPercent: number;
  vramUsedBytes: number;
  vramTotalBytes: number;
};

export type ResourceSnapshot = {
  ts: string;
  cpuPercent: number;
  cpuPerCore?: number[];
  ramUsedBytes: number;
  ramTotalBytes: number;
  gpus?: ResourceGpu[];
  scope: 'host';
};

export type NodeRuntime = {
  status: NodeRuntimeStatus;
  role?: string;
  waitReason?: WaitReason;
  lastMessage?: string;
  error?: string;
  llm?: { model: string; provider: LlmProvider; nodeId: string };
  tokens?: {
    in?: number;
    out?: number;
    perSecond?: number;
    contextUsed?: number;
    contextMax?: number;
  };
};

export type RunGraphNode = {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: { displayName?: string; role?: string; [k: string]: unknown };
};

export type RunGraphEdge = {
  id: string;
  source: string;
  sourceHandle?: string;
  target: string;
  targetHandle?: string;
};

export type RunGraph = {
  nodes: RunGraphNode[];
  edges: RunGraphEdge[];
};

export type ChatMessage = {
  id: string;
  runId: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
};

export type RunSnapshot = {
  runId: string;
  networkId: string;
  networkName: string;
  startedAt: string;
  endedAt?: string;
  outcome?: 'running' | 'succeeded' | 'failed' | 'cancelled' | 'timeout';
  archived?: boolean;
  serviceStatus: ServiceStatus;
  errorMessage?: string;
  graph: RunGraph;
  nodesRuntime: Record<string, NodeRuntime>;
  activity: {
    currentNodeIds: string[];
    dag?: { completed: number; total: number; pendingNodeIds: string[] };
    stepError?: { nodeId: string; message: string };
    tokens?: {
      in?: number;
      out?: number;
      perSecond?: number;
    };
  };
  chat?: { messages: ChatMessage[]; generating?: boolean };
};

export type LogEvent = {
  id: string;
  ts: string;
  level: LogLevel;
  runId: string;
  nodeId?: string;
  nodeName?: string;
  message: string;
  payload?: unknown;
  stack?: string;
};

export type MonitoringEvent =
  | { type: 'service'; serviceStatus: ServiceStatus; errorMessage?: string }
  | { type: 'run'; run: Partial<RunSnapshot> }
  | { type: 'resources'; resources: ResourceSnapshot }
  | { type: 'log'; log: LogEvent }
  | { type: 'chat'; runId: string; message?: ChatMessage; id?: string; delta?: string }
  | { type: 'adapterError'; messageKey: string };

export type MonitoringHandle = {
  subscribe(cb: (evt: MonitoringEvent) => void): () => void;
  getSnapshot(): {
    serviceStatus: ServiceStatus;
    run: RunSnapshot | null;
    resources: ResourceSnapshot | null;
  };
  sendChat?(text: string): void;
  abortChat?(): void;
  setMockScenario?(id: MockScenario): void;
};

export const MOCK_SCENARIOS = [
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

export type MockScenario = (typeof MOCK_SCENARIOS)[number];

export type ChatInputConfig = {
  displayName?: string;
  placeholder?: string;
  startMessage?: string;
  requireInput?: boolean;
};
