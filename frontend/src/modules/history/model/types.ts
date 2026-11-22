export type RunOutcome = 'running' | 'succeeded' | 'failed' | 'cancelled' | 'timeout';
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';
export type LlmProvider = 'ollama' | 'xai' | 'openai' | 'anthropic' | 'gemini' | 'openai_compat';
export type ErrorClass =
  | 'timeout'
  | 'tool_error'
  | 'llm_error'
  | 'validation'
  | 'service'
  | 'unknown'
  | 'orchestrator'
  | 'budget';
export type RangeKey = 'today' | '7d' | '30d' | 'custom';
export type HistoryTab = 'history' | 'model' | 'network';
export type DetailTab = 'log' | 'steps' | 'chat';

export const LOG_LEVELS: LogLevel[] = ['debug', 'info', 'warn', 'error'];
export const RUN_OUTCOMES: RunOutcome[] = ['running', 'succeeded', 'failed', 'cancelled', 'timeout'];
export const PAGE_SIZE = 50;
export const STATS_LIMIT = 500;
export const P95_MIN = 20;

export type LlmCall = {
  id: string;
  nodeId: string;
  nodeName?: string;
  provider: LlmProvider;
  model: string;
  ok: boolean;
  durationMs?: number;
  tokensIn?: number;
  tokensOut?: number;
  errorMessage?: string;
  runId?: string;
};

export type RunStep = {
  nodeId: string;
  nodeName?: string;
  role?: string;
  type?: string;
  status: 'idle' | 'waiting' | 'running' | 'done' | 'error';
  waitReason?: 'none' | 'llm' | 'tool' | 'human' | 'index' | 'knowledge' | 'thinking';
  errorMessage?: string;
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

export type GraphSnapshot = {
  nodes: Array<{
    id: string;
    type: string;
    position: { x: number; y: number };
    data: { displayName?: string; role?: string; [k: string]: unknown };
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    sourceHandle?: string;
    targetHandle?: string;
  }>;
};

export type RunSummary = {
  runId: string;
  networkId: string;
  networkName: string;
  startedAt: string;
  endedAt?: string;
  outcome: RunOutcome;
  errorMessage?: string;
  errorClass?: ErrorClass;
  errorNodeId?: string;
  errorNodeName?: string;
  models: Array<{ provider: LlmProvider; model: string }>;
};

export type RunChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  messageKey?: string;
  messageParams?: Record<string, string | number>;
};

export type RunDetail = RunSummary & {
  steps?: RunStep[];
  calls: LlmCall[];
  graphSnapshot?: GraphSnapshot;
  chat?: RunChatMessage[];
};

export type LogFilter = {
  level?: LogLevel;
  q?: string;
  nodeId?: string;
};

export type RunListFilter = {
  from?: string;
  to?: string;
  since?: string;
  networkId?: string;
  outcome?: RunOutcome[];
  model?: string;
  q?: string;
  /** Exact error key of failed runs (a tile of the error map). */
  error?: string;
  limit?: number;
  offset?: number;
};

export type HistoryFilter = {
  range: RangeKey;
  from: string;
  to: string;
  networkId: string;
  outcomes: RunOutcome[];
  model: string;
  q: string;
  /** Exact error key from the error map; '' for none. Only in the address, not remembered. */
  error: string;
  tab: HistoryTab;
  page: number;
};

export type HistoryKpis = {
  total: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  timeout: number;
  medianMs: number | null;
  p95Ms: number | null;
};

export type ChartBucket = {
  key: string;
  label: string;
  /** Short text under the column: "23. Okt.", or "14:00" for hours. */
  axisLabel: string;
  unit: 'day' | 'hour';
  succeeded: number;
  failed: number;
  cancelled: number;
  timeout: number;
};

/** One error key of failed runs in the error map; its area is its count. */
export type ErrorTile = {
  id: string;
  /** Error key to filter by ("none" for runs without one); null for the "more" tile. */
  error: string | null;
  /** The class most of these runs had. */
  errorClass: ErrorClass;
  count: number;
  /** Nodes where it happened, most often first. */
  nodes: { name: string; count: number }[];
  lastAt: string;
  /** The "more" tile: how many smaller error keys it holds. */
  more?: number;
};

export type ModelAggRow = {
  provider: LlmProvider;
  model: string;
  calls: number;
  ok: number;
  error: number;
  errorRate: number;
  medianMs: number | null;
  tokensIn: number | null;
  tokensOut: number | null;
};

export type NetworkAggRow = {
  networkId: string;
  networkName: string;
  runs: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  timeout: number;
  medianMs: number | null;
  topErrorNode?: string;
};
