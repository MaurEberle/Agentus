export type RunColumnId = 'runId' | 'network' | 'started' | 'duration' | 'outcome' | 'models' | 'error';

const STORAGE_KEY = 'agentus.history.runColumns';

export const RUN_COLUMN_IDS: RunColumnId[] = [
  'runId',
  'network',
  'started',
  'duration',
  'outcome',
  'models',
  'error',
];

/** Fehler steht am Ende. Netz startet bei 150 px und lässt sich weiter aufziehen. */
export const DEFAULT_RUN_ORDER: RunColumnId[] = [
  'runId',
  'network',
  'started',
  'duration',
  'outcome',
  'models',
  'error',
];

const DEFAULT_WIDTH: Record<RunColumnId, number> = {
  runId: 136,
  network: 150,
  started: 168,
  duration: 80,
  outcome: 112,
  models: 180,
  error: 240,
};

const MIN_WIDTH: Record<RunColumnId, number> = {
  runId: 112,
  network: 72,
  started: 96,
  duration: 64,
  outcome: 88,
  models: 96,
  error: 72,
};

const MAX_WIDTH = 720;

export type RunColumnLayout = {
  order: RunColumnId[];
  widths: Record<RunColumnId, number>;
};

function isColumnId(value: string): value is RunColumnId {
  return (RUN_COLUMN_IDS as string[]).includes(value);
}

export function clampColumnWidth(id: RunColumnId, value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_WIDTH[id];
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH[id], Math.round(value)));
}

export function normalizeRunColumns(raw: unknown): RunColumnLayout {
  const record = raw && typeof raw === 'object' ? (raw as { order?: unknown; widths?: unknown }) : {};
  const order: RunColumnId[] = [];
  if (Array.isArray(record.order)) {
    for (const item of record.order) {
      if (typeof item === 'string' && isColumnId(item) && !order.includes(item)) order.push(item);
    }
  }
  for (const id of DEFAULT_RUN_ORDER) {
    if (!order.includes(id)) order.push(id);
  }
  const widths = { ...DEFAULT_WIDTH };
  if (record.widths && typeof record.widths === 'object') {
    for (const id of RUN_COLUMN_IDS) {
      const value = (record.widths as Record<string, unknown>)[id];
      if (typeof value === 'number') widths[id] = clampColumnWidth(id, value);
    }
  }
  return { order, widths };
}

export function loadRunColumns(): RunColumnLayout {
  if (typeof window === 'undefined') return normalizeRunColumns(null);
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return normalizeRunColumns(null);
    return normalizeRunColumns(JSON.parse(raw) as unknown);
  } catch {
    return normalizeRunColumns(null);
  }
}

export function saveRunColumns(layout: RunColumnLayout): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeRunColumns(layout)));
  } catch {
    /* quota */
  }
}

export function columnMin(id: RunColumnId): number {
  return MIN_WIDTH[id];
}

export function columnMax(): number {
  return MAX_WIDTH;
}
