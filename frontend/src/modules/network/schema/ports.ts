import type { GraphNode, NodeType, PortDef, PortKind } from '@/modules/network/model/document';

const STATIC_PORTS: Record<NodeType, PortDef[]> = {
  chat_input: [{ id: 'message', kind: 'message', direction: 'out' }],
  llm: [{ id: 'llm', kind: 'llm', direction: 'out' }],
  agent: [
    { id: 'message', kind: 'message', direction: 'in', required: true },
    { id: 'llm', kind: 'llm', direction: 'in', required: true },
    { id: 'tool', kind: 'tool', direction: 'in' },
    { id: 'knowledge', kind: 'knowledge', direction: 'in' },
    { id: 'message', kind: 'message', direction: 'out' },
    { id: 'handoff', kind: 'handoff', direction: 'out' },
  ],
  tool: [{ id: 'tool', kind: 'tool', direction: 'out' }],
  knowledge: [{ id: 'knowledge', kind: 'knowledge', direction: 'out' }],
  router: [{ id: 'message', kind: 'message', direction: 'in', required: true }],
  end: [{ id: 'message', kind: 'message', direction: 'in', required: true }],
};

export function portsFor(node: GraphNode): PortDef[] {
  const base = STATIC_PORTS[node.type];
  if (node.type !== 'router') return base;
  const branches = Array.isArray(node.data.branches) ? node.data.branches : [];
  const outs: PortDef[] = [{ id: 'default', kind: 'message', direction: 'out' }];
  for (const branch of branches) {
    const id = String((branch as { id?: string }).id ?? '');
    if (id) outs.push({ id, kind: 'message', direction: 'out' });
  }
  return [...base, ...outs];
}

export function portKind(node: GraphNode, handleId: string | null | undefined, direction: 'in' | 'out'): PortKind | null {
  if (!handleId) return null;
  const id = handleId === 'out-message' ? 'message' : handleId;
  return portsFor(node).find((port) => port.id === id && port.direction === direction)?.kind ?? null;
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

export function connectionAllowed(input: {
  source: GraphNode;
  target: GraphNode;
  sourceHandle: string | null | undefined;
  targetHandle: string | null | undefined;
}): boolean {
  if (input.source.id === input.target.id) return false;
  const from = portKind(input.source, input.sourceHandle, 'out');
  const to = portKind(input.target, input.targetHandle, 'in');
  if (!from || !to) return false;
  if (from === 'knowledge' && !(input.target.type === 'agent' && to === 'knowledge')) return false;
  return kindsCompatible(from, to);
}

export const PALETTE_TYPES: NodeType[] = [
  'chat_input',
  'llm',
  'agent',
  'tool',
  'knowledge',
  'router',
  'end',
];
