import type { GraphEdge, GraphNode, PortDef } from '@/modules/network/model/document';
import { portsFor } from '@/modules/network/schema/ports';

/** Vertical space reserved per handle so stacked ports do not overlap. */
export const HANDLE_ROW_PX = 32;
const NODE_CHROME_PX = 16;
const NODE_HEADER_PX = 52;

export function rfHandleId(port: PortDef): string {
  if (port.direction === 'out' && port.id === 'message') return 'out-message';
  return port.id;
}

export function docHandleId(handle: string | null | undefined): string {
  if (handle === 'out-message') return 'message';
  return handle ?? '';
}

function portByHandle(
  node: GraphNode | undefined,
  direction: 'in' | 'out',
  handle?: string | null,
): PortDef | undefined {
  if (!node || !handle) return undefined;
  return portsFor(node).find(
    (port) => port.direction === direction && (port.id === handle || rfHandleId(port) === handle),
  );
}

/** Map document handle ids onto React Flow handle ids (`message` out → `out-message`). */
export function toRfHandlePair(
  source: GraphNode | undefined,
  target: GraphNode | undefined,
  edge: { sourceHandle?: string | null; targetHandle?: string | null },
): { sourceHandle?: string; targetHandle?: string } {
  const sourcePort = portByHandle(source, 'out', edge.sourceHandle);
  const targetPort = portByHandle(target, 'in', edge.targetHandle);
  return {
    sourceHandle: sourcePort ? rfHandleId(sourcePort) : (edge.sourceHandle ?? undefined),
    targetHandle: targetPort ? rfHandleId(targetPort) : (edge.targetHandle ?? undefined),
  };
}

export function portStateKey(port: PortDef): string {
  return `${port.direction}:${port.id}`;
}

export function connectedPortKeys(nodeId: string, edges: GraphEdge[]): string[] {
  const keys: string[] = [];
  for (const edge of edges) {
    if (edge.target === nodeId) keys.push(`in:${edge.targetHandle}`);
    if (edge.source === nodeId) keys.push(`out:${edge.sourceHandle}`);
  }
  return keys;
}

export function nodeMinHeightPx(inCount: number, outCount: number): number {
  const rows = Math.max(inCount, outCount, 1);
  return Math.max(NODE_HEADER_PX, NODE_CHROME_PX + rows * HANDLE_ROW_PX);
}

export function handleTopPercent(index: number, count: number): string {
  if (count <= 1) return '50%';
  return `${((index + 1) / (count + 1)) * 100}%`;
}
