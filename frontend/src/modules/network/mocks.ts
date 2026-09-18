import { ApiError } from '@/api/client';
import type { NetworkListItem } from '@/modules/dashboard/model';
import type { AgentNetworkDocument, ToolCatalogGroup } from '@/modules/network/model/document';
import { cloneDocument } from '@/modules/network/model/document';
import { validateDocument } from '@/modules/network/validation/validate';
import { mockGetDataLocation, mockListMcpServers } from '@/modules/settings/mocks';
import { useAppStore } from '@/store';

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

const demo: AgentNetworkDocument = {
  schemaVersion: 1,
  id: 'net-demo',
  name: 'Demo-Netz',
  description: 'Beispielnetz für den lokalen Lauf.',
  tags: ['demo'],
  updatedAt: hoursAgo(2),
  isActive: true,
  viewport: { x: 0, y: 0, zoom: 1 },
  nodes: [
    {
      id: 'chat-1',
      type: 'chat_input',
      position: { x: 0, y: 160 },
      data: { displayName: 'Eingabe', placeholder: 'Frage…', requireInput: false },
    },
    {
      id: 'llm-1',
      type: 'llm',
      position: { x: 0, y: 0 },
      data: { displayName: 'Lokal', provider: 'ollama', model: 'llama3.2:1b' },
    },
    {
      id: 'knowledge-1',
      type: 'knowledge',
      position: { x: 0, y: 320 },
      data: {
        displayName: 'Wissen',
        sourcePath: 'C:\\Users\\Demo\\AppData\\Local\\Agentus-Network\\data\\workspace\\demo',
        topK: 5,
      },
    },
    {
      id: 'agent-1',
      type: 'agent',
      position: { x: 280, y: 140 },
      data: { displayName: 'Assistent', systemPrompt: 'Du hilfst beim lokalen Netz.' },
    },
    {
      id: 'end-1',
      type: 'end',
      position: { x: 560, y: 160 },
      data: { displayName: 'Ende' },
    },
  ],
  edges: [
    { id: 'e-1', source: 'chat-1', sourceHandle: 'message', target: 'agent-1', targetHandle: 'message' },
    { id: 'e-2', source: 'llm-1', sourceHandle: 'llm', target: 'agent-1', targetHandle: 'llm' },
    { id: 'e-3', source: 'knowledge-1', sourceHandle: 'knowledge', target: 'agent-1', targetHandle: 'knowledge' },
    { id: 'e-4', source: 'agent-1', sourceHandle: 'message', target: 'end-1', targetHandle: 'message' },
  ],
};

const support: AgentNetworkDocument = {
  schemaVersion: 1,
  id: 'net-support',
  name: 'Support-Netz',
  description: 'Zweitnetz mit fehlendem Modell am LLM-Knoten.',
  tags: ['support'],
  updatedAt: hoursAgo(30),
  viewport: { x: 0, y: 0, zoom: 1 },
  nodes: [
    {
      id: 'llm-1',
      type: 'llm',
      position: { x: 0, y: 40 },
      data: { displayName: 'Cloud', provider: 'xai', model: '' },
    },
    {
      id: 'agent-1',
      type: 'agent',
      position: { x: 260, y: 80 },
      data: { displayName: 'Support', systemPrompt: '' },
    },
    {
      id: 'end-1',
      type: 'end',
      position: { x: 520, y: 100 },
      data: { displayName: 'Ende' },
    },
  ],
  edges: [
    { id: 'e-1', source: 'llm-1', sourceHandle: 'llm', target: 'agent-1', targetHandle: 'llm' },
    { id: 'e-2', source: 'agent-1', sourceHandle: 'message', target: 'end-1', targetHandle: 'message' },
  ],
};

let documents: AgentNetworkDocument[] = [structuredClone(demo), structuredClone(support)];

function delay(ms = 40) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function toListItem(doc: AgentNetworkDocument): NetworkListItem {
  const { activeNetworkId, serviceStatus } = useAppStore.getState();
  const running = serviceStatus === 'starting' || serviceStatus === 'running';
  const issues = validateDocument(doc);
  return {
    id: doc.id as string,
    name: doc.name,
    description: doc.description,
    tags: doc.tags,
    updatedAt: doc.updatedAt ?? new Date().toISOString(),
    nodeCount: doc.nodes.length,
    edgeCount: doc.edges.length,
    validationStatus: issues.length ? 'invalid' : 'valid',
    isActive: doc.id === activeNetworkId,
    isRunning: running && doc.id === activeNetworkId,
    validationErrors: issues.map((issue) => ({ nodeId: issue.nodeId, messageKey: issue.messageKey })),
  };
}

export async function mockListEditorNetworks(): Promise<{ items: NetworkListItem[] }> {
  await delay();
  return { items: documents.filter((doc) => doc.id).map(toListItem) };
}

export async function mockGetEditorNetwork(id: string): Promise<AgentNetworkDocument> {
  await delay();
  const doc = documents.find((item) => item.id === id);
  if (!doc) throw new ApiError(404, 'network.error.missing');
  return cloneDocument(doc);
}

export async function mockCreateNetwork(doc: AgentNetworkDocument): Promise<AgentNetworkDocument> {
  await delay();
  const created: AgentNetworkDocument = {
    ...cloneDocument(doc),
    id: crypto.randomUUID(),
    updatedAt: new Date().toISOString(),
    schemaVersion: 1,
  };
  documents = [created, ...documents];
  return cloneDocument(created);
}

export async function mockUpdateNetwork(id: string, doc: AgentNetworkDocument): Promise<AgentNetworkDocument> {
  await delay();
  const index = documents.findIndex((item) => item.id === id);
  if (index < 0) throw new ApiError(404, 'network.error.missing');
  const updated: AgentNetworkDocument = {
    ...cloneDocument(doc),
    id,
    updatedAt: new Date().toISOString(),
    schemaVersion: 1,
  };
  documents[index] = updated;
  return cloneDocument(updated);
}

export async function mockDuplicateNetwork(id: string): Promise<AgentNetworkDocument> {
  await delay();
  const source = documents.find((item) => item.id === id);
  if (!source) throw new ApiError(404, 'network.error.missing');
  const copy: AgentNetworkDocument = {
    ...cloneDocument(source),
    id: crypto.randomUUID(),
    name: `${source.name} (Kopie)`,
    isActive: false,
    updatedAt: new Date().toISOString(),
  };
  documents = [copy, ...documents];
  return cloneDocument(copy);
}

export async function mockValidateNetwork(doc: AgentNetworkDocument) {
  await delay();
  const location = await mockGetDataLocation();
  const mcp = await mockListMcpServers();
  const errors = validateDocument(doc, {
    dataDir: location.dataDir,
    mcpServers: mcp.items,
    helpCorpusHint: 'agentus_network_rag_documents',
  });
  return { valid: errors.length === 0, errors };
}

export async function mockListToolCatalog(): Promise<{ groups: ToolCatalogGroup[] }> {
  await delay();
  const mcp = await mockListMcpServers();
  const groups: ToolCatalogGroup[] = [
    {
      id: 'firstParty',
      titleKey: 'network.catalog.firstParty',
      tools: [
        { name: 'http', kind: 'http', credentialKind: 'token' },
        { name: 'web_search', kind: 'web_search', credentialKind: 'web_search' },
        { name: 'datetime', kind: 'datetime' },
        { name: 'calculator', kind: 'calculator' },
        { name: 'mcp', kind: 'mcp' },
      ],
    },
  ];
  for (const server of mcp.items.filter((item) => item.enabled)) {
    groups.push({
      id: server.id,
      titleKey: server.name,
      tools: [{ name: 'mcp', kind: 'mcp', serverId: server.id, mcpToolName: '*' }],
    });
  }
  return { groups };
}

export async function mockTestLlm(input: {
  provider: string;
  model: string;
  baseUrl?: string;
  credentialId?: string;
}) {
  await delay(200);
  const ok = Boolean(input.model.trim());
  return { ok, messageKey: ok ? 'network.inspector.llm.pingOk' : 'network.inspector.llm.pingFail' };
}

export async function mockReindexKnowledge(networkId: string, nodeId: string) {
  await delay(250);
  void networkId;
  void nodeId;
  return { state: 'ready' as const };
}
