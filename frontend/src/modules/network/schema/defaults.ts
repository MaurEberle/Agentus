import type { GraphNode, NodeType } from '@/modules/network/model/document';
import { newId, snapPosition } from '@/modules/network/model/document';
import { nodeSpec } from '@/modules/network/schema/catalog';

/** Data a new node starts with: the catalog's `initial` values; router branches get ids. */
export function defaultData(type: NodeType): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const field of nodeSpec(type).fields) {
    if ('initial' in field) data[field.key] = structuredClone(field.initial);
  }
  if (type === 'router' && Array.isArray(data.branches)) {
    data.branches = data.branches.map((branch) => ({ id: newId('br'), ...(branch as object) }));
  }
  return data;
}

export function createNode(type: NodeType, position: { x: number; y: number }, snap: boolean): GraphNode {
  return {
    id: newId(type),
    type,
    position: snapPosition(position, snap),
    data: defaultData(type),
  };
}
