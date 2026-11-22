export type NetworkColumnId = 'name' | 'tags' | 'kind' | 'description' | 'status' | 'updated';

const STORAGE_KEY = 'agentus.networks.listColumns';

export const NETWORK_COLUMN_IDS: NetworkColumnId[] = ['name', 'tags', 'kind', 'description', 'status', 'updated'];

export const DEFAULT_NETWORK_ORDER: NetworkColumnId[] = [...NETWORK_COLUMN_IDS];

const DEFAULT_WIDTH: Record<NetworkColumnId, number> = {
  name: 220,
  tags: 220,
  kind: 140,
  description: 220,
  status: 168,
  updated: 140,
};

const MIN_WIDTH: Record<NetworkColumnId, number> = {
  name: 120,
  tags: 96,
  kind: 96,
  description: 80,
  status: 96,
  updated: 88,
};

const MAX_WIDTH = 720;

export type NetworkColumnLayout = {
  order: NetworkColumnId[];
  widths: Record<NetworkColumnId, number>;
};

function isColumnId(value: string): value is NetworkColumnId {
  return (NETWORK_COLUMN_IDS as string[]).includes(value);
}

export function clampColumnWidth(id: NetworkColumnId, value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_WIDTH[id];
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH[id], Math.round(value)));
}

export function normalizeNetworkColumns(raw: unknown): NetworkColumnLayout {
  const record = raw && typeof raw === 'object' ? (raw as { order?: unknown; widths?: unknown }) : {};
  const order: NetworkColumnId[] = [];
  const saved = Array.isArray(record.order) ? record.order : [];
  for (const raw of saved) {
    // Layouts saved before 2026-11-22: "graph" (node and edge counts) became "kind" at its place.
    const item = raw === 'graph' ? 'kind' : raw;
    if (typeof item === 'string' && isColumnId(item) && !order.includes(item)) order.push(item);
  }
  // Tags had no column of their own: they come second, right after the name.
  if (saved.length > 0 && !saved.includes('tags')) order.splice(Math.min(1, order.length), 0, 'tags');
  for (const id of DEFAULT_NETWORK_ORDER) {
    if (!order.includes(id)) order.push(id);
  }
  const widths = { ...DEFAULT_WIDTH };
  if (record.widths && typeof record.widths === 'object') {
    for (const id of NETWORK_COLUMN_IDS) {
      const value = (record.widths as Record<string, unknown>)[id];
      if (typeof value === 'number') widths[id] = clampColumnWidth(id, value);
    }
  }
  return { order, widths };
}

export function loadNetworkColumns(): NetworkColumnLayout {
  if (typeof window === 'undefined') return normalizeNetworkColumns(null);
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return normalizeNetworkColumns(null);
    return normalizeNetworkColumns(JSON.parse(raw) as unknown);
  } catch {
    return normalizeNetworkColumns(null);
  }
}

export function saveNetworkColumns(layout: NetworkColumnLayout): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeNetworkColumns(layout)));
  } catch {
    /* quota */
  }
}

export function columnMin(id: NetworkColumnId): number {
  return MIN_WIDTH[id];
}

export function columnMax(): number {
  return MAX_WIDTH;
}
