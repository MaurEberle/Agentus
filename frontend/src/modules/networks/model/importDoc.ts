import {
  NODE_TYPES,
  SCHEMA_VERSION,
  type AgentNetworkDocument,
  type GraphEdge,
  type GraphNode,
  type NodeType,
} from '@/modules/network/model/document';
import { sanitizeDocument } from '@/modules/network/model/serialize';

const SECRET_KEYS = /^(secret|password|token|apiKey|authorization|bearer)$/i;

export type ImportParseOk = {
  fileName: string;
  document: AgentNetworkDocument;
  strippedSecrets: boolean;
};

export type ImportParseFail = {
  fileName: string;
  errorKey: 'networks.import.unreadable' | 'networks.import.schema';
};

export type ImportParseResult = ImportParseOk | ImportParseFail;

export function isImportFail(result: ImportParseResult): result is ImportParseFail {
  return 'errorKey' in result;
}

function stripSecretsDeep(value: unknown): { value: unknown; stripped: boolean } {
  if (Array.isArray(value)) {
    let stripped = false;
    const next = value.map((item) => {
      const result = stripSecretsDeep(item);
      stripped = stripped || result.stripped;
      return result.value;
    });
    return { value: next, stripped };
  }
  if (!value || typeof value !== 'object') return { value, stripped: false };
  const record = value as Record<string, unknown>;
  const next: Record<string, unknown> = {};
  let stripped = false;
  for (const [key, child] of Object.entries(record)) {
    if (SECRET_KEYS.test(key)) {
      stripped = true;
      continue;
    }
    const result = stripSecretsDeep(child);
    next[key] = result.value;
    stripped = stripped || result.stripped;
  }
  return { value: next, stripped };
}

function asNodes(value: unknown): GraphNode[] | null {
  if (!Array.isArray(value)) return null;
  const nodes: GraphNode[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') return null;
    const record = item as Record<string, unknown>;
    if (typeof record.id !== 'string' || typeof record.type !== 'string') return null;
    if (!(NODE_TYPES as readonly string[]).includes(record.type)) return null;
    if (!record.position || typeof record.position !== 'object') return null;
    nodes.push({
      id: record.id,
      type: record.type as NodeType,
      position: record.position as GraphNode['position'],
      data: record.data && typeof record.data === 'object' ? (record.data as Record<string, unknown>) : {},
    });
  }
  return nodes;
}

function asEdges(value: unknown): GraphEdge[] | null {
  if (!Array.isArray(value)) return null;
  const edges: GraphEdge[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') return null;
    const record = item as Record<string, unknown>;
    if (
      typeof record.id !== 'string' ||
      typeof record.source !== 'string' ||
      typeof record.target !== 'string' ||
      typeof record.sourceHandle !== 'string' ||
      typeof record.targetHandle !== 'string'
    ) {
      return null;
    }
    edges.push({
      id: record.id,
      source: record.source,
      target: record.target,
      sourceHandle: record.sourceHandle,
      targetHandle: record.targetHandle,
    });
  }
  return edges;
}

export function parseImportJson(fileName: string, raw: unknown): ImportParseResult {
  if (!raw || typeof raw !== 'object') return { fileName, errorKey: 'networks.import.unreadable' };
  const record = raw as Record<string, unknown>;
  if (record.schemaVersion !== SCHEMA_VERSION) return { fileName, errorKey: 'networks.import.schema' };
  const nodes = asNodes(record.nodes);
  const edges = asEdges(record.edges);
  if (!nodes || !edges) return { fileName, errorKey: 'networks.import.unreadable' };
  const stripped = stripSecretsDeep(record);
  const cleaned = stripped.value as Record<string, unknown>;
  const name =
    typeof cleaned.name === 'string' && cleaned.name.trim()
      ? cleaned.name.trim()
      : fileName.replace(/\.json$/i, '') || 'network';
  const document = sanitizeDocument({
    schemaVersion: 1,
    name,
    description: typeof cleaned.description === 'string' ? cleaned.description : undefined,
    tags: Array.isArray(cleaned.tags) ? cleaned.tags.filter((tag): tag is string => typeof tag === 'string') : [],
    nodes,
    edges,
    viewport:
      cleaned.viewport && typeof cleaned.viewport === 'object'
        ? (cleaned.viewport as AgentNetworkDocument['viewport'])
        : { x: 0, y: 0, zoom: 1 },
  });
  return { fileName, document, strippedSecrets: stripped.stripped };
}

export function exportFileStem(name: string): string {
  const stem = name
    .trim()
    .replace(/[^\w-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 60);
  return stem || 'network';
}

export function exportStamp(date = new Date()): string {
  return date.toISOString().slice(0, 10);
}
