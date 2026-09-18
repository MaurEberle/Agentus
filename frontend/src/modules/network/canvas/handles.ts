import type { GraphEdge, PortDef } from '@/modules/network/model/document';

/** Vertical space reserved per handle so stacked ports do not overlap. */
export const HANDLE_ROW_PX = 32;
const NODE_CHROME_PX = 16;
const NODE_HEADER_PX = 72;

export function rfHandleId(port: PortDef): string {
  if (port.direction === 'out' && port.id === 'message') return 'out-message';
  return port.id;
}

export function docHandleId(handle: string | null | undefined): string {
  if (handle === 'out-message') return 'message';
  return handle ?? '';
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
