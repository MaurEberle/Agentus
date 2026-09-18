import type { LlmProvider } from '@/modules/settings/model';

export const SCHEMA_VERSION = 1;
export const SNAP_SIZE = 16;

export const NODE_TYPES = [
  'chat_input',
  'llm',
  'agent',
  'tool',
  'knowledge',
  'router',
  'end',
] as const;

export type NodeType = (typeof NODE_TYPES)[number];

export type PortKind = 'message' | 'llm' | 'tool' | 'knowledge' | 'handoff';

export type PortDef = {
  id: string;
  kind: PortKind;
  direction: 'in' | 'out';
  /** Must have ≥1 compatible edge before the graph is valid. */
  required?: boolean;
};

export type RouterBranch = {
  id: string;
  name: string;
  condition: string;
};

export type ChatInputData = {
  displayName?: string;
  placeholder?: string;
  startMessage?: string;
  requireInput?: boolean;
};

export type LlmNodeData = {
  displayName?: string;
  provider: LlmProvider;
  model: string;
  baseUrl?: string;
  credentialId?: string;
  temperature?: number;
  maxTokens?: number;
};

export type AgentNodeData = {
  displayName?: string;
  systemPrompt?: string;
};

export type ToolKind = 'http' | 'web_search' | 'datetime' | 'calculator' | 'mcp';

export type ToolNodeData = {
  displayName?: string;
  kind: ToolKind;
  credentialId?: string;
  mcpServerId?: string;
  mcpToolNames?: string[];
  method?: string;
  url?: string;
};

export type KnowledgeNodeData = {
  displayName?: string;
  sourcePath: string;
  topK?: number;
  scoreThreshold?: number;
};

export type RouterNodeData = {
  displayName?: string;
  branches: RouterBranch[];
};

export type EndNodeData = {
  displayName?: string;
};

export type NodeDataMap = {
  chat_input: ChatInputData;
  llm: LlmNodeData;
  agent: AgentNodeData;
  tool: ToolNodeData;
  knowledge: KnowledgeNodeData;
  router: RouterNodeData;
  end: EndNodeData;
};

export type GraphNode = {
  id: string;
  type: NodeType;
  position: { x: number; y: number };
  data: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  source: string;
  sourceHandle: string;
  target: string;
  targetHandle: string;
};

export type AgentNetworkDocument = {
  schemaVersion: 1;
  id?: string;
  name: string;
  description?: string;
  tags?: string[];
  updatedAt?: string;
  isActive?: boolean;
  viewport?: { x: number; y: number; zoom: number };
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type ValidationIssue = {
  nodeId?: string;
  edgeId?: string;
  messageKey: string;
  values?: Record<string, string>;
};

export type KnowledgeState = 'ready' | 'missing' | 'stale' | 'indexing' | 'error';

export type CatalogTool = {
  name: string;
  kind?: string;
  description?: string;
  credentialKind?: string;
  serverId?: string;
  mcpToolName?: string;
};

export type ToolCatalogGroup = {
  id: string;
  titleKey?: string;
  tools: CatalogTool[];
};

export function emptyDocument(): AgentNetworkDocument {
  return {
    schemaVersion: SCHEMA_VERSION,
    name: '',
    tags: [],
    viewport: { x: 0, y: 0, zoom: 1 },
    nodes: [],
    edges: [],
  };
}

export function cloneDocument(doc: AgentNetworkDocument): AgentNetworkDocument {
  return structuredClone(doc);
}

export function displayNameOf(node: GraphNode): string {
  const name = node.data.displayName;
  return typeof name === 'string' && name.trim() ? name.trim() : node.type;
}

export function snapPosition(position: { x: number; y: number }, snap: boolean) {
  if (!snap) return position;
  return {
    x: Math.round(position.x / SNAP_SIZE) * SNAP_SIZE,
    y: Math.round(position.y / SNAP_SIZE) * SNAP_SIZE,
  };
}

export function newId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
}
