import { embeddingNeedsCredential, isForbiddenDataRoot } from '@/modules/settings/model';
import type { McpServerListItem } from '@/modules/settings/model';
import { connectionAllowed, portKind, type PortContext } from '@/modules/network/schema/ports';
import type {
  AgentNetworkDocument,
  GraphNode,
  KnowledgeState,
  ValidationIssue,
} from '@/modules/network/model/document';

const MCP_NEEDS_ROOT = new Set([
  'filesystem',
  'git',
  'pdf',
  'excel',
  'powerpoint',
  'word',
  'office',
]);

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function hasCycle(doc: AgentNetworkDocument): boolean {
  const outgoing = new Map<string, string[]>();
  for (const node of doc.nodes) outgoing.set(node.id, []);
  for (const edge of doc.edges) {
    outgoing.get(edge.source)?.push(edge.target);
  }
  const visiting = new Set<string>();
  const seen = new Set<string>();
  const visit = (id: string): boolean => {
    if (visiting.has(id)) return true;
    if (seen.has(id)) return false;
    visiting.add(id);
    for (const next of outgoing.get(id) ?? []) {
      if (visit(next)) return true;
    }
    visiting.delete(id);
    seen.add(id);
    return false;
  };
  return doc.nodes.some((node) => visit(node.id));
}

export function validateDocument(
  doc: AgentNetworkDocument,
  options: {
    mcpServers?: McpServerListItem[];
    dataDir?: string;
    helpCorpusHint?: string;
    knowledge?: Array<{ nodeId: string; state: KnowledgeState }>;
  } = {},
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const byId = new Map(doc.nodes.map((node) => [node.id, node]));
  const portContext: PortContext = { nodes: doc.nodes, edges: doc.edges };

  if (!doc.name.trim()) {
    issues.push({ messageKey: 'network.validation.nameRequired' });
  }

  const chatInputs = doc.nodes.filter((node) => node.type === 'chat_input');
  if (chatInputs.length > 1) {
    for (const node of chatInputs) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.tooManyChatInputs' });
    }
  }
  const orchestrators = doc.nodes.filter((node) => node.type === 'orchestrator');
  if (orchestrators.length > 1) {
    for (const node of orchestrators) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.orchestratorDuplicate' });
    }
  }
  if (orchestrators.length === 1) {
    const orch = orchestrators[0];
    if (incoming(doc, orch.id, 'llm', 'llm').length !== 1) {
      issues.push({ nodeId: orch.id, messageKey: 'network.validation.orchestratorLlm' });
    }
    const chat = chatInputs[0];
    const fromChat = chat ? doc.edges.filter((edge) => edge.source === chat.id) : [];
    if (!chat || !fromChat.some((edge) => edge.target === orch.id && edge.targetHandle === 'message')) {
      issues.push({ nodeId: orch.id, messageKey: 'network.validation.orchestratorChat' });
    }
    if (fromChat.some((edge) => edge.target !== orch.id)) {
      issues.push({ nodeId: chat?.id, messageKey: 'network.validation.orchestratorFanout' });
    }
    const toEnd = doc.edges.some(
      (edge) => edge.source === orch.id && edge.sourceHandle === 'message' && byId.get(edge.target)?.type === 'end',
    );
    if (!toEnd) {
      issues.push({ nodeId: orch.id, messageKey: 'network.validation.orchestratorEnd' });
    }
  }
  if (!doc.nodes.some((node) => node.type === 'end')) {
    issues.push({ messageKey: 'network.validation.endRequired' });
  }

  for (const edge of doc.edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) {
      issues.push({ edgeId: edge.id, messageKey: 'network.validation.danglingEdge' });
      continue;
    }
    if (
      !connectionAllowed({
        source,
        target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        context: portContext,
        ignore: edge,
      })
    ) {
      issues.push({ edgeId: edge.id, nodeId: source.id, messageKey: 'network.validation.edgeType' });
    }
  }

  for (const node of doc.nodes) {
    issues.push(...validateNode(node, doc, options));
  }

  if (hasCycle(doc)) {
    issues.push({ messageKey: 'network.validation.cycle' });
  }

  return issues;
}

function incoming(doc: AgentNetworkDocument, nodeId: string, handle: string, kind?: string) {
  return doc.edges.filter((edge) => {
    if (edge.target !== nodeId || edge.targetHandle !== handle) return false;
    if (!kind) return true;
    const source = doc.nodes.find((node) => node.id === edge.source);
    if (!source) return false;
    return portKind(source, edge.sourceHandle, 'out') === kind;
  });
}

function validateNode(
  node: GraphNode,
  doc: AgentNetworkDocument,
  options: {
    mcpServers?: McpServerListItem[];
    dataDir?: string;
    helpCorpusHint?: string;
    knowledge?: Array<{ nodeId: string; state: KnowledgeState }>;
  },
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (node.type === 'agent') {
    if (incoming(doc, node.id, 'llm', 'llm').length !== 1) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.agentLlm' });
    }
    const channels = doc.edges.filter((edge) => edge.target === node.id && edge.targetHandle === 'channel');
    const pipelineIn =
      incoming(doc, node.id, 'message', 'message').length + incoming(doc, node.id, 'message', 'handoff').length;
    const pipelineOut = doc.edges.some(
      (edge) => edge.source === node.id && (edge.sourceHandle === 'message' || edge.sourceHandle === 'handoff'),
    );
    if (channels.length > 1) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.agentChannel' });
    }
    if (channels.length > 0 && (pipelineIn > 0 || pipelineOut)) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.agentMode' });
    }
    const orchestrated = doc.nodes.some((item) => item.type === 'orchestrator');
    if (orchestrated && channels.length === 0) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.orchestratorLooseAgent' });
    } else if (channels.length === 0 && pipelineIn < 1) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.agentMessage' });
    }
  }
  if (node.type === 'llm') {
    const provider = asString(node.data.provider) || 'ollama';
    if (!asString(node.data.model)) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.modelRequired' });
    }
    if (provider !== 'ollama' && !asString(node.data.credentialId)) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.credentialRequired' });
    }
  }
  if (node.type === 'tool') {
    const kind = asString(node.data.kind);
    if (!kind) issues.push({ nodeId: node.id, messageKey: 'network.validation.toolKind' });
    if (kind === 'file_access') {
      const root = asString(node.data.rootPath);
      if (!root || isForbiddenDataRoot(root)) {
        issues.push({ nodeId: node.id, messageKey: 'network.validation.fileAccessRoot' });
      }
    }
    if (kind === 'mcp') {
      const serverId = asString(node.data.mcpServerId);
      const server = options.mcpServers?.find((item) => item.id === serverId);
      if (!server || !server.enabled) {
        issues.push({ nodeId: node.id, messageKey: 'network.validation.mcpServer' });
      } else if (MCP_NEEDS_ROOT.has(server.recipeId ?? '') && !asString(server.rootPath)) {
        issues.push({ nodeId: node.id, messageKey: 'network.validation.mcpRoot' });
      }
    }
  }
  if (node.type === 'knowledge') {
    const embedProvider = asString(node.data.embeddingProvider) || 'ollama';
    if (embeddingNeedsCredential(embedProvider) && !asString(node.data.embeddingCredentialId)) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.credentialRequired' });
    }
    const path = asString(node.data.sourcePath);
    if (!path) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.knowledgePath' });
    } else if (isForbiddenDataRoot(path)) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.knowledgeRoot' });
    } else if (options.helpCorpusHint && path.toLowerCase().includes(options.helpCorpusHint.toLowerCase())) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.knowledgeHelpCorpus' });
    }
    const outgoing = doc.edges.filter((edge) => edge.source === node.id);
    if (outgoing.some((edge) => edge.targetHandle !== 'knowledge')) {
      issues.push({ nodeId: node.id, messageKey: 'network.validation.knowledgeTarget' });
    }
    const state = options.knowledge?.find((item) => item.nodeId === node.id)?.state;
    if (state === 'missing' || state === 'stale' || state === 'error') {
      issues.push({ nodeId: node.id, messageKey: `network.validation.knowledge.${state}` });
    }
  }
  return issues;
}

export function issuesForNode(issues: ValidationIssue[], nodeId: string) {
  return issues.filter((issue) => issue.nodeId === nodeId);
}
