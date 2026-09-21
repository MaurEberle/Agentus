import { NODE_TYPES, type GraphNode, type NodeType, type PortDef, type PortKind } from '@/modules/network/model/document';
import {
  CHANNEL_GHOST_ID,
  agentIdFromChannel,
  channelHandle,
  channelLabel,
} from '@/modules/network/schema/channels';

const STATIC_PORTS: Record<NodeType, PortDef[]> = {
  chat_input: [{ id: 'message', kind: 'message', direction: 'out' }],
  orchestrator: [
    { id: 'message', kind: 'message', direction: 'in', required: true },
    { id: 'llm', kind: 'llm', direction: 'in', required: true },
    { id: 'message', kind: 'message', direction: 'out' },
  ],
  llm: [{ id: 'llm', kind: 'llm', direction: 'out' }],
  agent: [
    { id: 'message', kind: 'message', direction: 'in', required: true },
    { id: 'llm', kind: 'llm', direction: 'in', required: true },
    { id: 'tool', kind: 'tool', direction: 'in' },
    { id: 'knowledge', kind: 'knowledge', direction: 'in' },
    { id: 'channel', kind: 'channel', direction: 'in' },
    { id: 'message', kind: 'message', direction: 'out' },
    { id: 'handoff', kind: 'handoff', direction: 'out' },
  ],
  tool: [{ id: 'tool', kind: 'tool', direction: 'out' }],
  knowledge: [{ id: 'knowledge', kind: 'knowledge', direction: 'out' }],
  router: [{ id: 'message', kind: 'message', direction: 'in', required: true }],
  end: [{ id: 'message', kind: 'message', direction: 'in', required: true }],
};

export type PortEdge = {
  source: string;
  sourceHandle: string;
  target: string;
  targetHandle: string;
};

export type PortContext = {
  nodes: GraphNode[];
  edges: PortEdge[];
};

export function asPortContext(
  nodes: Array<{ id: string; type: string; position?: { x: number; y: number }; data?: Record<string, unknown> }>,
  edges: Array<{ source: string; sourceHandle?: string | null; target: string; targetHandle?: string | null }>,
): PortContext {
  const graphNodes: GraphNode[] = [];
  for (const node of nodes) {
    if (!(NODE_TYPES as readonly string[]).includes(node.type)) continue;
    graphNodes.push({
      id: node.id,
      type: node.type as NodeType,
      position: node.position ?? { x: 0, y: 0 },
      data: node.data ?? {},
    });
  }
  return {
    nodes: graphNodes,
    edges: edges.map((edge) => ({
      source: edge.source,
      sourceHandle: edge.sourceHandle ?? '',
      target: edge.target,
      targetHandle: edge.targetHandle ?? '',
    })),
  };
}

export function portsFor(node: GraphNode, context?: PortContext): PortDef[] {
  const base = STATIC_PORTS[node.type];
  if (node.type === 'router') {
    const branches = Array.isArray(node.data.branches) ? node.data.branches : [];
    const outs: PortDef[] = [{ id: 'default', kind: 'message', direction: 'out' }];
    for (const branch of branches) {
      const id = String((branch as { id?: string }).id ?? '');
      if (id) outs.push({ id, kind: 'message', direction: 'out' });
    }
    return [...base, ...outs];
  }
  if (node.type === 'agent') {
    const onChannel = (context?.edges ?? []).some(
      (edge) => edge.target === node.id && edge.targetHandle === 'channel',
    );
    const orchestrated = (context?.nodes ?? []).some((item) => item.type === 'orchestrator');
    if (!onChannel && !orchestrated) return base;
    return base.map((port) => {
      if (port.direction === 'in' && port.id === 'message') return { ...port, required: false };
      if (port.direction === 'in' && port.id === 'channel') return { ...port, required: true };
      return port;
    });
  }
  if (node.type !== 'orchestrator') return base;
  const channels: PortDef[] = [];
  const seen = new Set<string>();
  for (const edge of context?.edges ?? []) {
    if (edge.source !== node.id) continue;
    const agentId = agentIdFromChannel(edge.sourceHandle);
    if (!agentId || seen.has(edge.sourceHandle)) continue;
    seen.add(edge.sourceHandle);
    const agent = context?.nodes.find((item) => item.id === agentId);
    channels.push({
      id: edge.sourceHandle,
      kind: 'channel',
      direction: 'out',
      label: channelLabel(agent, agentId),
    });
  }
  channels.push({ id: CHANNEL_GHOST_ID, kind: 'channel', direction: 'out' });
  const inputs = base.filter((port) => port.direction === 'in');
  const messageOut = base.filter((port) => port.direction === 'out');
  return [...inputs, ...channels, ...messageOut];
}

export function portKind(
  node: GraphNode,
  handleId: string | null | undefined,
  direction: 'in' | 'out',
  context?: PortContext,
): PortKind | null {
  if (!handleId) return null;
  const id = handleId === 'out-message' ? 'message' : handleId;
  return portsFor(node, context).find((port) => port.id === id && port.direction === direction)?.kind ?? null;
}

export function portI18nKey(port: PortDef): string {
  if (port.id === 'default') return 'network.ports.default';
  return `network.ports.${port.kind}`;
}

export function routerBranchName(node: GraphNode, portId: string): string | undefined {
  if (node.type !== 'router') return undefined;
  const branches = Array.isArray(node.data.branches) ? node.data.branches : [];
  for (const branch of branches) {
    const rec = branch as { id?: string; name?: string };
    if (rec.id !== portId) continue;
    const name = typeof rec.name === 'string' ? rec.name.trim() : '';
    return name || undefined;
  }
  return undefined;
}

function kindsCompatible(source: PortKind, target: PortKind): boolean {
  if (source === target) return true;
  if (source === 'handoff' && target === 'message') return true;
  return false;
}

function sameEdge(edge: PortEdge, ignore?: PortEdge): boolean {
  if (!ignore) return false;
  return (
    edge.source === ignore.source &&
    edge.target === ignore.target &&
    edge.sourceHandle === ignore.sourceHandle &&
    edge.targetHandle === ignore.targetHandle
  );
}

function hasChannel(context: PortContext | undefined, nodeId: string, ignore?: PortEdge): boolean {
  if (!context) return false;
  return context.edges.some(
    (edge) => edge.target === nodeId && edge.targetHandle === 'channel' && !sameEdge(edge, ignore),
  );
}

function hasPipeline(context: PortContext | undefined, nodeId: string, ignore?: PortEdge): boolean {
  if (!context) return false;
  return context.edges.some(
    (edge) =>
      !sameEdge(edge, ignore) &&
      ((edge.target === nodeId && edge.targetHandle === 'message') ||
        (edge.source === nodeId && (edge.sourceHandle === 'message' || edge.sourceHandle === 'handoff'))),
  );
}

export function connectionAllowed(input: {
  source: GraphNode;
  target: GraphNode;
  sourceHandle: string | null | undefined;
  targetHandle: string | null | undefined;
  context?: PortContext;
  /** Skip this edge so validating a saved channel does not count it as a second one. */
  ignore?: PortEdge;
}): boolean {
  if (input.source.id === input.target.id) return false;
  const from = portKind(input.source, input.sourceHandle, 'out', input.context);
  const to = portKind(input.target, input.targetHandle, 'in', input.context);
  if (!from || !to) return false;
  if (from === 'knowledge' && !(input.target.type === 'agent' && to === 'knowledge')) return false;
  if (from === 'channel' || to === 'channel') {
    if (!(input.source.type === 'orchestrator' && input.target.type === 'agent' && from === 'channel' && to === 'channel')) {
      return false;
    }
    const bound = agentIdFromChannel(input.sourceHandle);
    if (bound && bound !== input.target.id) return false;
    if (hasChannel(input.context, input.target.id, input.ignore)) return false;
    if (hasPipeline(input.context, input.target.id, input.ignore)) return false;
    return true;
  }
  if (input.source.type === 'orchestrator' && from === 'message') {
    if (input.target.type !== 'end' && input.target.type !== 'router') return false;
  }
  if (!kindsCompatible(from, to)) return false;
  if (
    input.source.type === 'agent' &&
    (from === 'message' || from === 'handoff') &&
    hasChannel(input.context, input.source.id, input.ignore)
  ) {
    return false;
  }
  if (input.target.type === 'agent' && to === 'message' && hasChannel(input.context, input.target.id, input.ignore)) {
    return false;
  }
  return true;
}

/** Whether `toPort` on `toNode` can complete a drag that started at `from`. */
export function portAcceptsConnection(
  toNode: GraphNode,
  toPort: PortDef,
  from: {
    node: GraphNode;
    handleId: string | null | undefined;
    handleType: 'source' | 'target';
  },
  context?: PortContext,
): boolean {
  if (from.node.id === toNode.id) return false;
  if (from.handleType === 'source') {
    if (toPort.direction !== 'in') return false;
    return connectionAllowed({
      source: from.node,
      target: toNode,
      sourceHandle: from.handleId,
      targetHandle: toPort.id,
      context,
    });
  }
  if (toPort.direction !== 'out') return false;
  return connectionAllowed({
    source: toNode,
    target: from.node,
    sourceHandle: toPort.id,
    targetHandle: from.handleId,
    context,
  });
}

export function bindChannelHandle(sourceHandle: string, agentId: string): string {
  if (sourceHandle === CHANNEL_GHOST_ID || agentIdFromChannel(sourceHandle)) return channelHandle(agentId);
  return sourceHandle;
}

export const PALETTE_TYPES: NodeType[] = [
  'chat_input',
  'orchestrator',
  'llm',
  'agent',
  'tool',
  'knowledge',
  'router',
  'end',
];
